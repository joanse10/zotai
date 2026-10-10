"""
Componenta inspector de metadate cu file (Bibliografie, Proprietăți PDF, JSON brut).
"""

import customtkinter as ctk
import json
from typing import Callable, Optional, Dict
from gui.theme import Theme, make_segmented_button_contrast
from gui.icons import get_app_icon_image
from gui.models import TaskItem, BookMetadata
from zotero.item_types import all_labels, display_label
from core.i18n import tr


class MetadataInspectorComponent(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_save_metadata: Callable[[TaskItem, BookMetadata], None],
        on_rescan_ai: Callable[[TaskItem], None],
        on_sync_zotero: Callable[[TaskItem], None]
    ):
        super().__init__(
            master,
            width=375,
            corner_radius=10,
            fg_color=Theme.BG_PANEL,
            border_width=1,
            border_color=Theme.BG_BORDER
        )
        self.pack_propagate(False)

        self.on_save_metadata = on_save_metadata
        self.on_rescan_ai = on_rescan_ai
        self.on_sync_zotero = on_sync_zotero

        self.current_task: Optional[TaskItem] = None
        self._fields: Dict[str, ctk.CTkEntry] = {}
        self._field_labels: Dict[str, ctk.CTkLabel] = {}
        self._section_labels = []

        self._build_ui()

    def _build_ui(self):
        # 1. Antetul inspectorului
        header = ctk.CTkFrame(self, height=50, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        app_icon = get_app_icon_image(size=20)
        if app_icon:
            ctk.CTkLabel(header, text="", image=app_icon).pack(side="left", padx=(0, 6))

        self.title_lbl = ctk.CTkLabel(
            header,
            text=tr("inspector_title"),
            font=Theme.font_section(),
            text_color=Theme.TEXT_MAIN
        )
        self.title_lbl.pack(side="left")

        self.doc_type_badge = ctk.CTkLabel(
            header,
            text=tr("lbl_doc_type"),
            fg_color=Theme.PRIMARY_BG,
            text_color=Theme.PRIMARY_TEXT,
            corner_radius=6,
            font=Theme.font_caption_bold(),
            padx=8,
            pady=2
        )
        self.doc_type_badge.pack(side="right")

        # 2. Filele de vizualizare detaliată
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=Theme.BG_PANEL,
            segmented_button_fg_color=Theme.BG_PANEL_ALT,
            segmented_button_selected_color=Theme.PRIMARY,
            segmented_button_selected_hover_color=Theme.PRIMARY_HOVER,
            segmented_button_unselected_color=Theme.BG_PANEL_ALT,
            segmented_button_unselected_hover_color=Theme.BG_BORDER
        )
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tabview._segmented_button.configure(border_width=1, fg_color=Theme.BG_PANEL_ALT)

        self.tab_biblio = self.tabview.add(tr("tab_biblio"))
        self.tab_file = self.tabview.add(tr("tab_pdf_props"))
        self.tab_json = self.tabview.add(tr("tab_raw_json"))

        make_segmented_button_contrast(self.tabview._segmented_button, tr("tab_biblio"))

        self._build_biblio_tab()
        self._build_file_tab()
        self._build_json_tab()

        # 3. Blocul de acțiuni de jos
        actions_bar = ctk.CTkFrame(self, fg_color="transparent")
        actions_bar.pack(fill="x", padx=16, pady=(4, 14))

        self.btn_save_xmp = ctk.CTkButton(
            actions_bar,
            text=tr("btn_save_xmp"),
            height=38,
            fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER,
            text_color="#FFFFFF",
            font=Theme.font_body_bold(),
            command=self._on_save_clicked
        )
        self.btn_save_xmp.pack(fill="x", pady=(0, 6))

        sec_btns = ctk.CTkFrame(actions_bar, fg_color="transparent")
        sec_btns.pack(fill="x")

        self.btn_rescan = ctk.CTkButton(
            sec_btns,
            text=tr("btn_rescan_ai"),
            height=32,
            fg_color=Theme.BG_PANEL_ALT,
            hover_color=Theme.BG_BORDER_LIGHT,
            border_width=1,
            border_color=Theme.BG_BORDER,
            font=Theme.font_caption_bold(),
            text_color=Theme.TEXT_MAIN,
            command=self._on_rescan_clicked
        )
        self.btn_rescan.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_sync_one = ctk.CTkButton(
            sec_btns,
            text=tr("btn_send_zotero"),
            height=32,
            fg_color=Theme.STATUS_SUCCESS_BG,
            hover_color=Theme.STATUS_SUCCESS_HOVER,
            border_width=1,
            border_color=Theme.STATUS_SUCCESS,
            font=Theme.font_caption_bold(),
            text_color=Theme.STATUS_SUCCESS_TEXT,
            command=self._on_sync_clicked
        )
        self.btn_sync_one.pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _build_biblio_tab(self):
        scroll = ctk.CTkScrollableFrame(
            self.tab_biblio,
            fg_color=Theme.BG_PANEL,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Theme.BG_BORDER,
            scrollbar_button_hover_color=Theme.TEXT_MUTED
        )
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Secțiunea 1: Informații generale
        self._section_labels.append(self._make_section_title(scroll, "INFORMAȚII GENERALE"))
        for attr, key in (
            ("title",       "lbl_title"),
            ("subtitle",    "lbl_subtitle"),
            ("authors",     "lbl_authors"),
            ("editors",     "lbl_editors"),
        ):
            entry, lbl = self._create_input_field(scroll, tr(key))
            self._fields[attr] = entry
            self._field_labels[attr] = lbl

        self.lbl_abstract_hdr = ctk.CTkLabel(
            scroll, text=tr("lbl_abstract"), font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED, bg_color=Theme.BG_PANEL, anchor="w"
        )
        self.lbl_abstract_hdr.pack(fill="x", pady=(4, 2))
        self.field_abstract = ctk.CTkTextbox(
            scroll, height=64, fg_color=Theme.BG_INPUT, border_color=Theme.BG_BORDER,
            border_width=1, text_color=Theme.TEXT_MAIN, font=Theme.font_caption()
        )
        self.field_abstract.pack(fill="x", pady=(0, 2))

        # Secțiunea 2: Date de publicare
        self._section_labels.append(self._make_section_title(scroll, "DATE DE PUBLICARE"))
        for attr, key in (
            ("publisher",     "lbl_publisher"),
            ("city",          "lbl_city"),
            ("year",          "lbl_year"),
            ("edition",       "lbl_edition"),
            ("publication_title", "lbl_publication_title"),
            ("series",        "lbl_series"),
            ("series_number", "lbl_series_number"),
            ("volume",        "lbl_volume"),
            ("issue",         "lbl_issue"),
            ("num_volumes",   "lbl_num_volumes"),
            ("num_pages",     "lbl_pages"),
        ):
            entry, lbl = self._create_input_field(scroll, tr(key))
            self._fields[attr] = entry
            self._field_labels[attr] = lbl

        # Secțiunea 3: Identificatori și linkuri
        self._section_labels.append(self._make_section_title(scroll, "IDENTIFICATORI ȘI LINKURI"))
        for attr, key in (
            ("isbn",         "lbl_isbn"),
            ("issn",         "lbl_issn"),
            ("doi",          "lbl_doi"),
            ("url",          "lbl_url"),
            ("accessed",     "lbl_accessed"),
            ("citation_key", "lbl_citation_key"),
        ):
            entry, lbl = self._create_input_field(scroll, tr(key))
            self._fields[attr] = entry
            self._field_labels[attr] = lbl

        # Secțiunea 4: Arhivă și catalogare
        self._section_labels.append(self._make_section_title(scroll, "ARHIVĂ ȘI CATALOGARE"))
        for attr, key in (
            ("archive",          "lbl_archive"),
            ("loc_in_archive",   "lbl_loc_in_archive"),
            ("call_number",      "lbl_call_number"),
            ("library_catalog",  "lbl_library_catalog"),
            ("license",          "lbl_rights"),
            ("extra",            "lbl_extra"),
        ):
            entry, lbl = self._create_input_field(scroll, tr(key))
            self._fields[attr] = entry
            self._field_labels[attr] = lbl

        # Lista derulantă pentru tipul documentului
        self.lbl_type_hdr = ctk.CTkLabel(scroll, text=tr("lbl_doc_type"), font=Theme.font_caption_bold(), text_color=Theme.TEXT_MUTED, anchor="w")
        self.lbl_type_hdr.pack(fill="x", pady=(6, 2))
        self.type_combo = ctk.CTkComboBox(
            scroll,
            values=all_labels(),
            height=32,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            border_width=1,
            button_color=Theme.BG_PANEL_ALT,
            button_hover_color=Theme.BG_BORDER,
            dropdown_fg_color=Theme.BG_PANEL,
            dropdown_hover_color=Theme.BG_PANEL_ALT,
            dropdown_text_color=Theme.TEXT_MAIN,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_caption()
        )
        self.type_combo.pack(fill="x", pady=(0, 8))

    def _build_file_tab(self):
        scroll = ctk.CTkScrollableFrame(
            self.tab_file,
            fg_color=Theme.BG_PANEL,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=Theme.BG_BORDER,
            scrollbar_button_hover_color=Theme.TEXT_MUTED
        )
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self.info_file_name, self.lbl_fn = self._create_readonly_row(scroll, "lbl_file_path")
        self.info_file_path, self.lbl_fp = self._create_readonly_row(scroll, "lbl_file_path")
        self.info_file_size, self.lbl_fs = self._create_readonly_row(scroll, "lbl_file_size")
        self.info_pages, self.lbl_pc = self._create_readonly_row(scroll, "lbl_page_count")
        self.info_layer, self.lbl_lt = self._create_readonly_row(scroll, "col_layer")
        self.info_language, self.lbl_lg = self._create_readonly_row(scroll, "col_lang")
        self.info_confidence, self.lbl_cf = self._create_readonly_row(scroll, "lbl_confidence")
        self.info_error, self.lbl_er = self._create_readonly_row(scroll, "stage_error")

    def _build_json_tab(self):
        self.json_textbox = ctk.CTkTextbox(
            self.tab_json,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            border_width=1,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_mono()
        )
        self.json_textbox.pack(fill="both", expand=True, padx=4, pady=4)

    def _make_section_title(self, parent, text: str):
        title = ctk.CTkLabel(
            parent,
            text=text,
            font=Theme.font_caption_bold(),
            text_color=Theme.PRIMARY,
            fg_color="transparent",
            bg_color=Theme.BG_PANEL,
            anchor="w"
        )
        title.pack(fill="x", pady=(10, 4))
        return title

    def _create_input_field(self, parent, label_text: str):
        lbl = ctk.CTkLabel(
            parent,
            text=label_text,
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MUTED,
            fg_color="transparent",
            bg_color=Theme.BG_PANEL,
            anchor="w"
        )
        lbl.pack(fill="x", pady=(4, 2))

        entry = ctk.CTkEntry(
            parent,
            height=32,
            fg_color=Theme.BG_INPUT,
            border_color=Theme.BG_BORDER,
            border_width=1,
            text_color=Theme.TEXT_MAIN,
            font=Theme.font_body()
        )
        entry.pack(fill="x", pady=(0, 2))
        return entry, lbl

    def _create_readonly_row(self, parent, key: str):
        lbl = ctk.CTkLabel(
            parent,
            text=tr(key),
            font=Theme.font_caption_bold(),
            text_color=Theme.TEXT_MUTED,
            fg_color="transparent",
            bg_color=Theme.BG_PANEL,
            anchor="w"
        )
        lbl.pack(fill="x", pady=(6, 1))

        val = ctk.CTkLabel(
            parent,
            text="—",
            font=Theme.font_caption(),
            text_color=Theme.TEXT_MAIN,
            fg_color="transparent",
            bg_color=Theme.BG_PANEL,
            anchor="w",
            wraplength=340
        )
        val.pack(fill="x", pady=(0, 4))
        return val, lbl

    def refresh_texts(self):
        self.title_lbl.configure(text=tr("inspector_title"))
        self.btn_save_xmp.configure(text=tr("btn_save_xmp"))
        self.btn_rescan.configure(text=tr("btn_rescan_ai"))
        self.btn_sync_one.configure(text=tr("btn_send_zotero"))
        self.lbl_abstract_hdr.configure(text=tr("lbl_abstract"))
        self.lbl_type_hdr.configure(text=tr("lbl_doc_type"))

        field_key_map = {
            "title": "lbl_title", "subtitle": "lbl_subtitle",
            "authors": "lbl_authors", "editors": "lbl_editors",
            "publisher": "lbl_publisher", "city": "lbl_city",
            "year": "lbl_year", "edition": "lbl_edition",
            "series": "lbl_series", "series_number": "lbl_series_number",
            "publication_title": "lbl_publication_title", "issue": "lbl_issue",
            "volume": "lbl_volume", "num_volumes": "lbl_num_volumes",
            "num_pages": "lbl_pages", "isbn": "lbl_isbn",
            "issn": "lbl_issn", "doi": "lbl_doi", "url": "lbl_url",
            "accessed": "lbl_accessed", "citation_key": "lbl_citation_key",
            "archive": "lbl_archive", "loc_in_archive": "lbl_loc_in_archive",
            "call_number": "lbl_call_number", "library_catalog": "lbl_library_catalog",
            "license": "lbl_rights", "extra": "lbl_extra",
        }
        for attr, lbl in self._field_labels.items():
            key = field_key_map.get(attr)
            if key:
                lbl.configure(text=tr(key))

        self.set_task(self.current_task)

    def set_task(self, task: Optional[TaskItem]):
        self.current_task = task
        if not task:
            self._clear_fields()
            return

        m = task.metadata
        for attr, entry in self._fields.items():
            self._set_entry(entry, getattr(m, attr, ""))
        self.field_abstract.delete("1.0", "end")
        self.field_abstract.insert("1.0", m.abstract or "")
        label = display_label(m.doc_type)
        self.type_combo.set(label)
        self.doc_type_badge.configure(text=label)

        # Fila Fișier
        self.info_file_name.configure(text=task.file_name)
        self.info_file_path.configure(text=task.file_path)
        self.info_file_size.configure(text=task.file_size_str)
        self.info_pages.configure(text=str(task.page_count))
        self.info_layer.configure(text=task.layer_type)
        self.info_language.configure(text=task.language)
        self.info_confidence.configure(text=f"{int(m.confidence * 100)}%")
        self.info_error.configure(
            text=task.error if task.error else "—",
            text_color=Theme.STATUS_DANGER_TEXT if task.error else Theme.TEXT_MAIN
        )

        # Fila JSON
        self.json_textbox.delete("1.0", "end")
        self.json_textbox.insert("1.0", m.raw_json)

    def _set_entry(self, entry: ctk.CTkEntry, value: str):
        entry.delete(0, "end")
        entry.insert(0, value or "")

    def _clear_fields(self):
        for e in self._fields.values():
            e.delete(0, "end")
        self.field_abstract.delete("1.0", "end")
        self.json_textbox.delete("1.0", "end")

    def _on_save_clicked(self):
        if not self.current_task:
            return
        m = self.current_task.metadata
        for attr, entry in self._fields.items():
            setattr(m, attr, entry.get())
        m.abstract = self.field_abstract.get("1.0", "end").strip()
        m.doc_type = self.type_combo.get()
        self.doc_type_badge.configure(text=m.doc_type)

        try:
            parsed = json.loads(self.json_textbox.get("1.0", "end").strip())
            parsed.update({"title": m.title, "authors": m.authors, "publisher": m.publisher,
                           "year": m.year, "isbn": m.isbn, "item_type": m.doc_type})
            m.raw_json = json.dumps(parsed, ensure_ascii=False, indent=2)
            self.json_textbox.delete("1.0", "end")
            self.json_textbox.insert("1.0", m.raw_json)
        except Exception:
            pass

        self.on_save_metadata(self.current_task, m)

    def _on_rescan_clicked(self):
        if self.current_task:
            self.on_rescan_ai(self.current_task)

    def _on_sync_clicked(self):
        if self.current_task:
            self.on_sync_zotero(self.current_task)
