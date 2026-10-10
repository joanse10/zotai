"""
Componenta bară de stare a aplicației Zotai.
"""

import customtkinter as ctk
from typing import Callable
from gui.theme import Theme
from core.i18n import tr


class StatusBarComponent(ctk.CTkFrame):
    def __init__(self, master, on_sync_queue: Callable[[], None]):
        super().__init__(master, height=44, corner_radius=0, fg_color=Theme.BG_WINDOW)
        self.pack_propagate(False)

        self.on_sync_queue = on_sync_queue
        self._last_stats = (0, 0, 0, 0)
        self._build_ui()

    def _build_ui(self):
        # 1. Sumar în stânga
        self.lbl_stats = ctk.CTkLabel(
            self,
            text=tr("status_stats", total=0, synced=0, queued=0, processing=0),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED
        )
        self.lbl_stats.pack(side="left", padx=20, pady=10)

        # 2. Butonul de sincronizare a cozii în dreapta
        self.btn_sync_queue = ctk.CTkButton(
            self,
            text=tr("btn_sync_queue", count=0),
            height=28,
            fg_color=Theme.STATUS_SUCCESS_BG,
            hover_color=Theme.STATUS_SUCCESS_HOVER,
            border_width=1,
            border_color=Theme.STATUS_SUCCESS,
            text_color=Theme.STATUS_SUCCESS_TEXT,
            font=Theme.font_caption_bold(),
            command=self.on_sync_queue
        )
        self.btn_sync_queue.pack(side="right", padx=20, pady=8)

    def refresh_texts(self):
        self.update_stats(*self._last_stats)

    def update_stats(self, total: int, synced: int, queued: int, processing: int):
        self._last_stats = (total, synced, queued, processing)
        self.lbl_stats.configure(
            text=tr("status_stats", total=total, synced=synced, queued=queued, processing=processing)
        )
        self.btn_sync_queue.configure(
            text=tr("btn_sync_queue", count=queued)
        )
        if queued > 0:
            self.btn_sync_queue.configure(
                fg_color=Theme.STATUS_WARNING_BG,
                hover_color=Theme.STATUS_WARNING_HOVER,
                border_color=Theme.STATUS_WARNING,
                text_color=Theme.STATUS_WARNING_TEXT
            )
        else:
            self.btn_sync_queue.configure(
                fg_color=Theme.STATUS_SUCCESS_BG,
                hover_color=Theme.STATUS_SUCCESS_HOVER,
                border_color=Theme.STATUS_SUCCESS,
                text_color=Theme.STATUS_SUCCESS_TEXT
            )

