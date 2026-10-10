"""
Dialogul de gestionare a pachetelor de limbi Tesseract (tessdata) pentru Zotai.
"""

import os
import threading
import customtkinter as ctk
from typing import Dict, List

from gui.theme import Theme
from gui.icons import setup_window_icon, get_app_icon_image
from worker.lang_manager import (
    LANGUAGES, default_tessdata_dir, installed_languages,
    download_language, remove_language,
)
from core.i18n import tr


class LanguagesDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title(tr("langs_title"))
        self.geometry("560x600")
        self.minsize(500, 480)
        self.configure(fg_color=Theme.BG_WINDOW)
        setup_window_icon(self)
        self.grab_set()

        self.tessdata_dir = default_tessdata_dir()
        self.installed: Dict[str, int] = installed_languages(self.tessdata_dir)
        self._checkboxes: Dict[str, ctk.CTkCheckBox] = {}
        self._status_labels: Dict[str, ctk.CTkLabel] = {}
        self._busy = False

        self._build_ui()

    def _build_ui(self):
        # Catalog de căutare
        search_bar = ctk.CTkFrame(self, fg_color="transparent")
        search_bar.pack(fill="x", padx=16, pady=(14, 6))
        self.search_entry = ctk.CTkEntry(
            search_bar, placeholder_text=tr("search_lang_placeholder"),
            height=30, border_width=1, fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER, text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption()
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", lambda e: self._rebuild_list())

        # Introducerea unui cod de limbă personalizat
        custom_bar = ctk.CTkFrame(self, fg_color="transparent")
        custom_bar.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(custom_bar, text=tr("lbl_custom_code"), font=Theme.font_caption(),
                     text_color=Theme.TEXT_MUTED).pack(side="left")
        self.custom_entry = ctk.CTkEntry(
            custom_bar, width=110, height=28, placeholder_text="ex. deu",
            border_width=1, fg_color=Theme.BG_INPUT, border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN, font=Theme.font_mono()
        )
        self.custom_entry.pack(side="left", padx=(6, 6))
        ctk.CTkButton(
            custom_bar, text=tr("btn_add_custom"), width=90, height=28,
            fg_color=Theme.BG_PANEL_ALT, hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1, border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN, font=Theme.font_caption_bold(),
            command=self._add_custom_code
        ).pack(side="left")

        ctk.CTkLabel(custom_bar, text=f"tessdata: {self.tessdata_dir}",
                     font=Theme.font_caption(), text_color=Theme.TEXT_DARK
                     ).pack(side="right")

        # Lista derulantă de limbi
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=Theme.BG_PANEL,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Theme.BG_BORDER,
            scrollbar_button_hover_color=Theme.TEXT_MUTED
        )
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._rebuild_list()

        # Progres și stare
        self.progress = ctk.CTkProgressBar(self, progress_color=Theme.PRIMARY)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 4))
        self.status_lbl = ctk.CTkLabel(
            self, text=tr("langs_select_hint"),
            font=Theme.font_caption(), text_color=Theme.TEXT_MUTED
        )
        self.status_lbl.pack(anchor="w", padx=16)

        # Butoanele de jos
        bottom = ctk.CTkFrame(self, height=52, fg_color=Theme.BG_HEADER, corner_radius=0)
        bottom.pack(fill="x", side="bottom")

        self.btn_download = ctk.CTkButton(
            bottom, text=tr("btn_download_selected"), width=170, height=34,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_body_bold(), command=self._download_selected
        )
        self.btn_download.pack(side="right", padx=(8, 16), pady=9)

        self.btn_remove = ctk.CTkButton(
            bottom, text=tr("btn_remove_selected"), width=150, height=34,
            fg_color=Theme.STATUS_DANGER_BG, hover_color=Theme.STATUS_DANGER_HOVER,
            border_width=1, border_color=Theme.STATUS_DANGER,
            text_color=Theme.STATUS_DANGER_TEXT,
            font=Theme.font_caption_bold(), command=self._remove_selected
        )
        self.btn_remove.pack(side="right", padx=8, pady=9)

        ctk.CTkButton(
            bottom, text=tr("btn_close"), width=90, height=34,
            fg_color=Theme.BG_PANEL_ALT, hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1, border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN, font=Theme.font_body(),
            command=self.destroy
        ).pack(side="left", padx=16, pady=9)

    def _rebuild_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._checkboxes.clear()
        self._status_labels.clear()

        query = self.search_entry.get().strip().lower()
        for code, name in sorted(LANGUAGES.items(), key=lambda kv: kv[1]):
            if query and query not in code.lower() and query not in name.lower():
                continue
            self._build_row(code, name)

    def _build_row(self, code: str, name: str):
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent", height=30)
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        cb = ctk.CTkCheckBox(
            row, text=f"{name}", font=Theme.font_body(),
            text_color=Theme.TEXT_MAIN, checkbox_width=18, checkbox_height=18,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_HOVER,
            border_color=Theme.BG_BORDER_LIGHT
        )
        cb.pack(side="left", padx=(4, 8), pady=4)
        self._checkboxes[code] = cb

        ctk.CTkLabel(row, text=code, font=Theme.font_mono(),
                     text_color=Theme.TEXT_DARK, width=90, anchor="w"
                     ).pack(side="left", padx=4)

        if code in self.installed:
            size_mb = f"{self.installed[code] / 1024 / 1024:.1f}"
            status_text = tr("status_installed_size", size=size_mb)
            color = Theme.STATUS_SUCCESS_TEXT
        else:
            status_text = "—"
            color = Theme.TEXT_DARK
        lbl = ctk.CTkLabel(row, text=status_text, font=Theme.font_caption(),
                           text_color=color, anchor="e")
        lbl.pack(side="right", padx=8)
        self._status_labels[code] = lbl

    def _add_custom_code(self):
        code = self.custom_entry.get().strip()
        if not code:
            return
        if code in self._checkboxes:
            self.status_lbl.configure(text=tr("lang_code_exists", code=code), text_color=Theme.TEXT_MUTED)
            return
        self._build_row(code, tr("lang_custom_label", code=code))
        self.custom_entry.delete(0, "end")
        self.status_lbl.configure(text=tr("lang_code_added", code=code),
                                  text_color=Theme.TEXT_MUTED)

    def _selected_codes(self) -> List[str]:
        return [code for code, cb in self._checkboxes.items() if cb.get() == 1]

    def _download_selected(self):
        if self._busy:
            return
        codes = [c for c in self._selected_codes() if c not in self.installed]
        if not codes:
            self.status_lbl.configure(text=tr("lang_none_new_selected"), text_color=Theme.TEXT_MUTED)
            return

        self._busy = True
        self.btn_download.configure(state="disabled")
        self.btn_remove.configure(state="disabled")

        def worker_thread():
            for i, code in enumerate(codes):
                try:
                    self.after(0, lambda c=code: self.status_lbl.configure(
                        text=tr("lang_downloading_code", code=c), text_color=Theme.TEXT_MUTED))
                    download_language(
                        code, self.tessdata_dir,
                        progress=lambda d, t, idx=i: self.after(
                            0, lambda dd=d, tt=t, n=idx: self._on_progress(n, len(codes), dd, tt))
                    )
                    path = os.path.join(self.tessdata_dir, f"{code}.traineddata")
                    self.installed[code] = os.path.getsize(path)
                    size_mb = f"{self.installed[code] / 1024 / 1024:.1f}"
                    self.after(0, lambda c=code, sm=size_mb: self._status_labels[c].configure(
                        text=tr("status_installed_size", size=sm),
                        text_color=Theme.STATUS_SUCCESS_TEXT))
                except Exception as e:
                    self.after(0, lambda c=code, err=e: self._status_labels[c].configure(
                        text=tr("lang_download_error", err=err), text_color=Theme.STATUS_DANGER_TEXT))
            self.after(0, self._on_batch_done)

        threading.Thread(target=worker_thread, daemon=True).start()

    def _remove_selected(self):
        if self._busy:
            return
        codes = [c for c in self._selected_codes() if c in self.installed]
        if not codes:
            self.status_lbl.configure(text=tr("lang_none_installed_selected"), text_color=Theme.TEXT_MUTED)
            return
        for code in codes:
            if remove_language(code, self.tessdata_dir):
                self.installed.pop(code, None)
                self._status_labels[code].configure(text="—", text_color=Theme.TEXT_DARK)
                self._checkboxes[code].deselect()
        self.status_lbl.configure(text=tr("lang_packages_removed", count=len(codes)), text_color=Theme.TEXT_MUTED)

    def _on_progress(self, index: int, total: int, done: int, total_bytes: int):
        frac = (index + (done / total_bytes if total_bytes else 0)) / total
        self.progress.set(min(frac, 1.0))

    def _on_batch_done(self):
        self._busy = False
        self.progress.set(0)
        self.btn_download.configure(state="normal")
        self.btn_remove.configure(state="normal")
        installed_count = len(self.installed)
        self.status_lbl.configure(
            text=tr("lang_batch_done", count=installed_count),
            text_color=Theme.STATUS_SUCCESS_TEXT
        )
