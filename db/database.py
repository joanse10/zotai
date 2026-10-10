"""
Stratul de persistență Zotero pe SQLite (schemă — vezi TZ.md §7).

Tabele:
- settings: setări cheie/valoare (mod AI, cale CLI, adresă Zotero etc.)
- tasks: coada de procesare a documentelor. Câmpul zotero_status='queued' funcționează
  ca o coadă offline (Zero Data Loss): sarcinile se încarcă când Zotero devine accesibil.

Conexiunile se deschid pentru fiecare operație + modul WAL — sigur pentru apeluri
concurente din threadul GUI și workerii de fundal fără blocaje globale.
"""

import os
import sqlite3
from typing import Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_str TEXT,           -- câmp auxiliar UI
    page_count INTEGER DEFAULT 0, -- câmp auxiliar UI
    layer_type TEXT,              -- 'text' | 'scan'
    detected_language TEXT,
    metadata_json TEXT,
    extracted_text TEXT,          -- eșantion de text pentru etapa AI
    stage TEXT NOT NULL,          -- 'pending','analyzing','ai','xmp','completed','failed'
    zotero_status TEXT NOT NULL,  -- 'synced','queued','error'
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_zotero_status ON tasks(zotero_status);
"""


def default_db_path() -> str:
    """Calea către BD: frozen -> %LOCALAPPDATA%\\Zotai, dev -> rădăcina proiectului."""
    from core.paths import db_path
    return db_path()


class ZotaiDB:
    def __init__(self, path: Optional[str] = None):
        self.path = path or default_db_path()
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection):
        """Adaugă coloanele apărute după versiunea inițială a schemei."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)")}
        for col, ddl in (("extracted_text", "TEXT"),
                         ("file_size_str", "TEXT"),
                         ("page_count", "INTEGER DEFAULT 0")):
            if col not in cols:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ------------------------------------------------------------------
    # Setări (cheie/valoare)
    # ------------------------------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )

    def all_settings(self) -> Dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ------------------------------------------------------------------
    # Coada de sarcini
    # ------------------------------------------------------------------
    def upsert_task(self, task: Dict):
        """
        task: {id, file_path, file_name, file_size_str, page_count, layer_type,
               detected_language, metadata_json, stage, zotero_status, error_message}
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, file_path, file_name, file_size_str, page_count,
                                   layer_type, detected_language, extracted_text,
                                   metadata_json, stage, zotero_status, error_message)
                VALUES (:id, :file_path, :file_name, :file_size_str, :page_count,
                        :layer_type, :detected_language, :extracted_text,
                        :metadata_json, :stage, :zotero_status, :error_message)
                ON CONFLICT(id) DO UPDATE SET
                    file_path = excluded.file_path,
                    file_name = excluded.file_name,
                    file_size_str = excluded.file_size_str,
                    page_count = excluded.page_count,
                    layer_type = excluded.layer_type,
                    detected_language = excluded.detected_language,
                    extracted_text = excluded.extracted_text,
                    metadata_json = excluded.metadata_json,
                    stage = excluded.stage,
                    zotero_status = excluded.zotero_status,
                    error_message = excluded.error_message,
                    updated_at = CURRENT_TIMESTAMP
                """,
                task,
            )

    def get_task(self, task_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def get_tasks(self) -> List[Dict]:
        """Toate sarcinile în ordinea adăugării."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at, rowid").fetchall()
        return [dict(r) for r in rows]

    def delete_task(self, task_id: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def clear_completed(self) -> int:
        """Șterge sarcinile finalizate (stage IN ('completed','xmp')). Returnează numărul șters."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE stage IN ('completed', 'xmp')")
            return cur.rowcount

    def update_task_stage(self, task_id: str, stage: str, error: Optional[str] = None):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET stage = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (stage, error, task_id),
            )

    def update_zotero_status(self, task_id: str, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET zotero_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, task_id),
            )

    # ------------------------------------------------------------------
    # Coada offline Zotero (Zero Data Loss)
    # ------------------------------------------------------------------
    def get_zotero_queue(self) -> List[Dict]:
        """Sarcini în așteptarea exportului în Zotero (zotero_status='queued')."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE zotero_status = 'queued' ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_zotero_synced(self, task_ids: List[str]) -> int:
        """Marchează sarcinile ca sincronizate. Returnează numărul de rânduri actualizate."""
        if not task_ids:
            return 0
        placeholders = ",".join("?" * len(task_ids))
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE tasks SET zotero_status = 'synced', updated_at = CURRENT_TIMESTAMP "
                f"WHERE id IN ({placeholders})",
                task_ids,
            )
            return cur.rowcount

    def count_by_zotero_status(self) -> Dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT zotero_status, COUNT(*) AS n FROM tasks GROUP BY zotero_status"
            ).fetchall()
        return {r["zotero_status"]: r["n"] for r in rows}
