"""
Componenta de plasare și selectare a fișierelor (dropzone) pentru Zotai.
"""

import customtkinter as ctk
from typing import Callable
from gui.theme import Theme
from gui.icons import get_app_icon_image
from core.i18n import tr


class DropzoneComponent(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_select_files: Callable[[], None],
        on_select_folder: Callable[[], None]
    ):
        super().__init__(
            master,
            height=94,
            corner_radius=10,
            fg_color=Theme.BG_PANEL,
            border_width=1,
            border_color=Theme.BG_BORDER
        )
        self.pack_propagate(False)

        self.on_select_files = on_select_files
        self.on_select_folder = on_select_folder

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=18, pady=12)

        # Insigna cu iconița aplicației în stânga
        app_icon = get_app_icon_image(size=40)
        if app_icon:
            icon_badge = ctk.CTkLabel(
                container,
                text="",
                image=app_icon
            )
            icon_badge.pack(side="left", padx=(0, 14))

        # Text descriptiv
        info_box = ctk.CTkFrame(container, fg_color="transparent")
        info_box.pack(side="left", fill="y", expand=True)

        self.title_label = ctk.CTkLabel(
            info_box,
            text=tr("dropzone_title"),
            font=Theme.font_body_bold(),
            text_color=Theme.TEXT_MAIN,
            anchor="w"
        )
        self.title_label.pack(anchor="w", pady=(2, 2))

        self.desc_label = ctk.CTkLabel(
            info_box,
            text=tr("dropzone_desc"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED,
            anchor="w"
        )
        self.desc_label.pack(anchor="w")

        # Butoane de acțiune în dreapta
        actions_box = ctk.CTkFrame(container, fg_color="transparent")
        actions_box.pack(side="right", padx=(12, 0))

        self.btn_files = ctk.CTkButton(
            actions_box,
            text=tr("dropzone_btn_files"),
            width=130,
            height=36,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_body_bold(),
            command=self.on_select_files
        )
        self.btn_files.pack(side="left", padx=4)

        self.btn_folder = ctk.CTkButton(
            actions_box,
            text=tr("dropzone_btn_folder"),
            width=80,
            height=36,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.BG_BORDER,
            font=Theme.font_body(),
            text_color=Theme.TEXT_MAIN,
            command=self.on_select_folder
        )
        self.btn_folder.pack(side="left", padx=4)

    def refresh_texts(self):
        self.title_label.configure(text=tr("dropzone_title"))
        self.desc_label.configure(text=tr("dropzone_desc"))
        self.btn_files.configure(text=tr("dropzone_btn_files"))
        self.btn_folder.configure(text=tr("dropzone_btn_folder"))

    def flash_success(self, message: str):
        """Animație temporară de notificare de succes."""
        self.title_label.configure(
            text=f"✅ {message}",
            text_color=Theme.STATUS_SUCCESS_TEXT
        )
        self.configure(border_color=Theme.STATUS_SUCCESS, border_width=2)

        def restore():
            try:
                self.title_label.configure(
                    text=tr("dropzone_title"),
                    text_color=Theme.TEXT_MAIN
                )
                self.configure(border_color=Theme.BG_BORDER, border_width=1)
            except Exception:
                pass

        self.after(2400, restore)

    def flash_error(self, message: str):
        """Animație temporară de notificare de avertizare/eroare."""
        self.title_label.configure(
            text=f"⚠️ {message}",
            text_color=Theme.STATUS_WARNING_TEXT
        )
        self.configure(border_color=Theme.STATUS_WARNING, border_width=2)

        def restore():
            try:
                self.title_label.configure(
                    text=tr("dropzone_title"),
                    text_color=Theme.TEXT_MAIN
                )
                self.configure(border_color=Theme.BG_BORDER, border_width=1)
            except Exception:
                pass

        self.after(2400, restore)

