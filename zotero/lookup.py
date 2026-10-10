"""
Căutare online de metadate bibliografice fără AI.

Surse:
  - CrossRef REST API — DOI și căutare în text liber (api.crossref.org)
  - OpenLibrary API   — ISBN (openlibrary.org/isbn/{isbn}.json)
  - Google Books API  — rezervă pentru ISBN

Detectează tipul interogării (DOI / ISBN / URL / text), normalizează răspunsurile
în dicționar de câmpuri BookMetadata. Cereri de rețea prin httpx.
"""

import logging
import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

import httpx

log = logging.getLogger("zotai")

_TIMEOUT = 20.0
_UA = {"User-Agent": "Zotai/1.0 (mailto:zotai@local)"}

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)

# Capturează ISBN după cuvântul-cheie de etichetă
_ISBN_LABEL_RE = re.compile(r"ISBN[:\s]*([0-9Xx][0-9Xx\-\s]{8,24}[0-9Xx])", re.I)
# Rezervă: 13 cifre începând cu 978/979
_ISBN_BARE_RE = re.compile(r"\b97[89][\-\s0-9]{10,20}\d\b")


def _clean_isbn(raw: str) -> str:
    digits = re.sub(r"[^0-9Xx]", "", raw)
    return digits if len(digits) in (10, 13) else ""


def find_identifiers(text: str, max_chars: int = 8000) -> Dict[str, str]:
    """
    Găsește DOI și ISBN în antetul documentului / titlu / blocul CIP.
    Limitează la max_chars pentru a evita extragerea referințelor din bibliografie.
    """
    head = (text or "")[:max_chars]
    found: Dict[str, str] = {}
    m = _DOI_RE.search(head)
    if m:
        found["doi"] = m.group(0).rstrip(".")
    m = _ISBN_LABEL_RE.search(head) or _ISBN_BARE_RE.search(head)
    if m:
        isbn = _clean_isbn(m.group(1) if m.re is _ISBN_LABEL_RE else m.group(0))
        if isbn:
            found["isbn"] = isbn
    return found


def lookup_text_identifiers(text: str) -> Tuple[Optional[Dict], str]:
    """
    Găsește DOI/ISBN în textul documentului și returnează metadate exacte
    din CrossRef/OpenLibrary (similar cu „Retrieve Metadata" din Zotero).
    """
    ids = find_identifiers(text)
    if ids.get("doi"):
        fields, err = lookup_doi(ids["doi"])
        if fields:
            fields.setdefault("extra", "")
            log.info("Căutare după DOI %s: '%s'", ids["doi"], fields.get("title", "")[:60])
            return fields, ""
        log.info("DOI %s găsit în text, dar CrossRef a eșuat: %s", ids["doi"], err)
    if ids.get("isbn"):
        fields, err = lookup_isbn(ids["isbn"])
        if fields:
            log.info("Căutare după ISBN %s: '%s'", ids["isbn"], fields.get("title", "")[:60])
            return fields, ""
        log.info("ISBN %s găsit în text, dar căutarea a eșuat: %s", ids["isbn"], err)
    return None, ""


def detect_query_type(query: str) -> Tuple[str, str]:
    """
    Clasifică șirul de interogare de căutare.
    Returnează (tip, normalizat): 'doi' | 'isbn' | 'url_pdf' | 'url' | 'text'.
    """
    q = (query or "").strip()
    if not q:
        return "text", ""

    if q.lower().startswith(("http://", "https://")):
        if re.search(r"\.pdf(\?|#|$)", q, re.I):
            return "url_pdf", q
        if "doi.org/" in q:
            m = _DOI_RE.search(q)
            if m:
                return "doi", m.group(0).rstrip(".")
        return "url", q

    m = _DOI_RE.search(q)
    if m and (q.lower().startswith("doi") or q.startswith("10.")):
        return "doi", m.group(0).rstrip(".")

    digits = re.sub(r"[\-\s]", "", q)
    if re.fullmatch(r"\d{9}[\dXx]", digits) or re.fullmatch(r"97[89]\d{10}", digits):
        return "isbn", digits

    return "text", q


# ---------------------------------------------------------------------------
# Normalizare în câmpuri BookMetadata
# ---------------------------------------------------------------------------

