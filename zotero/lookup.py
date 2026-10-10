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
# DOI „rupt” de stratul de text al PDF-ului: „10.36120/2587-3636.v 44i2” / „doi: 10.1234/\nabc”
_DOI_LOOSE_RE = re.compile(r"10\.\d{4,9}/(?:[-._;()/:A-Za-z0-9]|[ \t\r\n](?=[-._A-Za-z0-9])){4,80}", re.I)

# Capturează ISBN după cuvântul-cheie de etichetă
_ISBN_LABEL_RE = re.compile(r"ISBN[-\s]*(?:1[03])?[:\s]*([0-9Xx][0-9Xx\-\s–]{8,24}[0-9Xx])", re.I)
# Rezervă: 13 cifre începând cu 978/979
_ISBN_BARE_RE = re.compile(r"\b97[89][\-\s–0-9]{10,20}\d\b")

_DOI_TRAIL = ".,;:)]}>\"'"


def _clean_isbn(raw: str) -> str:
    digits = re.sub(r"[^0-9Xx]", "", raw)
    return digits.upper() if len(digits) in (10, 13) else ""


def _isbn_valid(isbn: str) -> bool:
    """Suma de control ISBN-10 / ISBN-13 — elimină numerele de telefon și CZU-urile."""
    if len(isbn) == 13 and isbn.isdigit():
        s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn))
        return s % 10 == 0
    if len(isbn) == 10:
        try:
            s = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
        except ValueError:
            return False
        return s % 11 == 0
    return False


def normalize_isbn(raw: str) -> str:
    """„978-5-86654-577-3” -> „9785866545773”; șir gol dacă nu trece suma de control."""
    isbn = _clean_isbn(raw or "")
    return isbn if isbn and _isbn_valid(isbn) else ""


_DOI_GAP_RE = re.compile(r"^[ \t]{1,2}([A-Za-z0-9][-._A-Za-z0-9]{0,24})")


def _doi_candidates(head: str) -> List[str]:
    """
    Toate DOI-urile din antet, în ordinea apariției. Stratul de text al PDF-ului
    rupe adesea DOI-ul printr-un spațiu („…v 44i2”), de aceea pentru fiecare
    potrivire strictă încercăm și varianta lipită cu următorul token de pe linie.
    """
    seen, out = set(), []

    def _add(c: str):
        c = c.rstrip(_DOI_TRAIL)
        if len(c) > 8 and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)

    for m in _DOI_RE.finditer(head):
        strict = m.group(0)
        gap = _DOI_GAP_RE.match(head[m.end():m.end() + 30])
        # Lipim doar continuări plauzibile: fără sfârșit de propoziție înainte,
        # token care începe cu cifră/minusculă (nu „Ref”, „ISBN”, „http”)
        if gap and strict[-1] not in _DOI_TRAIL and (gap.group(1)[0].isdigit() or gap.group(1)[0].islower()) \
                and not gap.group(1).lower().startswith(("isbn", "issn", "http", "www")):
            _add(strict + gap.group(1))
        _add(strict)
    return out


def find_identifiers(text: str, max_chars: int = 12000) -> Dict[str, str]:
    """
    Găsește DOI și ISBN în antetul documentului / titlu / blocul CIP.
    Limitează la max_chars pentru a evita extragerea referințelor din bibliografie.
    `doi_candidates` conține toate variantele — verificate pe rând la CrossRef.
    """
    head = (text or "")[:max_chars]
    found: Dict[str, str] = {}
    cands = _doi_candidates(head)
    if cands:
        found["doi"] = cands[0]
        found["doi_candidates"] = cands  # type: ignore[assignment]
    for m in list(_ISBN_LABEL_RE.finditer(head)) + list(_ISBN_BARE_RE.finditer(head)):
        isbn = normalize_isbn(m.group(1) if m.re is _ISBN_LABEL_RE else m.group(0))
        if isbn:
            found["isbn"] = isbn
            break
    m = re.search(r"(?<![EeOo]-)\bISSN[:\s]*(\d{4}[-‐–]\s?\d{3}[\dXx])", head)
    if m:
        found["issn"] = re.sub(r"[^0-9Xx]", "", m.group(1)).upper()
        found["issn"] = found["issn"][:4] + "-" + found["issn"][4:]
    return found


