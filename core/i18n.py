"""
Modul de internaționalizare (i18n) pentru Zotai.

Încarcă traducerile din fișiere externe JSON din directorul `locales/`
(de ex. `locales/ro.json`, `locales/ru.json`, `locales/en.json`).
Dacă fișierele lipsesc sau un termen nu este definit, se folosește
limba română implicită (încorporată ca rezervă de siguranță).
"""

import json
import logging
import os
from typing import Dict, Optional

from core.paths import locales_dir

log = logging.getLogger("zotai")

DEFAULT_LANGUAGE = "ro"

# Denumiri implicite pentru codurile ISO cunoscute (folosite doar dacă fișierul JSON nu conține cheia '_lang_name')
_KNOWN_LANG_NAMES: Dict[str, str] = {
    "ro": "Română",
    "ru": "Русский",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "uk": "Українська",
    "pl": "Polski",
    "tr": "Türkçe",
    "zh": "中文",
    "ja": "日本語",
    "nl": "Nederlands",
    "el": "Ελληνικά",
    "cs": "Čeština",
    "hu": "Magyar",
    "bg": "Български",
}

# Dicționar încorporat de rezervă în limba română (fallback garantat dacă fișierele externe lipsesc complet)
_BUILTIN_RO: Dict[str, str] = {
    # Antet & Fereastră
    "app_title": "Zotai — Metadate PDF & punte AI pentru Zotero",
    "app_subtitle": "Punte AI între metadatele PDF și Zotero",
    "btn_settings": "⚙ Setări",
    "zotero_online": "Zotero: Online ({port}) ●",
    "zotero_offline": "Zotero: Offline ({count} în coadă) ●",
    "ai_active": "AI: CLI ({cli}) ●",
    "ai_inactive": "AI: CLI (inactiv) ●",

    # Dropzone
    "dropzone_title": "Glisați fișiere PDF/DOCX aici pentru procesare automată",
    "dropzone_desc": "Detectarea stratului (text digital / scan), extragerea metadatelor cu AI și injectarea XMP Dublin Core",
    "dropzone_btn_files": "+ Selectați fișiere",
    "dropzone_btn_folder": "Folder",
    "dropzone_added_success": "Fișiere adăugate în coadă: {count}",
    "dropzone_no_files_error": "Niciun fișier PDF/DOCX între elementele selectate",
    "dropzone_all_exist_error": "Toate fișierele selectate sunt deja în listă",

    # Căutare
    "search_placeholder": "ISBN, DOI, link PDF sau titlul cărții…",
    "search_btn": "🔍 Caută",
    "search_busy": "Se caută…",
    "search_results_title": "S-au găsit {count} rezultate — selectați înregistrarea",
    "search_results_window": "Rezultatele căutării",
    "search_no_results": "Niciun rezultat găsit",

    # Tabel de sarcini & Filtre
    "filter_all": "Toate",
    "filter_processing": "În procesare",
    "filter_queued": "Coadă Zotero",
    "filter_completed": "Finalizate",
    "btn_clear_completed": "Șterge finalizate",
    "col_doc": "Document",
    "col_layer": "Strat",
    "col_lang": "Limbă",
    "col_stage": "Etapă pipeline",
    "col_zotero": "Stare Zotero",
    "col_actions": "Acțiuni",
    "empty_queue": "Nicio sarcină în această categorie",
    "unit_pages": "{count} pagini",
    "unit_page_single": "1 pagină",

    # Etape pipeline
    "stage_pending": "În așteptare",
    "stage_analyzing_layer": "Analiză strat",
    "stage_ai": "Analiză AI",
    "stage_xmp": "Scriere XMP",
    "stage_xmp_updated": "XMP actualizat",
    "stage_completed": "Finalizat",
    "stage_error": "Eroare",

    # Straturi
    "layer_text": "Text",
    "layer_scan": "Scan (OCR)",
    "layer_empty": "Gol",
    "layer_analyzing": "Se analizează...",

    # Status Zotero
    "zotero_synced": "Sincronizat",
    "zotero_queued": "Zotero Offline (SQLite)",
    "zotero_error": "Eroare Zotero",

    # Bara de stare
    "status_stats": "Total: {total}  |  Sincronizate: {synced}  |  În coada Zotero: {queued}  |  În procesare: {processing}",
    "btn_sync_queue": "Sincronizează coada Zotero ({count})",

    # Inspector metadate
    "inspector_title": "Metadate document",
    "tab_biblio": "Bibliografie",
    "tab_pdf_props": "Proprietăți PDF",
    "tab_raw_json": "JSON brut",
    "btn_save_xmp": "💾 Scrie XMP în PDF",
    "btn_rescan_ai": "↺ Analiză AI",
    "btn_send_zotero": "↑ În Zotero",
    "inspector_select_task": "Selectați un document din listă pentru editare",
    "lbl_title": "Titlu",
    "lbl_subtitle": "Subtitlu",
    "lbl_authors": "Autori (separați prin virgulă)",
    "lbl_editors": "Editori (separați prin virgulă)",
    "lbl_doc_type": "Tip document",
    "lbl_language": "Limbă document",
    "lbl_publisher": "Editură",
    "lbl_year": "An publicare",
    "lbl_city": "Oraș / Loc",
    "lbl_edition": "Ediție",
    "lbl_series": "Serie",
    "lbl_series_number": "Număr serie",
    "lbl_volume": "Volum",
    "lbl_num_volumes": "Număr total volume",
    "lbl_pages": "Număr pagini",
    "lbl_isbn": "ISBN",
    "lbl_issn": "ISSN",
    "lbl_doi": "DOI",
    "lbl_url": "URL sursă",
    "lbl_accessed": "Data accesării",
    "lbl_citation_key": "Cheie citare",
    "lbl_archive": "Arhivă",
    "lbl_loc_in_archive": "Locație în arhivă",
    "lbl_call_number": "Clasificare / Cotă",
    "lbl_library_catalog": "Catalog bibliotecă",
    "lbl_rights": "Drepturi / Licență",
    "lbl_extra": "Câmpuri extra (CZU, tiraj, etc.)",
    "lbl_abstract": "Rezumat (Abstract)",
    "lbl_file_path": "Cale fișier:",
    "lbl_file_size": "Dimensiune fișier:",
    "lbl_page_count": "Număr pagini:",
    "lbl_ocr_engine": "Motor OCR:",
    "lbl_confidence": "Încredere AI:",

    # Dialog Setări
    "settings_title": "Setări — Zotai",
    "tab_ai_engine": "1. Motor AI",
    "tab_zotero_conn": "2. Zotero Connector",
    "tab_system_int": "3. Windows & Integrare",
    "tab_ocr_langs": "4. Limbi OCR",
    "btn_save_settings": "Salvează setările",
    "btn_close": "Închide",
    "lbl_ai_method": "METODĂ DE INVOCARE A AI",
    "ai_mode_cli": "CLI terminal (agy / claude)",
    "ai_mode_api": "API direct (cheie)",
    "lbl_cli_preset": "Preset agent CLI:",
    "lbl_cli_cmd": "Comandă în terminal:",
    "btn_test_cli": "▶ Testează conexiunea CLI",
    "lbl_api_provider": "Furnizor API:",
    "lbl_api_key": "Cheie API:",
    "lbl_zotero_server": "SERVER ZOTERO CONNECTOR",
    "lbl_zotero_url": "Adresă locală de conexiune:",
    "btn_test_zotero": "▶ Testează conexiunea Zotero (Ping 23119)",
    "lbl_tolerance_queue": "TOLERANȚĂ LA ERORI ȘI COADĂ",
    "sw_sqlite": "Salvează sarcinile în baza de date SQLite locală când Zotero este offline",
    "sw_autosync": "Golește automat coada la pornirea Zotero",
    "sw_recognize": "Permite Zotero să recunoască automat PDF (dacă există DOI/ISBN)",
    "lbl_os_integration": "INTEGRARE CU SISTEMUL DE OPERARE",
    "lbl_ctx_desc": "Adaugă în meniul contextual Windows Explorer (click dreapta pe orice fișier .pdf/.docx):",
    "btn_install_shell": "⚡ Înregistrează în meniul contextual Windows",
    "btn_remove_shell": "✕ Elimină din meniul contextual",
    "btn_open_logs": "📄 Deschide folderul cu jurnale",
    "sw_toast": "Afișează notificări de sistem în timpul procesării",
    "sw_tray": "Minimizează în bara de sistem în loc de închiderea aplicației",
    "lbl_appearance_theme": "TEMĂ DE ASPECT",
    "theme_system": "Sistem (implicit)",
    "theme_dark": "Întunecată",
    "theme_light": "Luminoasă",
    "lbl_ui_language": "LIMBĂ INTERFAȚĂ",

    # Dialog Limbi OCR
    "langs_title": "Limbi OCR — Zotai",
    "lbl_tess_packs": "PACHETE LINGVISTICE TESSERACT",
    "lbl_tess_desc": "Pachetele de limbi (*.traineddata) se descarcă la cerere în bin/tessdata, fără reinstalarea aplicației. Puteți adăuga și limbi personalizate după coduri ISO 639-2/3.",
    "btn_manage_langs": "Gestionează limbile OCR...",
    "btn_install": "Instalează",
    "btn_remove": "Elimină",
    "lbl_installed": "Instalate: {count} ({codes})",
    "lbl_status_installed": "Instalat ({size})",
    "lbl_status_not_installed": "Neinstalat",
    "lbl_status_downloading": "Se descarcă...",
    "search_lang_placeholder": "🔍 Caută limbă...",
    "lbl_custom_code": "Cod propriu:",

    # Notificări Toast
    "toast_task_card_added": "Fișă adăugată în coada Zotero",
    "toast_task_done": "Document procesat",
    "toast_task_zotero_exported": "Exportat în Zotero",
    "toast_task_extract_failed": "Extragerea textului a eșuat",
    "toast_task_ai_failed": "Eroare la analiza AI",
    "toast_task_xmp_failed": "Eroare la scrierea XMP",
    "toast_task_zotero_failed": "Eroare la exportul în Zotero",

    # Dialoguri fișiere & Gestionare limbi
    "dialog_select_files_title": "Selectați fișierele",
    "dialog_select_folder_title": "Selectați folderul cu cărți PDF",
    "btn_add_custom": "+ Adaugă",
    "lang_code_exists": "'{code}' există deja în listă",
    "lang_code_added": "S-a adăugat codul '{code}' — bifați și descărcați",
    "lang_custom_label": "Personalizat ({code})",
    "langs_select_hint": "Selectați limbile pentru descărcare",
    "btn_download_selected": "Descarcă selectate",
    "btn_remove_selected": "Elimină selectate",
    "status_installed_size": "✓ Instalat ({size} MB)",
    "lang_none_new_selected": "Nicio limbă nouă selectată",
    "lang_downloading_code": "Se descarcă {code}...",
    "lang_download_error": "✕ Eroare: {err}",
    "lang_none_installed_selected": "Nicio limbă instalată selectată",
    "lang_packages_removed": "Pachete eliminate: {count}",
    "lang_batch_done": "Gata. Total limbi instalate: {count}",
}

