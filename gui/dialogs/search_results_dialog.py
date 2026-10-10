"""
Dialog de selectare a candidatului din rezultatele CrossRef/OpenLibrary.
"""

import customtkinter as ctk
from typing import List, Dict, Callable
from gui.theme import Theme
from gui.icons import setup_window_icon
from core.i18n import tr


class SearchResultsDialog(ctk.CTkToplevel):
    def __init__(self, master, results: List[Dict], on_pick: Callable[[Dict], None]):
        super().__init__(master)
        self.title(tr("search_results_window"))
        self.geometry("640x420")
        self.resizable(True, True)
        setup_window_icon(self)

        self.results = results
        self.on_pick = on_pick

        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text=tr("search_results_title", count=len(self.results)),
            font=Theme.font_body_bold(),
            text_color=Theme.TEXT_MAIN
        ).pack(anchor="w", padx=16, pady=(14, 8))


        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Theme.BG_PANEL,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Theme.BG_BORDER
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        for res in self.results:
            self._build_row(scroll, res)

    def _build_row(self, parent, res: Dict):
        card = ctk.CTkFrame(parent, fg_color=Theme.BG_HEADER, corner_radius=8,
                            border_width=1, border_color=Theme.BG_BORDER)
        card.pack(fill="x", pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        text_box = ctk.CTkFrame(inner, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True)

        authors = res.get("authors") or []
        authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        meta_line = " • ".join(filter(None, [
            authors_str,
            str(res.get("year") or ""),
            res.get("publisher") or res.get("library_catalog") or "",
            f"DOI: {res['doi']}" if res.get("doi") else "",
        ]))

        ctk.CTkLabel(
            text_box, text=res.get("title") or "(fără titlu)",
            font=Theme.font_caption_bold(), text_color=Theme.TEXT_MAIN,
            anchor="w", justify="left", wraplength=470
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_box, text=meta_line or "—",
            font=Theme.font_caption(), text_color=Theme.TEXT_MUTED, anchor="w"
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            inner, text="Selectează", width=80, height=28,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_caption_bold(),
            command=lambda r=res: self._pick(r)
        ).pack(side="right", padx=(10, 0))

    def _pick(self, res: Dict):
        self.on_pick(res)
        self.destroy()