def lookup_text_identifiers(text: str) -> Tuple[Optional[Dict], str]:
    """
    Găsește DOI/ISBN în textul documentului și returnează metadate exacte
    din CrossRef/DataCite/OpenAlex/OpenLibrary (similar cu „Retrieve Metadata" din Zotero).
    Încearcă toate variantele de DOI (textul PDF rupe adesea identificatorul).
    """
    ids = find_identifiers(text)
    last_err = ""
    for doi in ids.get("doi_candidates", [])[:4]:
        fields, err = lookup_doi(doi)
        if fields:
            fields.setdefault("extra", "")
            log.info("Căutare după DOI %s: '%s'", doi, fields.get("title", "")[:60])
            if ids.get("isbn") and not fields.get("isbn"):
                fields["isbn"] = ids["isbn"]
            return fields, ""
        last_err = err
    if ids.get("doi"):
        log.info("DOI %s găsit în text, dar niciun registru nu-l cunoaște: %s", ids["doi"], last_err)
    if ids.get("isbn"):
        fields, err = lookup_isbn(ids["isbn"])
        if fields:
            log.info("Căutare după ISBN %s: '%s'", ids["isbn"], fields.get("title", "")[:60])
            if ids.get("doi") and not fields.get("doi"):
                fields["doi"] = ids["doi"]
            return fields, ""
        log.info("ISBN %s găsit în text, dar căutarea a eșuat: %s", ids["isbn"], err)
    # Identificatorii găsiți rămân utili chiar fără metadate online
    if ids.get("doi") or ids.get("isbn") or ids.get("issn"):
        return {"doi": ids.get("doi", ""), "isbn": ids.get("isbn", ""),
                "issn": ids.get("issn", ""), "confidence": 0.6, "_ids_only": True}, ""
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
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip()
               for a in w.get("author", [])]
    editors = [f"{a.get('given', '')} {a.get('family', '')}".strip()
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
    event_name = (w.get("event") or {}).get("name", "")
    is_proceedings = ctype in ("proceedings-article", "book-chapter")
    landing_url = (w.get("resource") or {}).get("primary", {}).get("URL", "")

    extra_parts = []
    if event_name and event_name != container:
        extra_parts.append(f"Conferință: {event_name}")
    orcids = [f"ORCID ({a.get('family', '')}): {a['ORCID'].rsplit('/', 1)[-1]}"
              for a in w.get("author", []) if a.get("ORCID")]
    extra_parts.extend(orcids)
    pdf_url = next((l.get("URL") for l in (w.get("link") or [])
                    if "pdf" in (l.get("content-type") or "").lower()), "")

    return {
        "item_type": item_type,
        "title": title,
        "subtitle": subtitle,
        "authors": authors,
        "editors": editors,
        "publisher": w.get("publisher", ""),
        "year": year,
        "city": (w.get("publisher-location") or ""),
        "edition": w.get("edition-number", ""),
        "publication_title": container,
        "series": "",
        "series_number": "",
        "volume": w.get("volume", ""),
        "issue": w.get("issue", "") or w.get("journal-issue", {}).get("issue", ""),
        "num_volumes": "",
        "num_pages": str(w.get("page", "") or ""),
        "isbn": normalize_isbn((w.get("ISBN") or [""])[0]),
        "issn": issns[0] if issns else "",
        "doi": w.get("DOI", ""),
        "url": landing_url or w.get("URL", ""),
        "language": (w.get("language") or "").upper(),
        "abstract": re.sub(r"<[^>]+>", "", w.get("abstract", "")).strip(),
        "extra": "\n".join(extra_parts),
        "pdf_url": pdf_url,
        "confidence": 1.0,
    }


def _parent_isbn(doi: str) -> str:
    """
    ISBN-ul culegerii (proceedings) stă pe DOI-ul părinte, nu pe articol:
    încercăm tăierea ultimului segment (ex. „…v44i2.p280-284” -> „…v44i2”).
    """
    parent = doi.rsplit(".", 1)[0] if "." in doi.split("/", 1)[-1] else ""
    if not parent or parent == doi:
        return ""
    try:
        r = httpx.get(f"https://api.crossref.org/works/{parent}",
                      headers=_UA, timeout=_TIMEOUT)
        if r.status_code != 200:
            return ""
        return (r.json()["message"].get("ISBN") or [""])[0]
    except Exception:
        return ""


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


def _openalex_abstract(inv: Optional[Dict]) -> str:
    """OpenAlex stochează rezumatul ca index inversat {cuvânt: [poziții]}."""
    if not inv:
        return ""
    words = sorted(((p, w) for w, ps in inv.items() for p in ps))
    return " ".join(w for _, w in words)


def _openalex_to_fields(w: Dict) -> Dict:
    """OpenAlex work -> câmpuri BookMetadata (rezumat, revistă, OA-PDF, ORCID)."""
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    oa = w.get("open_access") or {}
    bib = w.get("biblio") or {}
    authors = [(a.get("author") or {}).get("display_name", "")
               for a in w.get("authorships", [])]
    item_type = {
        "article": "journalArticle", "book": "book", "book-chapter": "bookSection",
        "dissertation": "thesis", "report": "report", "preprint": "preprint",
        "proceedings-article": "conferencePaper", "dataset": "dataset",
    }.get((w.get("type") or "").lower(), "journalArticle")
    pages = ""
    if bib.get("first_page"):
        pages = bib["first_page"] + (f"-{bib['last_page']}" if bib.get("last_page") else "")
    return {
        "item_type": item_type,
        "title": w.get("title") or w.get("display_name") or "",
        "subtitle": "", "editors": [],
        "authors": [a for a in authors if a],
        "publisher": src.get("host_organization_name", "") or "",
        "year": str(w.get("publication_year") or ""),
        "city": "", "edition": "", "series": "", "series_number": "",
        "publication_title": src.get("display_name", "") or "",
        "volume": bib.get("volume", "") or "",
        "issue": bib.get("issue", "") or "",
        "num_volumes": "", "num_pages": pages,
        "isbn": "", "issn": (src.get("issn_l") or ""),
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "url": loc.get("landing_page_url", "") or "",
        "language": (w.get("language") or "").upper(),
        "abstract": _openalex_abstract(w.get("abstract_inverted_index")),
        "extra": "",
        "pdf_url": oa.get("oa_url") or loc.get("pdf_url") or "",
        "confidence": 0.95,
    }


def lookup_openalex(doi: str) -> Optional[Dict]:
    """OpenAlex — indexează mai larg decât CrossRef și oferă rezumat + OA PDF."""
    try:
        r = httpx.get(f"https://api.openalex.org/works/https://doi.org/{doi}",
                      params={"mailto": "zotai@local"}, headers=_UA, timeout=_TIMEOUT)
        if r.status_code != 200:
            return None
        return _openalex_to_fields(r.json())
    except Exception:
        return None


def merge_fields(primary: Dict, secondary: Optional[Dict]) -> Dict:
    """Completează câmpurile goale din `primary` cu valorile din `secondary`."""
    if not secondary:
        return primary
    out = dict(primary)
    for k, v in secondary.items():
        cur = out.get(k)
        empty = cur is None or (isinstance(cur, (str, list)) and not cur)
        if empty and v not in (None, "", []):
            out[k] = v
    return out


def lookup_doi(doi: str) -> Tuple[Optional[Dict], str]:
    """
    DOI -> metadate: CrossRef (autoritativ) + OpenAlex (rezumat, revistă, OA-PDF),
    cu rezervă DataCite. Rezultatul este reuniunea surselor.
    """
    try:
        r = httpx.get(f"https://api.crossref.org/works/{doi}",
                      headers=_UA, timeout=_TIMEOUT, follow_redirects=True)
        if r.status_code == 404:
            fields, _ = _lookup_doi_datacite(doi)
            if not fields:
                fields = lookup_openalex(doi)
            if fields:
                return fields, ""
            return None, f"DOI neînregistrat (CrossRef + DataCite + OpenAlex): {doi}"
        r.raise_for_status()
        fields = _crossref_to_fields(r.json()["message"])
        fields = merge_fields(fields, lookup_openalex(doi))
        if not fields.get("isbn") and fields.get("item_type") in ("conferencePaper", "bookSection"):
            parent_isbn = _parent_isbn(doi)
            if parent_isbn:
                fields["isbn"] = parent_isbn
        return fields, ""
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


def _safe_filename(name: str, limit: int = 80) -> str:
    name = re.sub(r"[\\/:*?\"<>|\r\n]+", " ", name or "").strip(" .")
    name = re.sub(r"\s+", " ", name)
    return name[:limit].strip() or "document"


def download_pdf(url: str, dest_dir: str, preferred_name: str = "") -> Tuple[Optional[str], str]:
    """
    Descarcă PDF de la un URL (inclusiv bitstream-uri DSpace / linkuri fără extensie).
    Validează după Content-Type sau semnătura %PDF. Returnează (cale | None, eroare).
    """
    try:
        os.makedirs(dest_dir, exist_ok=True)
        base = _safe_filename(preferred_name) if preferred_name else \
            _safe_filename(os.path.basename(url.split("?")[0].split("#")[0]).rsplit(".", 1)[0])
        dest = os.path.join(dest_dir, base + ".pdf")
        n = 1
        while os.path.exists(dest):
            n += 1
            dest = os.path.join(dest_dir, f"{base} ({n}).pdf")
        headers = {**_UA, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zotai/1.0",
                   "Accept": "application/pdf,*/*"}
        with httpx.stream("GET", url, headers=headers, timeout=90.0,
                          follow_redirects=True) as r:
            r.raise_for_status()
            ctype = (r.headers.get("content-type") or "").lower()
            it = r.iter_bytes(1 << 16)
            first = next(it, b"")
            if not first.lstrip().startswith(b"%PDF") and "pdf" not in ctype:
                return None, f"Linkul nu indică un PDF (Content-Type: {ctype or 'necunoscut'})"
            with open(dest, "wb") as f:
                f.write(first)
                for chunk in it:
                    f.write(chunk)
        if os.path.getsize(dest) < 512:
            os.remove(dest)
            return None, "Fișierul descărcat este prea mic — probabil nu este un PDF valid"
        return os.path.normpath(dest), ""
    except Exception as e:
        return None, f"Eroare la descărcare: {e}"
