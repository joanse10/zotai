"""
Depozitul de sarcini: mapare TaskItem (model UI) <-> rânduri din tabelul tasks.

UI operează cu statusuri în limba română ("Finalizat", "Sincronizat"),
iar BD stochează tokeni canonici ('pending', 'synced' etc.).
"""

import json
from dataclasses import asdict
from typing import List, Optional

from db.database import ZotaiDB
from gui.models import TaskItem, BookMetadata

# Etapă pipeline: șir UI -> token BD
STAGE_TO_DB = {
    "În așteptare": "pending",
    "Se analizează": "analyzing",
    "Analiză strat": "analyzing",
    "Analiză AI": "ai",
    "Analiză AI (agy)": "ai",
    "Scriere XMP": "xmp",
    "XMP actualizat": "xmp",
    "Finalizat": "completed",
    "Eroare": "failed",
}
STAGE_FROM_DB = {
    "pending": "În așteptare",
    "analyzing": "Analiză strat",
    "ai": "Analiză AI",
    "xmp": "XMP actualizat",
    "completed": "Finalizat",
    "failed": "Eroare",
}

# Tipul stratului de text: șir UI -> token BD
LAYER_TO_DB = {
    "Text": "text",
    "Scan (OCR)": "scan",
    "Scan": "scan",
}
LAYER_FROM_DB = {
    "text": "Text",
    "scan": "Scan (OCR)",
}

# Statusul sincronizării Zotero: șir UI -> token BD
ZOTERO_TO_DB = {
    "Sincronizat": "synced",
    "Zotero Offline (SQLite)": "queued",
    "În așteptare": "queued",   # sarcina nouă este deja în coada de export
    "Eroare": "error",
    "—": "none",                # fișă manuală — nu se exportă automat
}
ZOTERO_FROM_DB = {
    "synced": "Sincronizat",
    "queued": "Zotero Offline (SQLite)",
    "error": "Eroare Zotero",
    "none": "—",
}


def _lang_ui(raw: Optional[str]) -> str:
    """Coduri vechi din BD (RON/ENG/rus) -> ISO 639-1 afișat în UI (ro/en/ru)."""
    from gui.models import iso639_1
    code = iso639_1(raw or "")
    return code if code and code != "und" else "—"


def _norm(mapping: dict, key: str, default: str) -> str:
    """Potrivire exactă, apoi după subșir."""
    if key in mapping:
        return mapping[key]
    for k, v in mapping.items():
        if k in key:
            return v
    return default


class TaskRepository:
    """Acces la sarcini în termenii modelului UI TaskItem."""

    def __init__(self, db: Optional[ZotaiDB] = None):
        self.db = db or ZotaiDB()

    # ------------------------------------------------------------------
    # Mapare
    # ------------------------------------------------------------------
    @staticmethod
    def to_row(task: TaskItem) -> dict:
        return {
            "id": task.id,
            "file_path": task.file_path,
            "file_name": task.file_name,
            "file_size_str": task.file_size_str,
            "page_count": task.page_count,
            "layer_type": _norm(LAYER_TO_DB, task.layer_type, ""),
            "detected_language": task.language,
            "extracted_text": task.extracted_text,
            "metadata_json": json.dumps(asdict(task.metadata), ensure_ascii=False),
            "stage": _norm(STAGE_TO_DB, task.pipeline_stage, "pending"),
            "zotero_status": _norm(ZOTERO_TO_DB, task.zotero_status, "queued"),
            "error_message": task.error,
        }

    @staticmethod
    def from_row(row: dict) -> TaskItem:
        try:
            meta = BookMetadata(**json.loads(row["metadata_json"] or "{}"))
        except Exception:
            meta = BookMetadata()

        return TaskItem(
            id=row["id"],
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_size_str=row.get("file_size_str") or "—",
            page_count=row.get("page_count") or 0,
            layer_type=LAYER_FROM_DB.get(row["layer_type"], row["layer_type"] or "—"),
            language=_lang_ui(row["detected_language"]),
            pipeline_stage=STAGE_FROM_DB.get(row["stage"], row["stage"]),
            zotero_status=ZOTERO_FROM_DB.get(row["zotero_status"], row["zotero_status"]),
            metadata=meta,
            extracted_text=row.get("extracted_text") or "",
            error=row.get("error_message") or "",
        )

    # ------------------------------------------------------------------
    # Operații CRUD
    # ------------------------------------------------------------------
    def save(self, task: TaskItem):
        self.db.upsert_task(self.to_row(task))

    def save_all(self, tasks: List[TaskItem]):
        for t in tasks:
            self.save(t)

    def load_all(self) -> List[TaskItem]:
        return [self.from_row(r) for r in self.db.get_tasks()]

    def delete(self, task_id: str):
        self.db.delete_task(task_id)

    def clear_completed(self) -> int:
        return self.db.clear_completed()

    def set_stage(self, task: TaskItem, stage_ui: str, error: str = ""):
        task.pipeline_stage = stage_ui
        self.db.update_task_stage(task.id, _norm(STAGE_TO_DB, stage_ui, "pending"), error or None)

    def set_zotero_status(self, task: TaskItem, status_ui: str):
        task.zotero_status = status_ui
        self.db.update_zotero_status(task.id, _norm(ZOTERO_TO_DB, status_ui, "queued"))

    def update_zotero_status(self, task_id: str, status_ui: str):
        self.db.update_zotero_status(task_id, _norm(ZOTERO_TO_DB, status_ui, "queued"))

    def zotero_queue_count(self) -> int:
        return self.db.count_by_zotero_status().get("queued", 0)
