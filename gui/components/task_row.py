"""
Componenta rând de sarcină din coada de documente — optimizată pentru performanță ridicată
și actualizare in-place (fără recrearea canvas-urilor Tkinter).
"""

import customtkinter as ctk
from typing import Callable, Optional
from gui.theme import Theme
from gui.models import TaskItem
from core.i18n import tr


def localize_stage(stage_raw: str) -> str:
    s = (stage_raw or "").lower()
    if any(k in s for k in ("finalizat", "completed")):
        return tr("stage_completed")
    if any(k in s for k in ("xmp", "actualizat", "updated")):
        return tr("stage_xmp_updated")
    if any(k in s for k in ("eroare", "error", "eșec", "failed")):
        return tr("stage_error")
    if "ai" in s:
        return tr("stage_ai")
    if any(k in s for k in ("strat", "layer", "analiz")):
        return tr("stage_analyzing_layer")
    if any(k in s for k in ("așteptare", "pending", "coadă", "queue")):
        return tr("stage_pending")
    return stage_raw


def localize_layer(layer_raw: str) -> str:
    l = (layer_raw or "").lower()
    if "scan" in l:
        return tr("layer_scan")
    if "text" in l:
        return tr("layer_text")
    if any(k in l for k in ("analiz", "analyz")):
        return tr("layer_analyzing")
    if any(k in l for k in ("gol", "empty")):
        return tr("layer_empty")
    return layer_raw


def localize_zotero(status_raw: str) -> str:
    z = (status_raw or "").lower()
    if any(k in z for k in ("sincron", "synced")):
        return tr("zotero_synced")
    if any(k in z for k in ("offline", "așteptare", "queued")):
        return tr("zotero_queued")
    if any(k in z for k in ("eroare", "error")):
        return tr("zotero_error")
    return status_raw


