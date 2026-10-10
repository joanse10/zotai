"""
Componenta de antet (header) a aplicației Zotai.
"""

import customtkinter as ctk
from typing import Callable
from gui.theme import Theme
from gui.icons import get_app_icon_image
from core.i18n import tr


class HeaderComponent(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_open_settings: Callable[[], None],
        on_check_zotero: Callable[[], None],
        on_check_ai: Callable[[], None]
    ):
        super().__init__(master, height=64, corner_radius=0, fg_color=Theme.BG_HEADER)
        self.pack_propagate(False)

        self.on_open_settings = on_open_settings
        self.on_check_zotero = on_check_zotero
        self.on_check_ai = on_check_ai
        self._zotero_state = (False, 0)
        self._ai_state = ("agy", False)

        self._build_ui()

    def _build_ui(self):
        # 1. Secțiunea din stânga: logo și denumirea
        left_box = ctk.CTkFrame(self, fg_color="transparent")
        left_box.pack(side="left", padx=(20, 16), pady=12)

        icon_img = get_app_icon_image(size=26)
        if icon_img:
            logo_icon = ctk.CTkLabel(
                left_box,
                text="",
                image=icon_img
            )
            logo_icon.pack(side="left", padx=(0, 8))

        logo_title = ctk.CTkLabel(
            left_box,
            text="Zotai",
            font=Theme.font_title(),
            text_color=Theme.PRIMARY
        )
        logo_title.pack(side="left", padx=(0, 8))

        version_badge = ctk.CTkLabel(
            left_box,
            text="v1.1",
            fg_color=Theme.PRIMARY_BG,
            text_color=Theme.PRIMARY_TEXT,
            corner_radius=4,
            font=Theme.font_caption_bold(),
            padx=6,
            pady=1
        )
        version_badge.pack(side="left", padx=(0, 12))

        separator = ctk.CTkFrame(left_box, width=1, height=22, fg_color=Theme.BG_BORDER)
        separator.pack(side="left", padx=8)

        self.subtitle = ctk.CTkLabel(
            left_box,
            text=tr("app_subtitle"),
            font=Theme.font_subtitle(),
            text_color=Theme.TEXT_MUTED
        )
        self.subtitle.pack(side="left", padx=6)

        # 2. Secțiunea din dreapta: butoane de stare și Setări
        right_box = ctk.CTkFrame(self, fg_color="transparent")
        right_box.pack(side="right", padx=(16, 20), pady=12)

        # Butonul Setări
        self.btn_settings = ctk.CTkButton(
            right_box,
            text=tr("btn_settings"),
            width=110,
            height=34,
            fg_color=Theme.BG_PANEL,
            hover_color=Theme.BG_PANEL_ALT,
            text_color=Theme.TEXT_MAIN,
            border_width=1,
            border_color=Theme.BG_BORDER,
            font=Theme.font_body_bold(),
            command=self.on_open_settings
        )
        self.btn_settings.pack(side="right", padx=(10, 0))

        # Butonul de stare AI
        self.ai_status_btn = ctk.CTkButton(
            right_box,
            text=tr("ai_active", cli="agy"),
            width=140,
            height=34,
            fg_color=Theme.PRIMARY_BG,
            hover_color=Theme.PRIMARY_BG_HOVER,
            text_color=Theme.PRIMARY_TEXT,
            border_width=1,
            border_color=Theme.PRIMARY,
            font=Theme.font_caption_bold(),
            command=self.on_check_ai
        )
        self.ai_status_btn.pack(side="right", padx=6)

        # Butonul de stare Zotero
        self.zotero_status_btn = ctk.CTkButton(
            right_box,
            text=tr("zotero_online", port="23119"),
            width=180,
            height=34,
            fg_color=Theme.STATUS_SUCCESS_BG,
            hover_color=Theme.STATUS_SUCCESS_HOVER,
            text_color=Theme.STATUS_SUCCESS_TEXT,
            border_width=1,
            border_color=Theme.STATUS_SUCCESS,
            font=Theme.font_caption_bold(),
            command=self.on_check_zotero
        )
        self.zotero_status_btn.pack(side="right", padx=6)

    def refresh_texts(self):
        self.subtitle.configure(text=tr("app_subtitle"))
        self.btn_settings.configure(text=tr("btn_settings"))
        self.set_zotero_status(*self._zotero_state)
        self.set_ai_status(self._ai_state[0], self._ai_state[1])

    def set_zotero_status(self, is_online: bool, pending_count: int = 0):
        self._zotero_state = (is_online, pending_count)
        if is_online:
            self.zotero_status_btn.configure(
                text=tr("zotero_online", port="23119"),
                fg_color=Theme.STATUS_SUCCESS_BG,
                hover_color=Theme.STATUS_SUCCESS_HOVER,
                text_color=Theme.STATUS_SUCCESS_TEXT,
                border_color=Theme.STATUS_SUCCESS
            )
        else:
            self.zotero_status_btn.configure(
                text=tr("zotero_offline", count=pending_count),
                fg_color=Theme.STATUS_WARNING_BG,
                hover_color=Theme.STATUS_WARNING_HOVER,
                text_color=Theme.STATUS_WARNING_TEXT,
                border_color=Theme.STATUS_WARNING
            )

    def set_ai_status(self, text_or_cli: str = "agy", is_active: bool = True):
        self._ai_state = (text_or_cli, is_active)
        cli_name = text_or_cli if ("(" not in text_or_cli and "●" not in text_or_cli) else "agy"
        display_text = tr("ai_active", cli=cli_name) if is_active else tr("ai_inactive")
        bg = Theme.STATUS_SUCCESS_BG if is_active else Theme.STATUS_WARNING_BG
        hover = Theme.STATUS_SUCCESS_HOVER if is_active else Theme.STATUS_WARNING_HOVER
        text_col = Theme.STATUS_SUCCESS_TEXT if is_active else Theme.STATUS_WARNING_TEXT
        border_col = Theme.STATUS_SUCCESS if is_active else Theme.STATUS_WARNING
        self.ai_status_btn.configure(
            text=display_text,
            fg_color=bg,
            hover_color=hover,
            text_color=text_col,
            border_color=border_col
        )

