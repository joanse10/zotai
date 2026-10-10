"""
Bara de căutare online a metadatelor bibliografice:
ISBN / DOI / link PDF / titlu -> CrossRef, OpenLibrary.
"""

import customtkinter as ctk
from typing import Callable
from gui.theme import Theme
from core.i18n import tr


class SearchBarComponent(ctk.CTkFrame):
    def __init__(self, master, on_search: Callable[[str], None]):
        super().__init__(
            master,
            height=54,
            corner_radius=10,
            fg_color=Theme.BG_PANEL,
            border_width=1,
            border_color=Theme.BG_BORDER
        )
        self.pack_propagate(False)
        self.on_search = on_search
        self._busy = False
        self._build_ui()

    def _build_ui(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=11)

        self.entry = ctk.CTkEntry(
            inner,
            placeholder_text=tr("search_placeholder"),
            font=Theme.font_caption(),
            height=30,
            border_color=Theme.BG_BORDER,
            fg_color=Theme.BG_INPUT,
            text_color=Theme.TEXT_MAIN
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._on_enter)

        self.btn = ctk.CTkButton(
            inner,
            text=tr("search_btn"),
            width=90,
            height=30,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_caption_bold(),
            command=self._fire
        )
        self.btn.pack(side="right")

    def _on_enter(self, _event):
        self._fire()

    def _fire(self):
        q = self.entry.get().strip()
        if q:
            self.on_search(q)

    def set_busy(self, busy: bool):
        self._busy = busy
        self.btn.configure(
            state="disabled" if busy else "normal",
            text=tr("search_busy") if busy else tr("search_btn")
        )

    def refresh_texts(self):
        self.entry.configure(placeholder_text=tr("search_placeholder"))
        self.btn.configure(text=tr("search_busy") if self._busy else tr("search_btn"))

    def clear(self):
        self.entry.delete(0, "end")