class TaskRowComponent(ctk.CTkFrame):
    def __init__(
        self,
        master,
        task: TaskItem,
        is_selected: bool,
        on_select: Callable[[TaskItem], None],
        on_delete: Callable[[TaskItem], None]
    ):
        self._is_selected = is_selected
        bg = Theme.BG_PANEL_ALT if is_selected else Theme.BG_HEADER
        border_col = Theme.PRIMARY if is_selected else Theme.BG_BORDER

        super().__init__(
            master,
            height=60,
            corner_radius=8,
            fg_color=bg,
            border_width=1,
            border_color=border_col,
            cursor="hand2"
        )
        self.pack_propagate(False)

        self.task = task
        self.on_select = on_select
        self.on_delete = on_delete

        self._build_ui()
        self._bind_clicks()

    def _build_ui(self):
        self.grid_propagate(False)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Aranjare proporțională adaptivă a coloanelor
        self.grid_columnconfigure(0, weight=4, minsize=200)   # Document (titlu + dimensiune)
        self.grid_columnconfigure(1, weight=0, minsize=80)    # Strat
        self.grid_columnconfigure(2, weight=0, minsize=40)    # Limbă
        self.grid_columnconfigure(3, weight=1, minsize=110)   # Etapă pipeline
        self.grid_columnconfigure(4, weight=1, minsize=120)   # Stare Zotero
        self.grid_columnconfigure(5, weight=0, minsize=32)    # Acțiuni (✕)

        # 1. Coloana: titlul documentului și info
        self.title_lbl = ctk.CTkLabel(
            self,
            text=self._format_title(self.task.file_name, 320),
            font=Theme.font_body_bold(),
            text_color=Theme.TEXT_MAIN,
            height=20,
            anchor="w"
        )
        self.title_lbl.grid(row=0, column=0, sticky="w", padx=(16, 6), pady=(8, 1))

        page_str = tr("unit_pages", count=self.task.page_count) if self.task.page_count != 1 else tr("unit_page_single")
        self.sub_lbl = ctk.CTkLabel(
            self,
            text=f"{self.task.file_size_str} • {page_str}",
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED,
            height=16,
            anchor="w"
        )
        self.sub_lbl.grid(row=1, column=0, sticky="w", padx=(16, 6), pady=(1, 8))

        # 2. Coloana: stratul documentului
        is_scan = "scan" in self.task.layer_type.lower()
        layer_color = Theme.STATUS_INFO_SCAN if is_scan else Theme.STATUS_INFO_TEXT
        self.layer_badge = ctk.CTkLabel(
            self,
            text=localize_layer(self.task.layer_type),
            width=76,
            height=24,
            fg_color=layer_color,
            text_color="#FFFFFF",
            corner_radius=6,
            font=Theme.font_caption_bold()
        )
        self.layer_badge.grid(row=0, column=1, rowspan=2, sticky="w", padx=2)

        # 3. Coloana: limbă
        self.lang_lbl = ctk.CTkLabel(
            self,
            text=self.task.language,
            width=36,
            font=Theme.font_caption_bold(),
            text_color=Theme.TEXT_MUTED
        )
        self.lang_lbl.grid(row=0, column=2, rowspan=2, sticky="w", padx=2)

        # 4. Coloana: etapa pipeline
        stage_color = self._get_stage_color(self.task.pipeline_stage)
        self.stage_lbl = ctk.CTkLabel(
            self,
            text=f"● {localize_stage(self.task.pipeline_stage)}",
            anchor="w",
            font=Theme.font_caption_bold(),
            text_color=stage_color
        )
        self.stage_lbl.grid(row=0, column=3, rowspan=2, sticky="w", padx=4)

        # 5. Coloana: stare Zotero
        zotero_color = self._get_zotero_color(self.task.zotero_status)
        self.zotero_lbl = ctk.CTkLabel(
            self,
            text=localize_zotero(self.task.zotero_status),
            anchor="w",
            font=Theme.font_caption(),
            text_color=zotero_color
        )
        self.zotero_lbl.grid(row=0, column=4, rowspan=2, sticky="w", padx=4)

        # 6. Butonul de ștergere (✕)
        self.btn_del = ctk.CTkButton(
            self,
            text="✕",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=Theme.STATUS_DANGER_BG,
            text_color=Theme.TEXT_MUTED,
            font=Theme.font_caption_bold(),
            command=lambda: self.on_delete(self.task)
        )
        self.btn_del.grid(row=0, column=5, rowspan=2, sticky="e", padx=(2, 12))

    def _bind_clicks(self):
        """Leagă evenimentul de selecție doar pe elementele relevante, fără recursivitate profundă."""
        cb = lambda e: self.on_select(self.task)
        self.bind("<Button-1>", cb)
        self.title_lbl.bind("<Button-1>", cb)
        self.sub_lbl.bind("<Button-1>", cb)
        self.layer_badge.bind("<Button-1>", cb)
        self.lang_lbl.bind("<Button-1>", cb)
        self.stage_lbl.bind("<Button-1>", cb)
        self.zotero_lbl.bind("<Button-1>", cb)

    def set_selected(self, is_selected: bool):
        """Actualizează selecția vizuală instant (fără recrearea widget-ului)."""
        if self._is_selected == is_selected:
            return
        self._is_selected = is_selected
        bg = Theme.BG_PANEL_ALT if is_selected else Theme.BG_HEADER
        border_col = Theme.PRIMARY if is_selected else Theme.BG_BORDER
        self.configure(fg_color=bg, border_color=border_col)

    def update_task(self, task: TaskItem, is_selected: Optional[bool] = None):
        """Actualizează datele rândului pe loc (in-place) fără a distruge widget-urile."""
        self.task = task
        if is_selected is not None:
            self.set_selected(is_selected)

        # 1. Titlu & Pagini
        self.title_lbl.configure(text=self._format_title(task.file_name, 320))
        page_str = tr("unit_pages", count=task.page_count) if task.page_count != 1 else tr("unit_page_single")
        self.sub_lbl.configure(text=f"{task.file_size_str} • {page_str}")

        # 2. Strat
        is_scan = "scan" in task.layer_type.lower()
        layer_color = Theme.STATUS_INFO_SCAN if is_scan else Theme.STATUS_INFO_TEXT
        self.layer_badge.configure(
            text=localize_layer(task.layer_type),
            fg_color=layer_color
        )

        # 3. Limbă
        self.lang_lbl.configure(text=task.language)

        # 4. Etapă
        stage_color = self._get_stage_color(task.pipeline_stage)
        self.stage_lbl.configure(
            text=f"● {localize_stage(task.pipeline_stage)}",
            text_color=stage_color
        )

        # 5. Zotero
        zotero_color = self._get_zotero_color(task.zotero_status)
        self.zotero_lbl.configure(
            text=localize_zotero(task.zotero_status),
            text_color=zotero_color
        )

    @staticmethod
    def _get_stage_color(stage: str):
        s = stage.lower()
        if any(k in s for k in ("finalizat", "completed", "xmp")):
            return Theme.STATUS_SUCCESS
        if any(k in s for k in ("eroare", "error", "eșec", "failed")):
            return Theme.STATUS_DANGER
        if any(k in s for k in ("așteptare", "pending", "coadă", "queue")):
            return Theme.TEXT_MUTED
        return Theme.PRIMARY

    @staticmethod
    def _get_zotero_color(status: str):
        z = status.lower()
        if any(k in z for k in ("sincron", "synced")):
            return Theme.STATUS_SUCCESS
        if any(k in z for k in ("așteptare", "pending")):
            return Theme.TEXT_MUTED
        if any(k in z for k in ("eroare", "error")):
            return Theme.STATUS_DANGER
        return Theme.STATUS_WARNING

    @staticmethod
    def _format_title(filename: str, width_px: int) -> str:
        if width_px < 60:
            width_px = 300
        max_chars = max(20, int(width_px / 7.6))
        if len(filename) <= max_chars:
            return filename
        ext_idx = filename.rfind(".")
        if ext_idx != -1 and len(filename) - ext_idx <= 6:
            ext = filename[ext_idx:]
            base = filename[:ext_idx]
            avail = max_chars - len(ext) - 3
            if avail > 6:
                return base[:avail] + "..." + ext
        return filename[:max_chars - 3] + "..."
