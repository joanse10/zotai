"""
Modele de date pentru componentele UI Zotai.
"""

from dataclasses import dataclass, field

# Tesseract/AI folosesc ISO 639-2/T; Zotero și XMP preferă ISO 639-1
_ISO3_TO_ISO1 = {
    "ron": "ro", "rum": "ro", "rus": "ru", "eng": "en", "ukr": "uk",
    "fra": "fr", "fre": "fr", "deu": "de", "ger": "de", "ita": "it",
    "spa": "es", "por": "pt", "bul": "bg", "pol": "pl", "tur": "tr",
    "ara": "ar", "chi": "zh", "zho": "zh", "jpn": "ja", "kor": "ko",
    "lat": "la", "gre": "el", "ell": "el", "heb": "he", "hun": "hu",
    "ces": "cs", "cze": "cs", "slk": "sk", "swe": "sv", "nld": "nl",
    "dut": "nl", "mol": "mo", "srp": "sr", "hrv": "hr", "aze": "az",
}


def iso639_1(lang: str) -> str:
    """Normalizează codul de limbă la ISO 639-1 („ron” → „ro”, „eng” → „en”)."""
    code = (lang or "").strip().lower().replace("_", "-").split("-")[0]
    if not code:
        return ""
    if len(code) == 2:
        return code
    return _ISO3_TO_ISO1.get(code, code)


@dataclass
class BookMetadata:
    """
    Metadate bibliografice ale documentului.
    Câmpurile corespund schemei panoului Info din Zotero (vezi zotero/item_types.py,
    zotero/convert.py — convertor către JSON-ul API-ului Zotero).
    """
    # Informații generale
    title: str = ""
    subtitle: str = ""
    short_title: str = ""
    authors: str = ""            # separate prin virgulă -> creators[author]
    editors: str = ""            # separate prin virgulă -> creators[editor]
    doc_type: str = "Carte (book)"  # eticheta UI canonică
    language: str = "RON"
    abstract: str = ""

    # Date de publicare
    publisher: str = ""
    year: str = ""               # -> date
    city: str = ""               # -> place
    edition: str = ""
    publication_title: str = ""  # revista / culegerea / cartea-părinte -> publicationTitle / proceedingsTitle / bookTitle
    series: str = ""
    series_number: str = ""
    volume: str = ""
    issue: str = ""              # numărul revistei -> issue
    num_volumes: str = ""
    num_pages: str = ""

    # Identificatori și linkuri
    isbn: str = ""
    issn: str = ""
    doi: str = ""
    url: str = ""
    accessed: str = ""           # -> accessDate
    citation_key: str = ""

    # Câmpuri de arhivă și bibliotecă
    archive: str = ""
    loc_in_archive: str = ""     # -> archiveLocation
    call_number: str = ""
    library_catalog: str = ""
    license: str = ""            # -> rights
    extra: str = ""

    # Câmpuri interne Zotai
    confidence: float = 0.95
    raw_json: str = "{}"


@dataclass
class TaskItem:
    id: str
    file_name: str
    file_path: str
    file_size_str: str
    page_count: int
    layer_type: str       # "Text" sau "Scan (OCR)"
    language: str         # "RON", "RUS", "ENG"
    pipeline_stage: str   # "În așteptare", "Analiză AI", "Scriere XMP", "Finalizat", "Eroare"
    zotero_status: str    # "Sincronizat", "Zotero Offline (SQLite)", "În așteptare"
    metadata: BookMetadata = field(default_factory=BookMetadata)
    extracted_text: str = ""  # eșantion de text pentru etapa AI
    error: str = ""           # ultimul mesaj de eroare din pipeline
