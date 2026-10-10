"""
Catalogul tipurilor de elemente Zotero și schema câmpurilor de metadate.

Lista corespunde tipurilor de elemente Zotero (excluzând tipurile de serviciu precum
attachment/note/annotation, care nu sunt fișe bibliografice).
"""

from typing import Dict, List, Tuple

# (cheie Zotero API, nume afișat în română)
ITEM_TYPES: List[Tuple[str, str]] = [
    ("book",                "Carte"),
    ("bookSection",         "Capitol de carte"),
    ("journalArticle",      "Articol de jurnal"),
    ("conferencePaper",     "Lucrare de conferință"),
    ("thesis",              "Teză"),
    ("report",              "Raport"),
    ("preprint",            "Preprint"),
    ("manuscript",          "Manuscris"),
    ("document",            "Document"),
    ("artwork",             "Operă de artă"),
    ("audioRecording",      "Înregistrare audio"),
    ("bill",                "Proiect de lege"),
    ("blogPost",            "Articol de blog"),
    ("case",                "Caz juridic"),
    ("computerProgram",     "Program informatic"),
    ("dataset",             "Set de date"),
    ("dictionaryEntry",     "Articol de dicționar"),
    ("email",               "E-mail"),
    ("encyclopediaArticle", "Articol de enciclopedie"),
    ("film",                "Film"),
    ("forumPost",           "Postare de forum"),
    ("hearing",             "Audiere"),
    ("instantMessage",      "Mesaj instant"),
    ("interview",           "Interviu"),
    ("letter",              "Scrisoare"),
    ("magazineArticle",     "Articol de revistă"),
    ("map",                 "Hartă"),
    ("newspaperArticle",    "Articol de ziar"),
    ("patent",              "Brevet"),
    ("podcast",             "Podcast"),
    ("presentation",        "Prezentare"),
    ("radioBroadcast",      "Emisiune radio"),
    ("standard",            "Standard"),
    ("statute",             "Statut"),
    ("tvBroadcast",         "Emisiune TV"),
    ("videoRecording",      "Înregistrare video"),
    ("webpage",             "Pagină web"),
]

# Mapări de etichete vechi -> chei Zotero API
LEGACY_LABELS: Dict[str, str] = {
    "Book (Book)": "book",
    "Article (Article)": "journalArticle",
    "Chapter (Chapter)": "bookSection",
    "Thesis (Thesis)": "thesis",
}

# Nume englezești -> chei API (rezervă pentru răspunsurile AI și fișele salvate anterior)
_ENGLISH_NAMES: Dict[str, str] = {
    "book": "book", "book section": "bookSection", "journal article": "journalArticle",
    "conference paper": "conferencePaper", "thesis": "thesis", "report": "report",
    "preprint": "preprint", "manuscript": "manuscript", "document": "document",
    "artwork": "artwork", "audio recording": "audioRecording", "bill": "bill",
    "blog post": "blogPost", "case": "case", "computer program": "computerProgram",
    "dataset": "dataset", "dictionary entry": "dictionaryEntry", "email": "email",
    "encyclopedia article": "encyclopediaArticle", "film": "film",
    "forum post": "forumPost", "hearing": "hearing", "instant message": "instantMessage",
    "interview": "interview", "letter": "letter", "magazine article": "magazineArticle",
    "map": "map", "newspaper article": "newspaperArticle", "patent": "patent",
    "podcast": "podcast", "presentation": "presentation",
    "radio broadcast": "radioBroadcast", "standard": "standard", "statute": "statute",
    "tv broadcast": "tvBroadcast", "video recording": "videoRecording",
    "webpage": "webpage",
}

_KEY_TO_NAME: Dict[str, str] = dict(ITEM_TYPES)
_NAME_TO_KEY: Dict[str, str] = {name.lower(): key for key, name in ITEM_TYPES}
_NAME_TO_KEY.update(_ENGLISH_NAMES)


def type_label(key: str) -> str:
    """Eticheta canonică UI: 'Carte (book)'."""
    return f"{_KEY_TO_NAME.get(key, key)} ({key})"


def all_labels() -> List[str]:
    """Toate etichetele pentru lista derulantă de selectare a tipului de element."""
    return [type_label(k) for k, _ in ITEM_TYPES]


def type_key(label_or_key: str) -> str:
    """
    Normalizează eticheta sau cheia în cheia canonică Zotero API.
    Acceptă: 'book', 'Carte (book)', 'Carte', 'journalArticle'.
    """
    s = (label_or_key or "").strip()
    if s in _KEY_TO_NAME:
        return s
    if s in LEGACY_LABELS:
        return LEGACY_LABELS[s]
    s_lower = s.lower()
    if s_lower in _NAME_TO_KEY:
        return _NAME_TO_KEY[s_lower]
    if s.endswith(")") and "(" in s:
        inner = s.rsplit("(", 1)[1].rstrip(")").strip()
        if inner in _KEY_TO_NAME:
            return inner
    return "book"


def display_label(any_value: str) -> str:
    """Convertește orice reprezentare de tip în eticheta canonică UI."""
    return type_label(type_key(any_value))


# ------------------------------------------------------------------
# Schema de răspuns JSON așteptată de la etapa AI (TZ.md §5.1)
# ------------------------------------------------------------------
AI_OUTPUT_SCHEMA: Dict[str, str] = {
    "item_type": "una dintre cheile ITEM_TYPES: book, journalArticle, thesis...",
    "title": "titlul complet al documentului",
    "subtitle": "subtitlul, dacă există",
    "authors": "lista autorilor: ['Prenume Nume', ...]",
    "editors": "lista editorilor, dacă este specificată",
    "publisher": "numele editorului",
    "year": "anul publicării sau data completă",
    "city": "locul publicării",
    "edition": "numărul/descrierea ediției (ex. 'ed. a 4-a')",
    "publication_title": "revista / culegerea de conferință / cartea-părinte (pentru articole și capitole)",
    "series": "numele seriei editoriale",
    "series_number": "numărul seriei",
    "volume": "volumul",
    "issue": "numărul revistei (issue), ex. '2(44)'",
    "num_volumes": "numărul total de volume",
    "num_pages": "numărul total de pagini",
    "isbn": "ISBN-10/13 fără marcaje de validare",
    "issn": "ISSN pentru publicații periodice",
    "doi": "identificatorul DOI",
    "url": "URL-ul sursei",
    "language": "codul de limbă ISO 639-1/3: ron, eng, rus, fra, deu...",
    "abstract": "rezumatul din paginile de titlu, dacă este disponibil",
    "extra": ("metadate suplimentare fără câmp în Zotero — linie cu linie 'Nume: valoare': "
              "'CZU: ...', 'UDC: ...', 'Tiraj: ...', 'LBC: ...'"),
    "confidence": "0.0-1.0 încrederea modelului",
}
