"""
Dialog modal de setări pentru aplicația Zotai.
"""

import os
import shutil
import subprocess
import threading
from typing import Callable
import customtkinter as ctk
from gui.theme import Theme, ThemedSegmentedButton
from gui.icons import setup_window_icon
from gui.dialogs.languages_dialog import LanguagesDialog
from worker.lang_manager import installed_languages, default_tessdata_dir
from db import ZotaiDB
from zotero.connector import ZoteroConnector, DEFAULT_URL
from core.i18n import tr, get_available_languages, get_language, set_language


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, on_save: Callable[[], None] = None):
        super().__init__(master)

        self.title(tr("settings_title"))
        self.geometry("580x600")
        self.minsize(540, 520)
        self.configure(fg_color=Theme.BG_WINDOW)
        setup_window_icon(self)
        self.grab_set()

        self.on_save = on_save
        self.db = ZotaiDB()
        self._avail_langs = get_available_languages()

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=Theme.BG_PANEL,
            segmented_button_fg_color=Theme.BG_INPUT,
            segmented_button_selected_color=Theme.PRIMARY,
            segmented_button_selected_hover_color=Theme.PRIMARY_HOVER
        )
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(14, 12))

        self.tab_ai = self.tabview.add(tr("tab_ai_engine"))
        self.tab_zotero = self.tabview.add(tr("tab_zotero_conn"))
        self.tab_system = self.tabview.add(tr("tab_system_int"))
        self.tab_langs = self.tabview.add(tr("tab_ocr_langs"))

        self._build_ai_tab()
        self._build_zotero_tab()
        self._build_system_tab()
        self._build_langs_tab()

        # Bara de acțiuni de jos
        bottom_bar = ctk.CTkFrame(self, height=52, fg_color=Theme.BG_HEADER, corner_radius=0)
        bottom_bar.pack(fill="x", side="bottom")

        btn_save = ctk.CTkButton(
            bottom_bar,
            text=tr("btn_save_settings"),
            width=160,
            height=34,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_body_bold(),
            command=self._on_save_clicked
        )
        btn_save.pack(side="right", padx=16, pady=9)

        btn_cancel = ctk.CTkButton(
            bottom_bar,
            text=tr("btn_close"),
            width=90,
            height=34,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.BG_BORDER,
            font=Theme.font_body(),
            text_color=Theme.TEXT_MAIN,
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(0, 8), pady=9)

    def _build_ai_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_ai, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkLabel(container, text=tr("lbl_ai_method"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(4, 4))

        self.ai_mode_selector = ThemedSegmentedButton(
            container,
            values=[tr("ai_mode_cli"), tr("ai_mode_api")],
            height=30,
            border_width=1,
            fg_color=Theme.BG_PANEL_ALT,
            unselected_color=Theme.BG_PANEL_ALT,
            unselected_hover_color=Theme.BG_BORDER,
            selected_color=Theme.PRIMARY,
            selected_hover_color=Theme.PRIMARY_HOVER,
            command=self._on_ai_mode_changed
        )
        self.ai_mode_selector.set(tr("ai_mode_cli"))
        self.ai_mode_selector.pack(fill="x", pady=(0, 12))

        # Secțiunea CLI
        self.frame_cli = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)
        self.frame_cli.pack(fill="x", pady=6)

        cli_inner = ctk.CTkFrame(self.frame_cli, fg_color="transparent")
        cli_inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(cli_inner, text=tr("lbl_cli_preset"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.cli_preset = ctk.CTkComboBox(
            cli_inner,
            values=["Antigravity CLI (agy)", "Claude Code (claude)", "Comandă personalizată / Custom"],
            height=32,
            border_width=1,
            border_color=Theme.BG_BORDER,
            button_color=Theme.BG_PANEL_ALT,
            button_hover_color=Theme.BG_BORDER,
            dropdown_fg_color=Theme.BG_PANEL,
            dropdown_hover_color=Theme.BG_PANEL_ALT,
            dropdown_text_color=Theme.TEXT_MAIN,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption(),
            command=self._on_cli_preset_changed
        )
        self.cli_preset.set("Antigravity CLI (agy)")
        self.cli_preset.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(cli_inner, text=tr("lbl_cli_cmd"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.cli_cmd_entry = ctk.CTkEntry(
            cli_inner,
            height=32,
            border_width=1,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_mono()
        )
        self.cli_cmd_entry.insert(0, "agy")
        self.cli_cmd_entry.pack(fill="x", pady=(2, 8))

        self.btn_test_cli = ctk.CTkButton(
            cli_inner,
            text=tr("btn_test_cli"),
            height=32,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.PRIMARY,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption_bold(),
            command=self._test_cli_connection
        )
        self.btn_test_cli.pack(fill="x", pady=(4, 6))

        self.cli_log_box = ctk.CTkTextbox(
            cli_inner,
            height=70,
            border_width=1,
            border_color=Theme.BG_BORDER,
            fg_color=Theme.BG_INPUT,
            font=Theme.font_mono(),
            text_color=Theme.TEXT_MAIN
        )
        self.cli_log_box.pack(fill="x", pady=(2, 0))
        self.cli_log_box.insert("1.0", "> Test CLI")

        # Secțiunea API
        self.frame_api = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)

        api_inner = ctk.CTkFrame(self.frame_api, fg_color="transparent")
        api_inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(api_inner, text=tr("lbl_api_provider"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.api_provider = ctk.CTkComboBox(
            api_inner,
            values=["Google Gemini API", "OpenAI API", "Anthropic Claude API"],
            height=32,
            border_width=1,
            border_color=Theme.BG_BORDER,
            button_color=Theme.BG_PANEL_ALT,
            button_hover_color=Theme.BG_BORDER,
            dropdown_fg_color=Theme.BG_PANEL,
            dropdown_hover_color=Theme.BG_PANEL_ALT,
            dropdown_text_color=Theme.TEXT_MAIN,
            text_color=Theme.TEXT_MAIN
        )
        self.api_provider.set("Google Gemini API")
        self.api_provider.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(api_inner, text=tr("lbl_api_key"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.api_key_entry = ctk.CTkEntry(
            api_inner,
            height=32,
            border_width=1,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            show="●",
            placeholder_text="API Key..."
        )
        self.api_key_entry.pack(fill="x", pady=(2, 8))

    def _build_zotero_tab(self):
        container = ctk.CTkFrame(self.tab_zotero, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text=tr("lbl_zotero_server"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(0, 4))

        zotero_box = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)
        zotero_box.pack(fill="x", pady=(0, 12))

        z_inner = ctk.CTkFrame(zotero_box, fg_color="transparent")
        z_inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(z_inner, text=tr("lbl_zotero_url"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.zotero_url = ctk.CTkEntry(
            z_inner,
            height=32,
            border_width=1,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_mono()
        )
        self.zotero_url.insert(0, "http://127.0.0.1:23119")
        self.zotero_url.pack(fill="x", pady=(2, 8))

        self.btn_check_zotero = ctk.CTkButton(
            z_inner,
            text=tr("btn_test_zotero"),
            height=32,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.STATUS_SUCCESS,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption_bold(),
            command=self._test_zotero_connection
        )
        self.btn_check_zotero.pack(fill="x", pady=4)

        self.zotero_log_lbl = ctk.CTkLabel(z_inner, text="Port: 23119", font=Theme.font_caption(), text_color=Theme.STATUS_SUCCESS)
        self.zotero_log_lbl.pack(anchor="w", pady=(4, 0))

        # Toleranța la erori și coada offline
        ctk.CTkLabel(container, text=tr("lbl_tolerance_queue"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(10, 4))

        self.sw_sqlite = ctk.CTkSwitch(
            container,
            text=tr("sw_sqlite"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MAIN
        )
        self.sw_sqlite.select()
        self.sw_sqlite.pack(anchor="w", pady=4)

        self.sw_autosync = ctk.CTkSwitch(
            container,
            text=tr("sw_autosync"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MAIN
        )
        self.sw_autosync.select()
        self.sw_autosync.pack(anchor="w", pady=4)

        self.sw_recognize = ctk.CTkSwitch(
            container,
            text=tr("sw_recognize"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MAIN
        )
        self.sw_recognize.select()
        self.sw_recognize.pack(anchor="w", pady=4)

        # Rezervă web: căutare PDF după DOI/ISBN neînregistrat (Brave Search API)
        ctk.CTkLabel(container, text=tr("lbl_web_search"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(10, 4))

        web_box = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)
        web_box.pack(fill="x")

        web_inner = ctk.CTkFrame(web_box, fg_color="transparent")
        web_inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(web_inner, text=tr("lbl_brave_key"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED).pack(anchor="w")
        self.brave_key_entry = ctk.CTkEntry(
            web_inner,
            height=32,
            border_width=1,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_mono(),
            placeholder_text=tr("brave_key_placeholder")
        )
        self.brave_key_entry.pack(fill="x", pady=(2, 4))

        ctk.CTkLabel(web_inner, text=tr("lbl_brave_hint"), font=Theme.font_caption(), text_color=Theme.TEXT_MUTED, wraplength=430, justify="left").pack(anchor="w")

    def _build_system_tab(self):
        container = ctk.CTkFrame(self.tab_system, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text=tr("lbl_os_integration"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(0, 4))

        sys_box = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)
        sys_box.pack(fill="x", pady=(0, 12))

        s_inner = ctk.CTkFrame(sys_box, fg_color="transparent")
        s_inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(
            s_inner,
            text=tr("lbl_ctx_desc"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED,
            wraplength=480,
            anchor="w"
        ).pack(anchor="w", pady=(0, 8))

        btn_install_shell = ctk.CTkButton(
            s_inner,
            text=tr("btn_install_shell"),
            height=36,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_body_bold(),
            command=self._register_context_menu
        )
        btn_install_shell.pack(fill="x", pady=4)

        self.shell_status_lbl = ctk.CTkLabel(s_inner, text="Ready", font=Theme.font_caption(), text_color=Theme.TEXT_DARK)
        self.shell_status_lbl.pack(anchor="w", pady=(2, 0))

        btn_remove_shell = ctk.CTkButton(
            s_inner,
            text=tr("btn_remove_shell"),
            height=30,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption(),
            command=self._unregister_context_menu
        )
        btn_remove_shell.pack(fill="x", pady=(8, 0))

        from core.context_menu import is_registered
        if is_registered():
            self.shell_status_lbl.configure(
                text="✓ Active (.pdf/.docx)",
                text_color=Theme.STATUS_SUCCESS
            )

        ctk.CTkButton(
            s_inner,
            text=tr("btn_open_logs"),
            height=32,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.BG_BORDER,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption_bold(),
            command=self._open_logs_folder
        ).pack(fill="x", pady=(10, 0))

        self.sw_toast = ctk.CTkSwitch(
            container,
            text=tr("sw_toast"),
            font=Theme.font_caption()
        )
        self.sw_toast.select()
        self.sw_toast.pack(anchor="w", pady=8)

        self.sw_tray = ctk.CTkSwitch(
            container,
            text=tr("sw_tray"),
            font=Theme.font_caption()
        )
        self.sw_tray.select()
        self.sw_tray.pack(anchor="w", pady=4)

        # Temă de aspect
        ctk.CTkLabel(container, text=tr("lbl_appearance_theme"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(10, 4))
        self.theme_selector = ThemedSegmentedButton(
            container,
            values=[tr("theme_system"), tr("theme_dark"), tr("theme_light")],
            height=30,
            border_width=1,
            fg_color=Theme.BG_PANEL_ALT,
            unselected_color=Theme.BG_PANEL_ALT,
            unselected_hover_color=Theme.BG_BORDER,
            selected_color=Theme.PRIMARY,
            selected_hover_color=Theme.PRIMARY_HOVER,
            command=self._on_theme_changed
        )
        self.theme_selector.set(tr("theme_system"))
        self.theme_selector.pack(fill="x", pady=2)

        # Limbă interfață (i18n)
        ctk.CTkLabel(container, text=tr("lbl_ui_language"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(10, 4))
        lang_names = list(self._avail_langs.values())
        self.lang_selector = ctk.CTkComboBox(
            container,
            values=lang_names,
            height=32,
            border_width=1,
            border_color=Theme.BG_BORDER,
            button_color=Theme.BG_PANEL_ALT,
            button_hover_color=Theme.BG_BORDER,
            dropdown_fg_color=Theme.BG_PANEL,
            dropdown_hover_color=Theme.BG_PANEL_ALT,
            dropdown_text_color=Theme.TEXT_MAIN,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption()
        )
        cur_lang_code = get_language()
        cur_lang_name = self._avail_langs.get(cur_lang_code, "Română")
        self.lang_selector.set(cur_lang_name)
        self.lang_selector.pack(fill="x", pady=2)

    def _build_langs_tab(self):
        container = ctk.CTkFrame(self.tab_langs, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text=tr("lbl_tess_packs"), font=Theme.font_caption_bold(), text_color=Theme.PRIMARY).pack(anchor="w", pady=(0, 4))

        box = ctk.CTkFrame(container, fg_color=Theme.BG_HEADER, corner_radius=8, border_width=1, border_color=Theme.BG_BORDER)
        box.pack(fill="x", pady=(0, 12))

        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(
            inner,
            text=tr("lbl_tess_desc"),
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED,
            wraplength=480,
            anchor="w"
        ).pack(anchor="w", pady=(0, 8))

        self.langs_count_lbl = ctk.CTkLabel(inner, text="", font=Theme.font_caption_bold(), text_color=Theme.TEXT_MAIN)
        self.langs_count_lbl.pack(anchor="w", pady=(0, 8))
        self._refresh_langs_count()

        ctk.CTkButton(
            inner,
            text=tr("btn_manage_langs"),
            height=36,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            font=Theme.font_body_bold(),
            command=self._open_languages_manager
        ).pack(fill="x", pady=4)

    def _refresh_langs_count(self):
        installed = installed_languages(default_tessdata_dir())
        codes = ", ".join(sorted(installed)) if installed else "—"
        self.langs_count_lbl.configure(
            text=tr("lbl_installed", count=len(installed), codes=codes)
        )

    def _open_languages_manager(self):
        dlg = LanguagesDialog(self)
        self.wait_window(dlg)
        self._refresh_langs_count()

    def _on_ai_mode_changed(self, mode: str):
        if mode == tr("ai_mode_cli") or "CLI" in mode:
            self.frame_api.pack_forget()
            self.frame_cli.pack(fill="x", pady=6)
        else:
            self.frame_cli.pack_forget()
            self.frame_api.pack(fill="x", pady=6)

    def _on_cli_preset_changed(self, preset: str):
        if "Antigravity" in preset:
            self.cli_cmd_entry.delete(0, "end")
            self.cli_cmd_entry.insert(0, "agy")
        elif "Claude" in preset:
            self.cli_cmd_entry.delete(0, "end")
            self.cli_cmd_entry.insert(0, "claude")

    def _test_cli_connection(self):
        cmd = self.cli_cmd_entry.get().strip() or "agy"
        self.cli_log_box.delete("1.0", "end")
        self.cli_log_box.insert("1.0", f"> Test: {cmd}...\n")

        def run_test():
            try:
                from worker.ai_adapter import resolve_cli_binary
                resolved = resolve_cli_binary(cmd)
                if not os.path.isfile(resolved) and not shutil.which(resolved):
                    self.after(0, lambda: self._update_cli_log(
                        f"> ERROR: '{cmd}' not found in PATH or standard dirs"
                    ))
                    return

                res = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=8)
                ver = res.stdout.strip() or res.stderr.strip() or "OK"

                probe = subprocess.run([resolved, "-p", "Reply with one word: OK", "--output-format", "text"], capture_output=True, text=True, timeout=25)
                probe_res = probe.stdout.strip() if probe.returncode == 0 else (probe.stderr.strip() or "error")

                log_msg = (
                    f"> SUCCESS: CLI active.\n"
                    f"> Path: {resolved}\n"
                    f"> Version: {ver}\n"
                    f"> Output: {probe_res}"
                )
                self.after(0, lambda: self._update_cli_log(log_msg))
            except Exception as e:
                self.after(0, lambda: self._update_cli_log(f"> ERROR: {str(e)}"))

        threading.Thread(target=run_test, daemon=True).start()

    def _update_cli_log(self, text: str):
        self.cli_log_box.delete("1.0", "end")
        self.cli_log_box.insert("1.0", text)

    def _test_zotero_connection(self):
        url = self.zotero_url.get().strip() or DEFAULT_URL
        self.zotero_log_lbl.configure(text=f"Connecting {url}...", text_color=Theme.PRIMARY)

        def run_test():
            online = ZoteroConnector(url).ping()
            def apply():
                if online:
                    self.zotero_log_lbl.configure(
                        text=f"✓ Zotero online ({url})",
                        text_color=Theme.STATUS_SUCCESS)
                else:
                    self.zotero_log_lbl.configure(
                        text=f"✕ Zotero offline ({url})",
                        text_color=Theme.STATUS_WARNING)
            self.after(0, apply)

        threading.Thread(target=run_test, daemon=True).start()

    def _open_logs_folder(self):
        from core.logging_setup import default_log_dir
        path = default_log_dir()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _register_context_menu(self):
        from core.context_menu import register_context_menu
        msg = register_context_menu()
        ok = msg.startswith("✓")
        self.shell_status_lbl.configure(
            text=msg,
            text_color=Theme.STATUS_SUCCESS if ok else Theme.STATUS_DANGER
        )

    def _unregister_context_menu(self):
        from core.context_menu import unregister_context_menu
        msg = unregister_context_menu()
        self.shell_status_lbl.configure(text=msg, text_color=Theme.TEXT_DARK)

    def _on_theme_changed(self, choice: str):
        if choice == tr("theme_system") or "Sistem" in choice or "System" in choice:
            ctk.set_appearance_mode("system")
        elif choice == tr("theme_dark") or "Întunecat" in choice or "Dark" in choice or "Тёмн" in choice:
            ctk.set_appearance_mode("dark")
        elif choice == tr("theme_light") or "Luminos" in choice or "Light" in choice or "Светл" in choice:
            ctk.set_appearance_mode("light")

    def _load_settings(self):
        g = self.db.get_setting
        url = g("zotero_url", "")
        if url:
            self.zotero_url.delete(0, "end")
            self.zotero_url.insert(0, url)
        for key, widget in (("cli_preset", self.cli_preset), ("api_provider", self.api_provider)):
            val = g(key, "")
            if val:
                widget.set(val)
                if key == "cli_preset":
                    self._on_cli_preset_changed(val)
        cmd = g("cli_cmd", "")
        if cmd:
            self.cli_cmd_entry.delete(0, "end")
            self.cli_cmd_entry.insert(0, cmd)
        key_val = g("api_key", "")
        if key_val:
            self.api_key_entry.delete(0, "end")
            self.api_key_entry.insert(0, key_val)
        brave_val = g("brave_api_key", "")
        if brave_val:
            self.brave_key_entry.delete(0, "end")
            self.brave_key_entry.insert(0, brave_val)
        if g("ai_mode", "cli") == "api":
            self.ai_mode_selector.set(tr("ai_mode_api"))
            self._on_ai_mode_changed(tr("ai_mode_api"))
        for key, sw in (("sqlite_queue", self.sw_sqlite), ("autosync", self.sw_autosync),
                        ("zotero_recognize", self.sw_recognize),
                        ("toast", self.sw_toast), ("tray", self.sw_tray)):
            if g(key, "1") == "0":
                sw.deselect()
        theme = g("theme", "")
        if theme:
            self.theme_selector.set(theme)

        # Limbă UI
        ui_code = g("ui_lang", get_language())
        ui_name = self._avail_langs.get(ui_code, "Română")
        self.lang_selector.set(ui_name)

    def _on_save_clicked(self):
        cli_mode = "CLI" in self.ai_mode_selector.get()
        self.db.set_setting("ai_mode", "cli" if cli_mode else "api")
        self.db.set_setting("ai_enabled", "1" if cli_mode else "0")
        self.db.set_setting("cli_preset", self.cli_preset.get())
        self.db.set_setting("cli_cmd", self.cli_cmd_entry.get().strip())
        self.db.set_setting("api_provider", self.api_provider.get())
        self.db.set_setting("api_key", self.api_key_entry.get().strip())
        self.db.set_setting("zotero_url", self.zotero_url.get().strip() or DEFAULT_URL)
        self.db.set_setting("sqlite_queue", "1" if self.sw_sqlite.get() else "0")
        self.db.set_setting("autosync", "1" if self.sw_autosync.get() else "0")
        self.db.set_setting("zotero_recognize", "1" if self.sw_recognize.get() else "0")
        self.db.set_setting("brave_api_key", self.brave_key_entry.get().strip())
        self.db.set_setting("toast", "1" if self.sw_toast.get() else "0")
        self.db.set_setting("tray", "1" if self.sw_tray.get() else "0")
        self.db.set_setting("theme", self.theme_selector.get())

        # Salvare limbă interfață
        sel_name = self.lang_selector.get()
        sel_code = "ro"
        for code, name in self._avail_langs.items():
            if name == sel_name:
                sel_code = code
                break
        self.db.set_setting("ui_lang", sel_code)
        set_language(sel_code)

        if self.on_save:
            self.on_save()
        self.destroy()
