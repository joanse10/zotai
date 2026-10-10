"""
Reunirea metadatelor din mai multe surse, cu prioritate explicită.

Ierarhia încrederii (de la cea mai mare):
  1. lookup   — registre bibliografice după DOI/ISBN (CrossRef, OpenAlex, OpenLibrary)
  2. web      — pagina sursă (DSpace, citation_* meta) când documentul a fost descărcat
  3. ai       — extragerea AI din textul documentului
  4. embedded — Info Dictionary / XMP deja prezente în fișier
  5. filename — numele fișierului (doar titlu, ultimă rezervă)

Regula: o sursă cu prioritate mai mare suprascrie una mai mică; o sursă mai
mică doar completează golurile. Titlul derivat din numele fișierului este un
„placeholder” — orice sursă reală îl înlocuiește.
"""

import re
from typing import Dict, Iterable, Optional

from gui.models import BookMetadata

# Câmpuri BookMetadata care pot fi completate din surse
_FIELDS = (
    "title", "subtitle", "short_title", "authors", "editors", "doc_type", "language",
    "abstract", "publisher", "year", "city", "edition", "publication_title", "series",
    "series_number", "volume", "issue", "num_volumes", "num_pages", "isbn", "issn",
    "doi", "url", "accessed", "citation_key", "archive", "loc_in_archive", "call_number",
    "library_catalog", "license", "extra",
)

from gui.models import iso639_1


def _has(v) -> bool:
    return v is not None and str(v).strip() not in ("", "—", "0.0", "und")


def norm_lang(v: str) -> str:
    """Orice cod (RON / ron / ro-MD / Română) -> ISO 639-1 afișat peste tot: „ro”, „en”, „ru”."""
    names = {"română": "ro", "romana": "ro", "romanian": "ro", "русский": "ru", "russian": "ru",
             "english": "en", "engleză": "en", "engleza": "en", "ukrainian": "uk", "français": "fr"}
    raw = (v or "").strip().lower()
    if raw in names:
        return names[raw]
    code = iso639_1(raw)
    return "" if code in ("und", "") else code


def filename_title(file_name: str) -> str:
    """„Dumitru_2023_Interventia-psihologica.pdf” -> „Dumitru 2023 Interventia psihologica”."""
    stem = re.sub(r"\.(pdf|docx?)$", "", file_name or "", flags=re.I)
    return re.sub(r"[_\-]+", " ", stem).strip()


def apply_source(meta: BookMetadata, fields: Dict, *, override: bool,
                 placeholder_title: str = "", skip: Iterable[str] = ()) -> int:
    """
    Aplică `fields` peste `meta`.
    override=True  -> suprascrie valorile existente (sursă mai de încredere)
    override=False -> doar completează golurile
    `placeholder_title` — titlul provizoriu (din numele fișierului), tratat ca gol.
    Returnează numărul de câmpuri modificate.
    """
    changed = 0
    skip = set(skip) | {"raw_json", "confidence", "_ids_only", "pdf_url", "item_type"}
    for k, v in (fields or {}).items():
        if k in skip or k not in _FIELDS:
            continue
        if isinstance(v, list):
            v = ", ".join(str(x) for x in v if str(x).strip())
        if not _has(v):
            continue
        v = str(v).strip()
        if k == "language":
            v = norm_lang(v)
        cur = str(getattr(meta, k, "") or "").strip()
        cur_is_placeholder = (k == "title" and placeholder_title and cur == placeholder_title)
        if override or not _has(cur) or cur_is_placeholder:
            if cur != v:
                setattr(meta, k, v)
                changed += 1
    return changed


def extra_merge(meta: BookMetadata, new_extra: str) -> None:
    """Liniile „Cheie: valoare” din Extra se reunesc fără duplicate."""
    lines = []
    seen = set()
    for src in (meta.extra or "", new_extra or ""):
        for line in re.split(r"[\n;]+", src):
            line = line.strip()
            key = line.split(":", 1)[0].strip().lower() if ":" in line else line.lower()
            if line and key not in seen:
                seen.add(key)
                lines.append(line)
    meta.extra = "\n".join(lines)


def heuristic_title(text: str) -> str:
    """
    Titlu de rezervă din primele linii ale paginii de titlu (fără AI):
    reunește liniile scurte de la început până la ~100 de caractere.
    Sare peste CZU/ISBN/ISSN/DOI, instituții și linii pur numerice.
    """
    skip = re.compile(r"^(czu|udc|удк|ббк|isbn|issn|doi|e-issn|http|www\.|universitatea|университет|"
                      r"ministerul|министерство|tip\b|nr\.?\s*\d|\d+[\s.,()-]*$)", re.I)
    parts = []
    for line in (text or "")[:2500].splitlines():
        line = re.sub(r"\s+", " ", line).strip(" -–—•·")
        if not line or len(line) < 3 or skip.search(line):
            if parts and not line:
                break
            continue
        parts.append(line)
        if sum(len(p) for p in parts) >= 60:
            break
    title = " ".join(parts).strip()
    if title.isupper():
        title = title.capitalize()
    return title[:160]


def finalize(meta: BookMetadata, *, file_name: str = "", detected_language: str = "",
             page_count: int = 0, text: str = "") -> None:
    """Rezerve finale: titlu din text/numele fișierului, limbă din detecție, pagini din PDF."""
    placeholder = filename_title(file_name)
    if not _has(meta.title) or meta.title == placeholder:
        meta.title = heuristic_title(text) or placeholder or "Document"
    if not _has(meta.language) and detected_language and detected_language != "UND":
        meta.language = norm_lang(detected_language)
    is_book_like = not any(k in (meta.doc_type or "").lower()
                           for k in ("article", "articol", "conference", "conferin", "section", "capitol"))
    if not _has(meta.num_pages) and page_count and is_book_like:
        meta.num_pages = str(page_count)
    # DOI/ISBN curate
    meta.doi = (meta.doi or "").replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
    meta.isbn = re.sub(r"[^0-9Xx]", "", meta.isbn or "").upper()


def known_facts(meta: BookMetadata, placeholder_title: str = "") -> Dict:
    """Câmpurile certe de transmis AI-ului drept context (fără placeholder-e)."""
    out = {}
    for k in ("title", "authors", "publisher", "year", "isbn", "issn", "doi",
              "publication_title", "volume", "issue", "num_pages", "doc_type"):
        v = getattr(meta, k, "")
        if _has(v) and not (k == "title" and v == placeholder_title):
            out[k] = v
    return out
