"""
Fereastra principală a aplicației Zotai, coordonând componentele UI izolate.
"""

import os
import re
import json
import time
import shutil
import logging
import customtkinter as ctk
from tkinter import filedialog
from typing import List, Optional
import uuid

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_TKDND = True
except ImportError:
    HAS_TKDND = False

from gui.theme import Theme
from gui.icons import setup_window_icon
from gui.models import TaskItem, BookMetadata
from db import ZotaiDB, TaskRepository
from zotero.connector import ZoteroConnector, DEFAULT_URL
from core.notifier import Notifier
from core.i18n import tr, set_language, get_language

log = logging.getLogger("zotai")
from gui.components.header import HeaderComponent
from gui.components.dropzone import DropzoneComponent
from gui.components.task_table import TaskTableComponent
from gui.components.metadata_inspector import MetadataInspectorComponent
from gui.components.status_bar import StatusBarComponent
from gui.dialogs.settings_dialog import SettingsDialog


class MainWindow(ctk.CTk, TkinterDnD.DnDWrapper if HAS_TKDND else object):
    def __init__(self):
        super().__init__()

        # Inițializarea motorului nativ TkinterDnD
        if HAS_TKDND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as e:
                log.warning("Eroare la inițializarea TkDnD: %s", e)

        # Stratul de persistență SQLite
        self.db = ZotaiDB()
        self.repo = TaskRepository(self.db)

        # Internaționalizare (i18n): limba din setări, implicit 'ro'
        set_language(self.db.get_setting("ui_lang", "ro"))

        # Configurarea ferestrei principale
        self.title(tr("app_title"))
        self.geometry("1180x740")
        self.minsize(1040, 680)
        self.configure(fg_color=Theme.BG_WINDOW)
        setup_window_icon(self)

        # Detectare automată a Antigravity CLI (agy) și popularea PATH
        try:
            from worker.ai_adapter import resolve_cli_binary
            resolve_cli_binary("agy")
        except Exception:
            pass

        # Starea aplicației
        self.tasks: List[TaskItem] = self._load_or_seed_tasks()
        self.selected_task: Optional[TaskItem] = self.tasks[0] if self.tasks else None
        self._last_drop_time = 0.0

        # Clientul Zotero Connector + monitorul de fundal al cozii
        self.zotero = ZoteroConnector(self.db.get_setting("zotero_url", DEFAULT_URL))
        self._zotero_busy = False

        # Notificări Toast Windows
        self.notifier = Notifier(enabled=self.db.get_setting("toast", "1") == "1")
        self._is_ai_on: Optional[bool] = None

        self._bind_cyrillic_clipboard()

        # Inițializarea interfeței
        self._build_layout()
        self._update_all_states()
        self._init_drag_and_drop()
        self._start_zotero_monitor()
        self._resume_unfinished_tasks()
        self._poll_inbox()

    def _poll_inbox(self):
        # Căile lăsate de o a doua instanță (meniu contextual etc.) se preiau aici
        try:
            from core.single_instance import drain_inbox
            paths = drain_inbox()
            if paths:
                self.deiconify()
                self.lift()
                self._process_incoming_paths(paths)
        except Exception as e:
            log.warning("Eroare la citirea inbox-ului: %s", e)
        finally:
            self.after(1500, self._poll_inbox)

    def _bind_cyrillic_clipboard(self):
        # Pe tastatura chirilică (ru/uk) Ctrl+C/V/X ajung cu keysym chirilic
        # și combinațiile latine nu se mai declanșează. Folosim keycode
        # (VK-codes Windows: C=67 V=86 X=88 A=65) — identice în orice tastatură.
        keymap = {67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>"}
        cyr_keysyms = {
            "cyrillic_es": "<<Copy>>", "cyrillic_em": "<<Paste>>",
            "cyrillic_che": "<<Cut>>",
        }

        def on_ctrl_key(event):
            w = event.widget
            if getattr(event, "keycode", 0) == 65 or event.keysym.lower() == "cyrillic_ef":
                try:
                    w.select_range(0, "end")
                except Exception:
                    try:
                        w.tag_add("sel", "1.0", "end")
                    except Exception:
                        return
                return "break"
            virt = keymap.get(getattr(event, "keycode", 0)) \
                or cyr_keysyms.get(event.keysym.lower())
            if virt:
                w.event_generate(virt)
                return "break"

        for cls in ("Entry", "TEntry", "Spinbox", "TSpinbox", "Text"):
            self.bind_class(cls, "<Control-KeyPress>", on_ctrl_key)

    def _build_layout(self):
        # 1. Antet
        self.header = HeaderComponent(
            self,
            on_open_settings=self._open_settings,
            on_check_zotero=self._check_zotero_status,
            on_check_ai=self._check_ai_status
        )
        self.header.pack(fill="x", side="top")

        # 2. Bara de stare
        self.status_bar = StatusBarComponent(
            self,
            on_sync_queue=self._sync_offline_queue
        )
        self.status_bar.pack(fill="x", side="bottom")

        # 3. Zona de lucru
        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.pack(fill="both", expand=True, padx=16, pady=12)

        # Panoul din stânga: Dropzone + Căutare + Tabel de sarcini
        self.left_pane = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.left_pane.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.dropzone = DropzoneComponent(
            self.left_pane,
            on_select_files=self._on_select_files,
            on_select_folder=self._on_select_folder
        )
        self.dropzone.pack(fill="x", pady=(0, 10))

        from gui.components.search_bar import SearchBarComponent
        self.search_bar = SearchBarComponent(self.left_pane, on_search=self._on_search)
        self.search_bar.pack(fill="x", pady=(0, 10))

        self.task_table = TaskTableComponent(
            self.left_pane,
            tasks=self.tasks,
            selected_task_id=self.selected_task.id if self.selected_task else None,
            on_select_task=self._on_select_task,
            on_delete_task=self._on_delete_task,
            on_clear_completed=self._on_clear_completed
        )
        self.task_table.pack(fill="both", expand=True)

        # Panoul din dreapta: inspectorul de metadate
        self.inspector = MetadataInspectorComponent(
            self.workspace,
            on_save_metadata=self._on_save_metadata,
            on_rescan_ai=self._on_rescan_ai,
            on_sync_zotero=self._on_sync_zotero_single
        )
        self.inspector.pack(side="right", fill="y", padx=(0, 0))

    def _update_stats_only(self):
        """Actualizează doar contoarele din bara de stare (fără a atinge rândurile tabelului)."""
        total = len(self.tasks)
        synced = sum(1 for t in self.tasks if "sincron" in t.zotero_status.lower())
        queued = sum(1 for t in self.tasks if "offline" in t.zotero_status.lower() or "așteptare" in t.zotero_status.lower())
        processing = sum(1 for t in self.tasks if any(k in t.pipeline_stage.lower() for k in ("ai", "analiz", "așteptare", "procesare")))
        self.status_bar.update_stats(total, synced, queued, processing)

    def _refresh_ai_badge(self, force: bool = False):
        """Verifică starea agentului CLI cu memorie cache pentru a evita căutările repetate pe disc."""
        if not force and self._is_ai_on is not None:
            badge_text = tr("ai_active", cli="agy") if self._is_ai_on else tr("ai_inactive")
            self.header.set_ai_status(badge_text, is_active=self._is_ai_on)
            return

        try:
            from worker.ai_adapter import resolve_cli_binary
            cli_cmd = self.db.get_setting("cli_cmd", "agy")
            resolved = resolve_cli_binary(cli_cmd)
            self._is_ai_on = os.path.isfile(resolved) or (shutil.which(resolved) is not None)
            badge_text = tr("ai_active", cli="agy") if self._is_ai_on else tr("ai_inactive")
            self.header.set_ai_status(badge_text, is_active=self._is_ai_on)
        except Exception:
            self._is_ai_on = False

    def _update_all_states(self):
        """Actualizare completă a interfeței (folosită doar la inițializare sau schimbări majore de listă)."""
        self.inspector.set_task(self.selected_task)
        self.task_table.set_tasks(
            self.tasks,
            selected_task_id=self.selected_task.id if self.selected_task else None
        )
        self._update_stats_only()
        self._refresh_ai_badge()

    # ------------------------------------------------------------------
    # Handlere de evenimente ale utilizatorului
    # ------------------------------------------------------------------
    def _on_select_task(self, task: TaskItem):
        """Selecție instantanee (0ms): nu redesenează tabelul, ci doar schimbă chenarul."""
        self.selected_task = task
        self.inspector.set_task(task)
        self.task_table.select_task_by_id(task.id)

    def _on_delete_task(self, task: TaskItem):
        self.tasks = [t for t in self.tasks if t.id != task.id]
        self.repo.delete(task.id)
        if self.selected_task and self.selected_task.id == task.id:
            self.selected_task = self.tasks[0] if self.tasks else None
        self._update_all_states()

    def _on_clear_completed(self):
        self.tasks = [t for t in self.tasks if not any(k in t.pipeline_stage.lower() for k in ("finalizat", "xmp actualizat"))]
        self.repo.clear_completed()
        if self.selected_task and self.selected_task not in self.tasks:
            self.selected_task = self.tasks[0] if self.tasks else None
        self._update_all_states()

    def _on_save_metadata(self, task: TaskItem, meta: BookMetadata):
        task.metadata = meta
        if task.file_path and os.path.isfile(task.file_path):
            from worker.xmp_injector import inject_metadata
            result = inject_metadata(task.file_path, meta)
            task.pipeline_stage = "XMP actualizat" if result.ok else "Eroare"
            if not result.ok:
                task.error = result.error
                log.error("Scrierea manuală XMP a eșuat | %s | %s", task.file_name, result.error)
                self.dropzone.flash_error(f"{tr('toast_task_xmp_failed')}: {result.error}")
        else:
            task.pipeline_stage = "Finalizat"
        self.repo.save(task)
        self.task_table.update_single_task(task)
        self._update_stats_only()

    def _on_rescan_ai(self, task: TaskItem):
        self._run_analysis([task])

    def _on_sync_zotero_single(self, task: TaskItem):
        # Pipeline încă în lucru — punem în coadă; monitorul trimite după finalizare
        if not any(k in task.pipeline_stage.lower() for k in ("finalizat", "xmp")):
            self.repo.set_zotero_status(task, "În așteptare")
            task.zotero_status = "În așteptare"
            self.task_table.update_single_task(task)
            self._update_stats_only()
            return

        prefer_recognize = self.db.get_setting("zotero_recognize", "1") == "1"

        import threading

        def work():
            if not self.zotero.ping():
                self.after(0, lambda: self._on_zotero_offline(task))
                return
            ok, info = self.zotero.send_task(task, prefer_recognize=prefer_recognize)
            self.after(0, lambda t=task, o=ok, m=info: self._on_zotero_sent(t, o, m))

        threading.Thread(target=work, daemon=True).start()

    def _on_zotero_offline(self, task: TaskItem):
        self.repo.set_zotero_status(task, "Zotero Offline (SQLite)")
        task.zotero_status = "Zotero Offline (SQLite)"
        self.task_table.update_single_task(task)
        self._update_stats_only()

    # ------------------------------------------------------------------
    # Căutarea online a metadatelor (ISBN / DOI / URL / titlu)
    # ------------------------------------------------------------------
    def _on_search(self, query: str):
        import threading
        from zotero import lookup

        self.search_bar.set_busy(True)

        def run():
            qtype, q = lookup.detect_query_type(query)
            log.info("Căutare: '%s' -> tip %s (%s)", query, qtype, q)
            try:
                if qtype == "doi":
                    fields, err = lookup.lookup_doi(q)
                    if fields:
                        self.after(0, lambda: self._create_card_task(fields))
                    elif not self._try_web_pdf(lookup, q):
                        self.after(0, lambda e=err, qq=q: self._offer_manual_card("doi", qq, e))
                elif qtype == "isbn":
                    fields, err = lookup.lookup_isbn(q)
                    if fields:
                        self.after(0, lambda: self._create_card_task(fields))
                    elif not self._try_web_pdf(lookup, q):
                        self.after(0, lambda e=err, qq=q: self._offer_manual_card("isbn", qq, e))
                elif qtype == "url_pdf":
                    from core.paths import downloads_dir
                    dest_dir = downloads_dir()
                    path, err = lookup.download_pdf(q, dest_dir)
                    if path:
                        self.after(0, lambda p=path: self._process_incoming_paths([p]))
                    else:
                        self.after(0, lambda e=err: self.dropzone.flash_error(e))
                elif qtype == "url":
                    from zotero.webpage import resolve_url
                    fields, pdf_url, err = resolve_url(q)
                    if not fields:
                        self.after(0, lambda e=err: self.dropzone.flash_error(e))
                    elif pdf_url:
                        # Pagina are PDF: îl descărcăm și rulăm pipeline-ul complet,
                        # cu metadatele paginii drept punct de plecare
                        from core.paths import downloads_dir
                        path, derr = lookup.download_pdf(pdf_url, downloads_dir(),
                                                         preferred_name=fields.get("title", ""))
                        if path:
                            log.info("PDF descărcat de pe pagină | %s -> %s", q, path)
                            self.after(0, lambda p=path, f=fields:
                                       self._process_incoming_paths([p], seed=f))
                        else:
                            log.warning("PDF-ul paginii nu s-a putut descărca (%s) — fișă fără fișier", derr)
                            self.after(0, lambda f=fields: self._create_card_task(f))
                    else:
                        self.after(0, lambda f=fields: self._create_card_task(f))
                else:
                    results, err = lookup.search_crossref(q)
                    if results:
                        self.after(0, lambda r=results: self._show_search_results(r))
                    else:
                        self.after(0, lambda e=err: self.dropzone.flash_error(
                            e or tr("search_no_results")))
            finally:
                self.after(0, lambda: self.search_bar.set_busy(False))

        threading.Thread(target=run, daemon=True).start()

    def _try_web_pdf(self, lookup, query: str) -> bool:
        """Rezervă web: caută PDF-ul după identificator (Brave API, dacă e configurat)."""
        key = self.db.get_setting("brave_api_key", "").strip()
        if not key:
            return False
        url, err = lookup.search_web_pdf(query, key)
        if not url:
            if err:
                log.warning("Căutare web PDF | %s | %s", query, err)
            return False
        from core.paths import downloads_dir
        path, derr = lookup.download_pdf(url, downloads_dir())
        if not path:
            log.warning("Descărcarea PDF a eșuat | %s | %s", url, derr)
            return False
        log.info("PDF găsit pe web | %s -> %s", query, url)
        self.after(0, lambda p=path: self._process_incoming_paths([p]))
        return True

    def _ask_yes_no(self, title: str, message: str) -> bool:
        """Dialog modal de confirmare în stilul aplicației (Da/Nu, nu nativ OS)."""
        result = {"ok": False}
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.configure(fg_color=Theme.BG_PANEL)
        dlg.resizable(False, False)
        setup_window_icon(dlg)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(
            dlg, text=message, font=Theme.font_body(),
            text_color=Theme.TEXT_MAIN, wraplength=380, justify="left"
        ).pack(padx=20, pady=(18, 14))

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=(0, 16))

        def yes():
            result["ok"] = True
            dlg.destroy()

        ctk.CTkButton(btns, text=tr("btn_yes"), width=90, fg_color=Theme.PRIMARY,
                      hover_color=Theme.PRIMARY_HOVER, command=yes).pack(side="left", padx=6)
        ctk.CTkButton(btns, text=tr("btn_no"), width=90, fg_color=Theme.BG_PANEL_ALT,
                      hover_color=Theme.BG_BORDER_LIGHT, border_width=1,
                      border_color=Theme.BG_BORDER, text_color=Theme.TEXT_MAIN,
                      command=dlg.destroy).pack(side="left", padx=6)

        dlg.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")
        self.wait_window(dlg)
        return result["ok"]

    def _offer_manual_card(self, qtype: str, q: str, err: str):
        """DOI/ISBN neînregistrat: propunem o fișă goală completabilă manual."""
        self.dropzone.flash_error(err)
        if not self._ask_yes_no(
            tr("search_not_found_title"),
            tr("search_manual_card_prompt", query=q)
        ):
            return
        fields = {
            "item_type": "book", "title": "", "authors": [],
            "doi": q if qtype == "doi" else "",
            "isbn": q if qtype == "isbn" else "",
            "confidence": 1.0,
        }
        self._create_card_task(fields, auto_queue=False)

    def _show_search_results(self, results: List[dict]):
        from gui.dialogs.search_results_dialog import SearchResultsDialog
        SearchResultsDialog(self, results, on_pick=self._create_card_task)

    def _create_card_task(self, fields: dict, auto_queue: bool = True):
        """Creează o sarcină de tip fișă (fără fișier PDF) din metadatele căutării."""
        from worker.ai_adapter import ai_fields_to_metadata
        from worker.merge import norm_lang

        task = TaskItem(
            id=str(uuid.uuid4()),
            file_name=fields.get("title") or fields.get("doi") or "Fișă",
            file_path="",
            file_size_str="—",
            page_count=0,
            layer_type="—",
            language=norm_lang(fields.get("language")) or "—",
            pipeline_stage="Finalizat",
            # Fișele goale (manual) nu pleacă singure în Zotero — lipsesc metadatele
            zotero_status="În așteptare" if auto_queue else "—",
            metadata=BookMetadata()
        )
        for k, v in ai_fields_to_metadata(fields).items():
            if v is not None and str(v).strip():
                setattr(task.metadata, k, v)

        self.tasks.append(task)
        self.repo.save(task)
        self.selected_task = task
        self._update_all_states()
        log.info("Fișă din căutare | %s | DOI:%s ISBN:%s",
                 task.metadata.title, task.metadata.doi, task.metadata.isbn)
        self.notifier.success(tr("toast_task_card_added"),
                              task.metadata.title[:80])

    # ------------------------------------------------------------------
    # Drag & Drop Windows (TkinterDnD)
    # ------------------------------------------------------------------
    def _init_drag_and_drop(self):
        if not HAS_TKDND:
            return
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_files_dropped)
            self.dnd_bind("<<DropEnter>>", self._on_drag_enter)
            self.dnd_bind("<<DropLeave>>", self._on_drag_leave)
        except Exception as e:
            log.warning("Eroare la înregistrarea Drag & Drop: %s", e)

    def _on_drag_enter(self, event=None):
        try:
            self.dropzone.configure(border_color=Theme.PRIMARY, border_width=2)
        except Exception:
            pass

    def _on_drag_leave(self, event=None):
        try:
            self.dropzone.configure(border_color=Theme.BG_BORDER, border_width=1)
        except Exception:
            pass

    def _on_files_dropped(self, event):
        self._on_drag_leave(event)
        raw_data = getattr(event, "data", "")
        if not raw_data:
            return

        matches = re.findall(r"\{([^}]+)\}|(\S+)", raw_data)
        paths = [m[0] or m[1] for m in matches]

        self._process_incoming_paths(paths)

    def _process_incoming_paths(self, raw_paths: List[str], seed: Optional[dict] = None):
        """
        Adaugă fișiere/foldere în coadă și pornește pipeline-ul.
        `seed` — metadate deja cunoscute (ex. de pe pagina web de unde s-a descărcat PDF-ul).
        """
        from worker import merge as _merge
        try:
            import pypdf
        except ImportError:
            pypdf = None

        pdf_files: List[str] = []
        supported = (".pdf", ".docx")
        for path in raw_paths:
            cleaned = path.strip('"\'')
            if not os.path.exists(cleaned):
                continue
            if os.path.isdir(cleaned):
                for root, _, files in os.walk(cleaned):
                    for f in files:
                        if f.lower().endswith(supported):
                            pdf_files.append(os.path.normpath(os.path.join(root, f)))
            elif os.path.isfile(cleaned) and cleaned.lower().endswith(supported):
                pdf_files.append(os.path.normpath(cleaned))

        if not pdf_files:
            self.dropzone.flash_error(tr("dropzone_no_files_error"))
            return

        new_items: List[TaskItem] = []
        existing_paths = {t.file_path for t in self.tasks}

        for p in pdf_files:
            p_norm = p.replace("\\", "/")
            if p_norm in existing_paths:
                continue

            existing_paths.add(p_norm)
            fname = os.path.basename(p)

            # Dimensiunea fișierului
            try:
                size_bytes = os.path.getsize(p)
                if size_bytes >= 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                elif size_bytes >= 1024:
                    size_str = f"{size_bytes / 1024:.0f} KB"
                else:
                    size_str = f"{size_bytes} B"
            except Exception:
                size_str = "—"

            # Numărul de pagini
            page_count = 0
            if pypdf and p.lower().endswith(".pdf"):
                try:
                    reader = pypdf.PdfReader(p)
                    page_count = len(reader.pages)
                except Exception:
                    page_count = 0

            # Titlu provizoriu din numele fișierului — orice sursă reală îl înlocuiește
            clean_title = _merge.filename_title(fname)

            item = TaskItem(
                id=str(uuid.uuid4()),
                file_name=fname,
                file_path=p_norm,
                file_size_str=size_str,
                page_count=page_count,
                layer_type="Se analizează...",
                language="—",
                pipeline_stage="În așteptare",
                zotero_status="În așteptare",
                metadata=BookMetadata(
                    title=clean_title,
                    language="",
                    raw_json=json.dumps({"title": clean_title, "file": fname}, ensure_ascii=False, indent=2)
                )
            )
            if seed:
                # Sursa 2: metadatele paginii web — suprascriu placeholder-ul, AI completează restul
                from worker.ai_adapter import ai_fields_to_metadata
                from zotero.item_types import type_label
                sf = ai_fields_to_metadata(seed)
                if seed.get("item_type"):
                    sf["doc_type"] = type_label(seed["item_type"])
                extra = sf.pop("extra", "")
                _merge.apply_source(item.metadata, sf, override=True, placeholder_title=clean_title)
                if extra:
                    _merge.extra_merge(item.metadata, extra)
            new_items.append(item)

        if new_items:
            self.tasks.extend(new_items)
            self.repo.save_all(new_items)
            log.info("Adăugate în coadă: %d fișier(e) | %s",
                     len(new_items), ", ".join(t.file_name for t in new_items[:5]))
            self.selected_task = new_items[-1]
            self._update_all_states()
            self.dropzone.flash_success(tr("dropzone_added_success", count=len(new_items)))
            self._run_analysis(new_items)
        else:
            self.dropzone.flash_error(tr("dropzone_all_exist_error"))

    # ------------------------------------------------------------------
    # Pipeline de fundal (worker/)
    # ------------------------------------------------------------------
    def _run_analysis(self, tasks: List[TaskItem]):
        import threading

        def run():
            from worker.extractor import extract_document, ExtractConfig, ExtractResult
            from worker.ai_adapter import analyze_text, AIConfig, build_cli_template
            from worker.xmp_injector import inject_metadata

            cfg = ExtractConfig(
                tesseract_cmd=self.db.get_setting("tesseract_cmd", "") or ""
            )
            ai_cfg = AIConfig(
                cli_template=build_cli_template(
                    self.db.get_setting("cli_preset", ""),
                    self.db.get_setting("cli_cmd", "agy"),
                ),
                enabled=self.db.get_setting("ai_enabled", "1") == "1",
            )

            from worker import merge
            from worker.ai_adapter import ai_fields_to_metadata
            from zotero.lookup import lookup_text_identifiers
            from zotero.item_types import type_label

            for task in tasks:
                if task not in self.tasks:
                    continue

                placeholder = merge.filename_title(task.file_name)
                text_to_analyze = getattr(task, "extracted_text", "")
                lang_hint = getattr(task, "language", "")
                embedded: dict = {}

                # Etapa 1: analiza stratului de text + extracție (+ metadatele din fișier)
                if not text_to_analyze:
                    self.after(0, lambda t=task: self._on_extraction_started(t))
                    try:
                        result = extract_document(task.file_path, cfg)
                    except Exception as e:
                        result = ExtractResult(
                            file_path=task.file_path, file_name=task.file_name,
                            ok=False, error=f"Eroare internă worker: {e}"
                        )
                    self.after(0, lambda t=task, r=result: self._on_extraction_done(t, r))
                    if not result.ok:
                        continue
                    text_to_analyze = result.text
                    lang_hint = result.language
                    embedded = result.embedded_metadata or {}
                else:
                    try:
                        from worker.extractor import read_embedded_metadata
                        embedded = read_embedded_metadata(task.file_path)
                    except Exception:
                        embedded = {}
                    if ai_cfg.enabled:
                        self.after(0, lambda t=task: self._on_ai_started(t))

                # Sursa 4 (încredere mică): metadatele deja încorporate în fișier — doar goluri
                if embedded:
                    merge.apply_source(task.metadata, embedded, override=False,
                                       placeholder_title=placeholder)

                # Sursa 1 (autoritativă): registre după DOI/ISBN din text sau din XMP
                lookup_hit = False
                try:
                    probe_text = text_to_analyze
                    for key in ("doi", "isbn"):
                        if embedded.get(key):
                            probe_text = f"{key.upper()}: {embedded[key]}\n" + probe_text
                    lf, _ = lookup_text_identifiers(probe_text)
                    if lf:
                        ids_only = lf.pop("_ids_only", False)
                        lf_meta = ai_fields_to_metadata(lf) if not ids_only else lf
                        if not ids_only and lf.get("item_type"):
                            lf_meta["doc_type"] = type_label(lf["item_type"])
                        extra = lf_meta.pop("extra", "") if isinstance(lf_meta, dict) else ""
                        applied = merge.apply_source(task.metadata, lf_meta, override=not ids_only,
                                                     placeholder_title=placeholder)
                        if extra:
                            merge.extra_merge(task.metadata, extra)
                        lookup_hit = applied > 0 and not ids_only
                        if applied:
                            self.after(0, lambda t=task: self._on_lookup_applied(t))
                except Exception as e:
                    log.warning("Eroare la căutarea identificatorilor: %s", e)

                # Sursa 3: AI completează ce lipsește (CZU, tiraj, rezumat, oraș, tip...)
                ai_failed_msg = ""
                if ai_cfg.enabled:
                    known = merge.known_facts(task.metadata, placeholder)
                    fields, err = analyze_text(text_to_analyze, ai_cfg,
                                               language_hint=lang_hint, known=known)
                    if fields:
                        task.metadata.raw_json = fields.get("raw_json", task.metadata.raw_json)
                        task.metadata.confidence = float(fields.get("confidence") or 0.5) \
                            if not lookup_hit else max(0.9, float(fields.get("confidence") or 0.9))
                        extra = fields.pop("extra", "")
                        # AI suprascrie doar ce NU a venit din registre
                        merge.apply_source(task.metadata, fields, override=not lookup_hit,
                                           placeholder_title=placeholder,
                                           skip=merge.known_facts(task.metadata, placeholder).keys()
                                           if lookup_hit else ())
                        if extra:
                            merge.extra_merge(task.metadata, extra)
                        self.after(0, lambda t=task: self._on_ai_applied(t))
                    else:
                        ai_failed_msg = err
                        log.warning("AI indisponibil | %s | %s", task.file_name, err)

                # Rezerve finale (titlu din fișier, limbă detectată, pagini)
                merge.finalize(task.metadata, file_name=task.file_name,
                               detected_language=lang_hint, page_count=task.page_count,
                               text=text_to_analyze)

                # Limba din metadatele finale (registre/AI) e autoritară față de euristică
                lang_final = merge.norm_lang(task.metadata.language)
                if lang_final:
                    task.language = lang_final

                # Fără nicio sursă reală de metadate -> eroare explicită
                if ai_failed_msg and not lookup_hit and not embedded.get("title"):
                    self.after(0, lambda t=task, e=ai_failed_msg: self._on_ai_failed(t, e))
                    continue
                if ai_failed_msg:
                    task.error = f"AI indisponibil ({ai_failed_msg[:80]}) — metadate din registre"

                # Etapa 3: injectarea XMP + Info Dict
                inj = inject_metadata(task.file_path, task.metadata)
                self.after(0, lambda t=task, r=inj: self._on_xmp_done(t, r))

        threading.Thread(target=run, daemon=True).start()

    def _on_ai_started(self, task: TaskItem):
        if task not in self.tasks:
            return
        task.pipeline_stage = "Analiză AI"
        task.error = ""
        self.repo.save(task)
        self.task_table.update_single_task(task)
        self._update_stats_only()

    def _on_extraction_started(self, task: TaskItem):
        if task not in self.tasks:
            return
        task.pipeline_stage = "Analiză strat"
        self.repo.save(task)
        self.task_table.update_single_task(task)
        self._update_stats_only()

    def _on_extraction_done(self, task: TaskItem, result):
        if task not in self.tasks:
            return
        if not result.ok:
            task.pipeline_stage = "Eroare"
            task.error = result.error
            log.error("Extragerea a eșuat | %s | %s", task.file_name, result.error)
            self.notifier.error(tr("toast_task_extract_failed"), task.file_name)
        else:
            task.layer_type = {
                "scan": "Scan (OCR)",
                "text": "Text",
            }.get(result.layer_type, "—")
            from worker.merge import norm_lang
            task.language = norm_lang(result.language) or "—"
            task.extracted_text = result.text
            if result.page_count:
                task.page_count = result.page_count
            task.pipeline_stage = "Analiză AI"
            task.error = ""
            log.info("Strat: %s | %s | %s, %d pagini, %d caractere",
                     task.file_name, task.layer_type, task.language,
                     result.page_count, len(result.text))
        self.repo.save(task)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)
        self._update_stats_only()

    def _on_lookup_applied(self, task: TaskItem):
        if task not in self.tasks:
            return
        log.info("Metadate din lookup aplicate | %s | '%s' DOI:%s ISBN:%s",
                 task.file_name, task.metadata.title,
                 task.metadata.doi, task.metadata.isbn)
        self.repo.save(task)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)

    def _on_ai_applied(self, task: TaskItem):
        if task not in self.tasks:
            return
        task.pipeline_stage = "Scriere XMP"
        log.info("Metadate AI aplicate | %s | '%s' (%s)",
                 task.file_name, task.metadata.title, task.metadata.doc_type)
        self.repo.save(task)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)
        self._update_stats_only()

    def _on_ai_failed(self, task: TaskItem, error: str):
        if task not in self.tasks:
            return
        task.pipeline_stage = "Eroare"
        task.error = error
        log.error("Etapa AI a eșuat | %s | %s", task.file_name, error)
        self.notifier.error(tr("toast_task_ai_failed"), task.file_name)
        self.repo.save(task)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)
        self._update_stats_only()

    def _on_xmp_done(self, task: TaskItem, result):
        if task not in self.tasks:
            return
        task.pipeline_stage = "Finalizat" if result.ok else "Eroare"
        if result.ok:
            task.error = ""
            log.info("XMP scris | %s", task.file_name)
            self.notifier.success(tr("toast_task_done"), task.file_name)
        else:
            task.error = result.error
            log.error("Scrierea XMP a eșuat | %s | %s", task.file_name, result.error)
            self.notifier.error(tr("toast_task_xmp_failed"), task.file_name)
        self.repo.save(task)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)
        self._update_stats_only()

    def _on_select_files(self):
        paths = filedialog.askopenfilenames(
            title=tr("dialog_select_files_title"),
            filetypes=[("Documente", "*.pdf *.docx"), ("Documente PDF", "*.pdf"),
                       ("Documente Word", "*.docx"), ("Toate fișierele", "*.*")]
        )
        if paths:
            self._process_incoming_paths(list(paths))

    def _on_select_folder(self):
        folder = filedialog.askdirectory(title=tr("dialog_select_folder_title"))
        if folder:
            self._process_incoming_paths([folder])

    def _open_settings(self):
        SettingsDialog(self, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        self.notifier.set_enabled(self.db.get_setting("toast", "1") == "1")
        self.zotero.base_url = self.db.get_setting("zotero_url", DEFAULT_URL).rstrip("/")
        self.title(tr("app_title"))
        if hasattr(self.header, "refresh_texts"):
            self.header.refresh_texts()
        if hasattr(self.dropzone, "refresh_texts"):
            self.dropzone.refresh_texts()
        if hasattr(self.search_bar, "refresh_texts"):
            self.search_bar.refresh_texts()
        if hasattr(self.task_table, "refresh_texts"):
            self.task_table.refresh_texts()
        if hasattr(self.inspector, "refresh_texts"):
            self.inspector.refresh_texts()
        if hasattr(self.status_bar, "refresh_texts"):
            self.status_bar.refresh_texts()
        self._refresh_ai_badge(force=True)
        self._update_all_states()
        log.info("Setări salvate și limba UI actualizată")

    def _check_zotero_status(self):
        import threading

        def ping():
            online = self.zotero.ping()
            queued = sum(1 for t in self.tasks if "offline" in t.zotero_status.lower() or "așteptare" in t.zotero_status.lower())
            self.after(0, lambda: self.header.set_zotero_status(online, queued))
        threading.Thread(target=ping, daemon=True).start()

    def _check_ai_status(self):
        self._open_settings()

    # ------------------------------------------------------------------
    # Monitorul de fundal Zotero: golirea cozii (Zero Data Loss)
    # ------------------------------------------------------------------
    def _start_zotero_monitor(self):
        try:
            interval = int(self.db.get_setting("zotero_poll_sec", "30"))
        except ValueError:
            interval = 30
        self.after(interval * 1000, self._zotero_tick)

    def _zotero_tick(self):
        import threading
        if self._zotero_busy:
            self._start_zotero_monitor()
            return
        self._zotero_busy = True

        def work():
            online = self.zotero.ping()
            queued = sum(1 for t in self.tasks if "offline" in t.zotero_status.lower() or "așteptare" in t.zotero_status.lower())

            def apply_status():
                self.header.set_zotero_status(online, queued)
                if online and queued:
                    def on_done():
                        self._zotero_busy = False
                        self._start_zotero_monitor()
                    self._flush_zotero_queue(on_done=on_done)
                else:
                    self._zotero_busy = False
                    self._start_zotero_monitor()
            self.after(0, apply_status)

        threading.Thread(target=work, daemon=True).start()

    def _flush_zotero_queue(self, on_done=None):
        import threading

        # Doar sarcinile cu pipeline finalizat — fișele nefinalizate nu au încă metadate reale
        queued_tasks = [t for t in self.tasks
                        if ("offline" in t.zotero_status.lower()
                            or "așteptare" in t.zotero_status.lower())
                        and any(k in t.pipeline_stage.lower()
                                for k in ("finalizat", "xmp"))]

        if not queued_tasks:
            if on_done:
                on_done()
            return

        prefer_recognize = self.db.get_setting("zotero_recognize", "1") == "1"

        def work():
            try:
                for task in queued_tasks:
                    ok, info = self.zotero.send_task(task, prefer_recognize=prefer_recognize)
                    self.after(0, lambda t=task, o=ok, m=info: self._on_zotero_sent(t, o, m))
            finally:
                if on_done:
                    self.after(0, on_done)

        threading.Thread(target=work, daemon=True).start()

    def _on_zotero_sent(self, task: TaskItem, ok: bool, info: str):
        if task not in self.tasks:
            return
        self.repo.update_zotero_status(task.id, "Sincronizat" if ok else "Eroare Zotero")
        task.zotero_status = "Sincronizat" if ok else "Eroare Zotero"
        if ok:
            log.info("Sincronizare Zotero | %s | %s", task.file_name, info)
            self.notifier.success(tr("toast_task_zotero_exported"), task.file_name)
        else:
            task.error = info
            log.error("Sincronizarea Zotero a eșuat | %s | %s", task.file_name, info)
            self.notifier.error(tr("toast_task_zotero_failed"), task.file_name)
        self.task_table.update_single_task(task)
        if self.selected_task and self.selected_task.id == task.id:
            self.inspector.set_task(task)
        self._update_stats_only()

    def _sync_offline_queue(self):
        if self._zotero_busy:
            return
        self._zotero_busy = True

        def on_done():
            self._zotero_busy = False
            self._start_zotero_monitor()

        self._flush_zotero_queue(on_done=on_done)

    def _resume_unfinished_tasks(self):
        """
        Relansează pipeline-ul pentru sarcinile întrerupte la închiderea anterioară
        (etapele 'În așteptare' / 'Analiză strat' / 'Analiză AI').
        Sarcinile cu extracted_text salvat omit re-extragerea.
        """
        unfinished = [
            t for t in self.tasks
            if any(k in t.pipeline_stage.lower() for k in ("așteptare", "analiz"))
            and t.file_path and os.path.isfile(t.file_path)
        ]
        if unfinished:
            log.info("Reluare pipeline pentru %d sarcină(i) nefinalizată(e)", len(unfinished))
            self._run_analysis(unfinished)

    def _load_or_seed_tasks(self) -> List[TaskItem]:
        tasks = self.repo.load_all()
        import sys
        if not tasks and not getattr(sys, "frozen", False):
            tasks = self._get_initial_mock_tasks()
            self.repo.save_all(tasks)
        return tasks

    def _get_initial_mock_tasks(self) -> List[TaskItem]:
        return [
            TaskItem(
                id="task-1",
                file_name="Attention_Is_All_You_Need_2017.pdf",
                file_path="C:/Users/joanse/Downloads/Attention_Is_All_You_Need_2017.pdf",
                file_size_str="2.4 MB",
                page_count=15,
                layer_type="Text",
                language="en",
                pipeline_stage="Finalizat",
                zotero_status="Sincronizat",
                metadata=BookMetadata(
                    title="Attention Is All You Need",
                    subtitle="",
                    authors="Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit",
                    publisher="NeurIPS",
                    year="2017",
                    city="Long Beach",
                    isbn="",
                    doi="10.48550/arXiv.1706.03762",
                    doc_type="Lucrare de conferință (conferencePaper)",
                    language="en",
                    confidence=0.99,
                    raw_json='{\n  "title": "Attention Is All You Need",\n  "authors": ["Ashish Vaswani", "Noam Shazeer"],\n  "year": "2017",\n  "type": "conferencePaper",\n  "language": "eng"\n}'
                )
            ),
            TaskItem(
                id="task-2",
                file_name="Deep_Residual_Learning_2015.pdf",
                file_path="C:/Users/joanse/Downloads/Deep_Residual_Learning_2015.pdf",
                file_size_str="3.8 MB",
                page_count=28,
                layer_type="Text",
                language="en",
                pipeline_stage="Finalizat",
                zotero_status="Zotero Offline (SQLite)",
                metadata=BookMetadata(
                    title="Deep Residual Learning for Image Recognition",
                    subtitle="",
                    authors="Kaiming He, Xiangyu Zhang, Shaoqing Ren, Jian Sun",
                    publisher="IEEE",
                    year="2016",
                    city="Las Vegas",
                    isbn="",
                    doi="10.1109/CVPR.2016.90",
                    doc_type="Lucrare de conferință (conferencePaper)",
                    language="en",
                    confidence=0.98,
                    raw_json='{\n  "title": "Deep Residual Learning for Image Recognition",\n  "authors": ["Kaiming He", "Xiangyu Zhang"],\n  "year": "2016",\n  "type": "conferencePaper",\n  "language": "eng"\n}'
                )
            ),
            TaskItem(
                id="task-3",
                file_name="Historical_Archive_Handbook_1998_Scan.pdf",
                file_path="C:/Users/joanse/Downloads/Historical_Archive_Handbook_1998_Scan.pdf",
                file_size_str="48.1 MB",
                page_count=312,
                layer_type="Scan (OCR)",
                language="en",
                pipeline_stage="Analiză AI",
                zotero_status="În așteptare",
                metadata=BookMetadata(
                    title="Historical Archive and Document Analysis",
                    subtitle="Methods and Perspectives in Modern Archival Science",
                    authors="S. A. Smith",
                    publisher="Academic Press",
                    year="1998",
                    city="New York",
                    isbn="0-12-345678-9",
                    doi="",
                    doc_type="Carte (book)",
                    language="en",
                    confidence=0.90,
                    raw_json='{\n  "title": "Historical Archive and Document Analysis",\n  "authors": ["S. A. Smith"],\n  "publisher": "Academic Press",\n  "year": "1998",\n  "isbn": "0-12-345678-9",\n  "type": "book",\n  "language": "eng"\n}'
                )
            )
        ]