_current_lang = DEFAULT_LANGUAGE
_translations_cache: Dict[str, Dict[str, str]] = {}
_cache_mtime: Dict[str, float] = {}


def _load_lang_file(lang_code: str) -> Dict[str, str]:
    """
    Încarcă fișierul JSON de localizare din directorul `locales/`.
    Dacă fișierul a fost modificat pe disc (mtime schimbat), este reîncărcat automat.
    """
    target_dir = locales_dir()
    file_path = os.path.join(target_dir, f"{lang_code}.json")

    if os.path.isfile(file_path):
        try:
            mtime = os.path.getmtime(file_path)
            if lang_code in _translations_cache and _cache_mtime.get(lang_code) == mtime:
                return _translations_cache[lang_code]

            with open(file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            _translations_cache[lang_code] = loaded
            _cache_mtime[lang_code] = mtime
            log.info("S-a încărcat pachetul de limbă '%s' din %s (%d termeni)",
                     lang_code, file_path, len(loaded))
            return loaded
        except Exception as e:
            log.warning("Nu s-a putut încărca fișierul de limbă %s: %s", file_path, e)
    else:
        log.debug("Fișierul de limbă %s nu există în %s", lang_code, target_dir)

    return _translations_cache.get(lang_code, {})


def get_available_languages() -> Dict[str, str]:
    """
    Scanează dinamic directorul locales/ pentru toate fișierele *.json.
    Numele limbii este citit direct din interiorul fișierului JSON (_lang_name sau language_name).
    Dacă un fișier nou (ex: de.json, es.json) este adăugat mâine în locales/,
    acesta apare automat în lista de limbi FĂRĂ modificarea vreunui fișier Python!
    Dacă directorul nu conține fișiere, se returnează implicit limba română {'ro': 'Română'}.
    """
    ldir = locales_dir()
    langs: Dict[str, str] = {}

    if os.path.isdir(ldir):
        for fname in sorted(os.listdir(ldir)):
            if fname.lower().endswith(".json") and not fname.startswith("."):
                code = os.path.splitext(fname)[0].lower()
                fpath = os.path.join(ldir, fname)
                name = None
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        name = (data.get("_lang_name") or
                                data.get("language_name") or
                                data.get("_name"))
                except Exception:
                    pass
                if not name:
                    name = _KNOWN_LANG_NAMES.get(code, code.upper())
                langs[code] = name

    # Dacă directorul locales/ este gol sau lipsește, fallback garantat: Română
    if not langs:
        langs["ro"] = "Română"

    return langs


# Compatibilitate backward: returnează limbile descoperite dinamic
def get_supported_languages() -> Dict[str, str]:
    return get_available_languages()


def set_language(lang_code: str):
    """
    Setează limba curentă a aplicației.
    Acceptă orice cod prezent ca fișier JSON în locales/ sau 'ro'.
    Dacă codul nu este găsit, comută pe limba română implicită.
    """
    global _current_lang
    avail = get_available_languages()
    if lang_code in avail or os.path.isfile(os.path.join(locales_dir(), f"{lang_code}.json")):
        _current_lang = lang_code
    else:
        _current_lang = DEFAULT_LANGUAGE


def get_language() -> str:
    """Returnează codul limbii active curente (ex: 'ro', 'ru', 'en', 'de')."""
    return _current_lang


def tr(key: str, default: Optional[str] = None, **kwargs) -> str:
    """
    Traduce cheia dată conform limbii active curente.
    Ierarhie de căutare / fallback:
    1. Limba curentă din fișierul JSON (ex. locales/de.json);
    2. Limba română din fișierul JSON (locales/ro.json);
    3. Dicționarul de urgență încorporat în caz că fișierele externe lipsesc (_BUILTIN_RO);
    4. Parametrul 'default' sau cheia însăși.
    """
    val = None

    # 1. Căutare în fișierul limbii active
    cur_dict = _load_lang_file(_current_lang)
    if cur_dict and key in cur_dict:
        val = cur_dict[key]

    # 2. Fallback la locales/ro.json dacă cheia lipsește în limba activă
    if val is None and _current_lang != DEFAULT_LANGUAGE:
        ro_dict = _load_lang_file(DEFAULT_LANGUAGE)
        if ro_dict and key in ro_dict:
            val = ro_dict[key]

    # 3. Fallback la dicționarul intern dacă fișierele JSON lipsesc de pe disc
    if val is None and key in _BUILTIN_RO:
        val = _BUILTIN_RO[key]

    # 4. Fallback final
    if val is None:
        val = default if default is not None else key

    if kwargs and isinstance(val, str):
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val if isinstance(val, str) else str(val or "")


def reload_translations():
    """Golește memoria cache pentru a forța reîncărcarea fișierelor de limbă."""
    _translations_cache.clear()
    _cache_mtime.clear()