def _crossref_to_fields(w: Dict) -> Dict:
    """CrossRef work -> dicționar de câmpuri BookMetadata."""
    authors = [f"{a.get('family', '')} {a.get('given', '')}".strip()
               for a in w.get("author", [])]
    editors = [f"{a.get('family', '')} {a.get('given', '')}".strip()
               for a in w.get("editor", [])]

    year = ""
    for key in ("published-print", "published-online", "issued", "published"):
        parts = (w.get(key) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break

    ctype = (w.get("type") or "").lower()
    item_type = {
        "journal-article": "journalArticle",
        "book-chapter": "bookSection",
        "book": "book",
        "monograph": "book",
        "proceedings-article": "conferencePaper",
        "proceedings": "book",
        "report": "report",
        "dissertation": "thesis",
        "dataset": "dataset",
        "posted-content": "preprint",
        "reference-book": "book",
    }.get(ctype, "journalArticle" if ctype.startswith("journal") else "book")

    title = (w.get("title") or [""])[0]
    subtitle = (w.get("subtitle") or [""])[0]
    container = (w.get("container-title") or [""])[0]
    issns = w.get("ISSN") or []

    return {
        "item_type": item_type,
        "title": title,
        "subtitle": subtitle,
        "authors": authors,
        "editors": editors,
        "publisher": w.get("publisher", ""),
        "year": year,
        "city": "",
        "edition": w.get("edition-number", ""),
        "series": "",
        "series_number": "",
        "volume": w.get("volume", ""),
        "num_volumes": "",
        "num_pages": str(w.get("page", "") or ""),
        "isbn": (w.get("ISBN") or [""])[0],
        "issn": issns[0] if issns else "",
        "doi": w.get("DOI", ""),
        "url": w.get("URL", ""),
        "language": (w.get("language") or "").upper(),
        "abstract": re.sub(r"<[^>]+>", "", w.get("abstract", "")),
        "extra": (f"Journal: {container}" if container else ""),
        "confidence": 1.0,
    }


def _openlib_to_fields(b: Dict, isbn: str) -> Dict:
    """Carte OpenLibrary -> dicționar de câmpuri BookMetadata."""
    authors = [a.get("name", "") for a in b.get("authors", [])]
    authors = [a for a in authors if a]
    year = (b.get("publish_date") or "")
    m = re.search(r"\d{4}", year)
    return {
        "item_type": "book",
        "title": b.get("title", ""),
        "subtitle": b.get("subtitle", ""),
        "authors": authors,
        "editors": [],
        "publisher": ", ".join(b.get("publishers", [])),
        "year": m.group(0) if m else year,
        "city": ", ".join(b.get("publish_places", [])),
        "edition": "",
        "series": "",
        "series_number": "",
        "volume": "",
        "num_volumes": "",
        "num_pages": str(b.get("number_of_pages", "") or ""),
        "isbn": isbn,
        "issn": "",
        "doi": "",
        "url": b.get("url", f"https://openlibrary.org/isbn/{isbn}"),
        "language": "",
        "abstract": "",
        "extra": "",
        "confidence": 1.0,
    }


# ---------------------------------------------------------------------------
# API public
# ---------------------------------------------------------------------------

def _datacite_to_fields(a: Dict) -> Dict:
    """Atribute DataCite -> dicționar de câmpuri BookMetadata."""
    titles = a.get("titles") or [{}]
    creators = []
    for c in a.get("creators", []):
        name = (c.get("name") or "").strip()
        if not name and c.get("familyName"):
            name = f"{c.get('givenName', '')} {c['familyName']}".strip()
        if name:
            creators.append(name)

    dtype = (a.get("types") or {}).get("resourceTypeGeneral", "")
    item_type = {
        "JournalArticle": "journalArticle", "Book": "book",
        "BookChapter": "bookSection", "ConferencePaper": "conferencePaper",
        "Dataset": "dataset", "Preprint": "preprint", "Report": "report",
        "Dissertation": "thesis", "Text": "book",
    }.get(dtype, "journalArticle" if "journal" in dtype.lower() else "book")

    descs = a.get("descriptions") or []
    abstract = next((d.get("description", "") for d in descs
                     if d.get("descriptionType") == "Abstract"), "")
    related = [i.get("relatedIdentifier", "") for i in a.get("relatedIdentifiers", [])]
    issn = next((i.get("relatedIdentifier", "") for i in a.get("relatedIdentifiers", [])
                 if i.get("relatedIdentifierType") == "ISSN"), "")

    return {
        "item_type": item_type,
        "title": titles[0].get("title", ""),
        "subtitle": "",
        "authors": creators,
        "editors": [],
        "publisher": a.get("publisher", ""),
        "year": str(a.get("publicationYear") or ""),
        "city": "",
        "edition": "",
        "series": (a.get("container") or {}).get("title", ""),
        "series_number": "",
        "volume": (a.get("container") or {}).get("volume", ""),
        "num_volumes": "",
        "num_pages": "",
        "isbn": "",
        "issn": issn,
        "doi": a.get("doi", ""),
        "url": a.get("url", ""),
        "language": (a.get("language") or "").upper(),
        "abstract": abstract,
        "extra": "",
        "confidence": 1.0,
    }


def _lookup_doi_datacite(doi: str) -> Tuple[Optional[Dict], str]:
    """Rezervă pentru DOI-urile înregistrate la DataCite (Zenodo, OSF, repositorii)."""
    try:
        r = httpx.get(f"https://api.datacite.org/dois/{doi}",
                      headers=_UA, timeout=_TIMEOUT)
        if r.status_code == 404:
            return None, ""
        r.raise_for_status()
        attrs = (r.json().get("data") or {}).get("attributes") or {}
        if not attrs.get("titles"):
            return None, ""
        return _datacite_to_fields(attrs), ""
    except Exception:
        return None, ""


def lookup_doi(doi: str) -> Tuple[Optional[Dict], str]:
    """DOI -> metadate prin CrossRef (cu rezervă DataCite)."""
    try:
        r = httpx.get(f"https://api.crossref.org/works/{doi}",
                      headers=_UA, timeout=_TIMEOUT, follow_redirects=True)
        if r.status_code == 404:
            fields, _ = _lookup_doi_datacite(doi)
            if fields:
                return fields, ""
            return None, f"DOI neînregistrat (CrossRef + DataCite): {doi}"
        r.raise_for_status()
        return _crossref_to_fields(r.json()["message"]), ""
    except httpx.HTTPError as e:
        return None, f"Cererea CrossRef a eșuat: {e}"
    except Exception as e:
        return None, f"Nu s-a putut analiza răspunsul CrossRef: {e}"


def search_web_pdf(query: str, api_key: str) -> Tuple[Optional[str], str]:
    """
    Rezervă web (Brave Search API) pentru DOI/ISBN neînregistrate:
    caută `"{query}" filetype:pdf` și returnează primul URL de PDF găsit.
    Necesită cheie gratuită de la https://brave.com/search/api/ (~2000 cereri/lună).
    """
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": f'"{query}" filetype:pdf', "count": 10},
            headers={**_UA, "X-Subscription-Token": api_key,
                     "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        results = (r.json().get("web") or {}).get("results", [])
        pdf = next((res.get("url") for res in results
                    if ".pdf" in (res.get("url") or "").lower()), None)
        return pdf, ""
    except httpx.HTTPError as e:
        return None, f"Căutarea web a eșuat: {e}"


def search_crossref(query: str, rows: int = 6) -> Tuple[List[Dict], str]:
    """Căutare în text liber după titlu — returnează lista de candidați."""
    try:
        r = httpx.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": rows},
            headers=_UA, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        items = r.json()["message"].get("items", [])
        return [_crossref_to_fields(w) for w in items], ""
    except Exception as e:
        return [], f"Căutarea CrossRef a eșuat: {e}"


def lookup_isbn(isbn: str) -> Tuple[Optional[Dict], str]:
    """ISBN -> metadate (OpenLibrary cu rezervă Google Books)."""
    try:
        r = httpx.get(f"https://openlibrary.org/isbn/{isbn}.json",
                      headers=_UA, timeout=_TIMEOUT, follow_redirects=True)
        if r.status_code == 200:
            data = r.json()
            for a in data.get("authors", []):
                key = a.get("key")
                if key and not a.get("name"):
                    try:
                        ar = httpx.get(f"https://openlibrary.org{key}.json",
                                       headers=_UA, timeout=10.0)
                        if ar.status_code == 200:
                            a["name"] = ar.json().get("name", "")
                    except Exception:
                        pass
            return _openlib_to_fields(data, isbn), ""
    except httpx.HTTPError as e:
        log.warning("OpenLibrary inaccesibil: %s", e)

    # Rezervă Google Books
    try:
        r = httpx.get("https://www.googleapis.com/books/v1/volumes",
                      params={"q": f"isbn:{isbn}"}, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return None, f"ISBN negăsit: {isbn}"
        v = items[0].get("volumeInfo", {})
        ids = {i.get("type"): i.get("identifier") for i in v.get("industryIdentifiers", [])}
        return {
            "item_type": "book",
            "title": v.get("title", ""),
            "subtitle": v.get("subtitle", ""),
            "authors": v.get("authors", []),
            "editors": [],
            "publisher": v.get("publisher", ""),
            "year": (re.search(r"\d{4}", v.get("publishedDate", "") or "") or [""])[0]
                    if re.search(r"\d{4}", v.get("publishedDate", "") or "") else "",
            "city": "", "edition": "", "series": "", "series_number": "",
            "volume": "", "num_volumes": "",
            "num_pages": str(v.get("pageCount", "") or ""),
            "isbn": ids.get("ISBN_13") or ids.get("ISBN_10") or isbn,
            "issn": "", "doi": "",
            "url": v.get("infoLink", ""),
            "language": (v.get("language") or "").upper(),
            "abstract": v.get("description", ""),
            "extra": "", "confidence": 1.0,
        }, ""
    except Exception as e:
        return None, f"ISBN negăsit în OpenLibrary sau Google Books: {e}"


def download_pdf(url: str, dest_dir: str) -> Tuple[Optional[str], str]:
    """
    Descarcă PDF de la un URL direct în dest_dir.
    Returnează (cale | None, eroare).
    """
    try:
        os.makedirs(dest_dir, exist_ok=True)
        fname = os.path.basename(url.split("?")[0].split("#")[0]) or "document.pdf"
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        dest = os.path.join(dest_dir, fname)
        with httpx.stream("GET", url, headers=_UA, timeout=60.0,
                          follow_redirects=True) as r:
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if "pdf" not in ctype.lower() and not url.lower().endswith(".pdf"):
                return None, f"Linkul nu indică un PDF (Content-Type: {ctype})"
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    f.write(chunk)
        if os.path.getsize(dest) < 512:
            os.remove(dest)
            return None, "Fișierul descărcat este prea mic — probabil nu este un PDF valid"
        return os.path.normpath(dest), ""
    except Exception as e:
        return None, f"Eroare la descărcare: {e}"
