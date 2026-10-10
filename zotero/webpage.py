"""
Rezolvarea unei pagini web într-o fișă bibliografică + link către PDF.

Strategie (în ordinea încrederii), rezultatele se reunesc:
  1. DOI în URL / în pagină         -> registre (CrossRef/OpenAlex/DataCite)
  2. DSpace (repozitorii universitare, /handle/…) -> REST API /server/api
     (metadate Dublin Core complete + bitstream-ul PDF original)
  3. Etichete <meta> Highwire/Google Scholar (citation_*) — OJS, Springer,
     Elsevier, arXiv etc.; Dublin Core (DC.*); Open Graph
  4. JSON-LD (schema.org ScholarlyArticle / Book)
  5. ISBN în pagină                  -> OpenLibrary / Google Books

Returnează (fields, pdf_url, err). `fields` este dicționarul BookMetadata
(aceleași chei ca zotero.lookup), `pdf_url` — link direct de descărcat.
"""

import html
import json
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from zotero.lookup import (_DOI_RE, _UA, lookup_doi, lookup_isbn,
                           merge_fields, normalize_isbn)

log = logging.getLogger("zotai")

_BROWSER_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"),
               "Accept-Language": "ro,ru;q=0.8,en;q=0.6"}
_TIMEOUT = 20.0

_META_RE = re.compile(
    r"<meta\s+[^>]*?(?:name|property)\s*=\s*[\"']([^\"']+)[\"'][^>]*?content\s*=\s*[\"']([^\"']*)[\"']"
    r"|<meta\s+[^>]*?content\s*=\s*[\"']([^\"']*)[\"'][^>]*?(?:name|property)\s*=\s*[\"']([^\"']+)[\"']",
    re.I | re.S)
_JSONLD_RE = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.I | re.S)
_PDF_LINK_RE = re.compile(r"href\s*=\s*[\"']([^\"']+\.pdf(?:\?[^\"']*)?)[\"']", re.I)
_HANDLE_RE = re.compile(r"/handle/(\d+(?:\.\d+)?/\d+)")


def _empty_fields(item_type: str = "webpage") -> Dict:
    return {"item_type": item_type, "title": "", "subtitle": "", "authors": [], "editors": [],
            "publisher": "", "year": "", "city": "", "edition": "", "publication_title": "",
            "series": "", "series_number": "", "volume": "", "issue": "", "num_volumes": "",
            "num_pages": "", "isbn": "", "issn": "", "doi": "", "url": "", "language": "",
            "abstract": "", "extra": "", "confidence": 0.8}


def _fetch(url: str) -> Tuple[Optional[httpx.Response], str]:
    try:
        r = httpx.get(url, headers=_BROWSER_UA, timeout=_TIMEOUT, follow_redirects=True)
        if r.status_code == 403:
            return None, "Site-ul blochează accesul automat (403)"
        r.raise_for_status()
        return r, ""
    except httpx.HTTPError as e:
        return None, f"Pagina nu a putut fi descărcată: {e}"


def _parse_meta(page: str) -> Dict[str, List[str]]:
    """Toate etichetele <meta name/property=… content=…> grupate pe nume (lowercase)."""
    out: Dict[str, List[str]] = {}
    for m in _META_RE.finditer(page):
        name, content = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if name and content:
            out.setdefault(name.strip().lower(), []).append(html.unescape(content.strip()))
    return out


def _first(meta: Dict[str, List[str]], *names: str) -> str:
    for n in names:
        if meta.get(n.lower()):
            return meta[n.lower()][0]
    return ""


def _year(s: str) -> str:
    m = re.search(r"(1[5-9]|20)\d{2}", s or "")
    return m.group(0) if m else ""


# ---------------------------------------------------------------------------
# 2. DSpace REST (DSpace 7 Angular UI nu are metadate în HTML)
# ---------------------------------------------------------------------------

def _dspace_fields(url: str) -> Tuple[Optional[Dict], str]:
    m = _HANDLE_RE.search(url)
    if not m:
        return None, ""
    handle = m.group(1)
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    for api in (f"{base}/server/api", f"{base}/rest/api", f"{base}/api"):
        try:
            r = httpx.get(f"{api}/pid/find", params={"id": handle},
                          headers=_BROWSER_UA, timeout=_TIMEOUT, follow_redirects=True)
            if r.status_code != 200:
                continue
            item = r.json()
            md = item.get("metadata") or {}

            def vals(key: str) -> List[str]:
                return [v.get("value", "") for v in md.get(key, []) if v.get("value")]

            def one(*keys: str) -> str:
                for k in keys:
                    v = vals(k)
                    if v:
                        return v[0]
                return ""

            dtype = one("dc.type").lower()
            item_type = ("journalArticle" if "article" in dtype else
                         "thesis" if "thesis" in dtype or "disserta" in dtype else
                         "conferencePaper" if "conference" in dtype else
                         "bookSection" if "chapter" in dtype else
                         "book" if "book" in dtype else "report" if "report" in dtype else "document")
            f = _empty_fields(item_type)
            f.update({
                "title": one("dc.title"),
                "authors": [a.strip() for a in vals("dc.contributor.author")],
                "editors": [a.strip() for a in vals("dc.contributor.editor")],
                "publisher": one("dc.publisher"),
                "year": _year(one("dc.date.issued", "dc.date")),
                "isbn": normalize_isbn(one("dc.identifier.isbn")),
                "issn": one("dc.identifier.issn"),
                "doi": one("dc.identifier.doi").replace("https://doi.org/", ""),
                "url": one("dc.identifier.uri") or url,
                "language": one("dc.language.iso", "dc.language").upper(),
                "abstract": one("dc.description.abstract"),
                "publication_title": one("dc.relation.ispartof", "dc.source"),
                "extra": "\n".join(filter(None, [
                    f"Citație: {one('dc.identifier.citation')}" if one("dc.identifier.citation") else "",
                    f"Cuvinte-cheie: {', '.join(vals('dc.subject'))}" if vals("dc.subject") else "",
                ])),
                "confidence": 0.95,
            })
            # Bitstream-ul PDF original
            pdf_url = ""
            try:
                bundles = (item.get("_links") or {}).get("bundles", {}).get("href")
                if bundles:
                    br = httpx.get(bundles, headers=_BROWSER_UA, timeout=_TIMEOUT).json()
                    for b in (br.get("_embedded") or {}).get("bundles", []):
                        if b.get("name") != "ORIGINAL":
                            continue
                        bs = httpx.get(b["_links"]["bitstreams"]["href"],
                                       headers=_BROWSER_UA, timeout=_TIMEOUT).json()
                        for s in (bs.get("_embedded") or {}).get("bitstreams", []):
                            if (s.get("name") or "").lower().endswith(".pdf"):
                                pdf_url = s["_links"]["content"]["href"]
                                break
            except Exception as e:
                log.debug("DSpace bitstreams: %s", e)
            f["pdf_url"] = pdf_url
            return f, ""
        except Exception:
            continue
    return None, ""


# ---------------------------------------------------------------------------
# 3-4. HTML: citation_* / DC.* / Open Graph / JSON-LD
# ---------------------------------------------------------------------------

def _jsonld_fields(page: str) -> Optional[Dict]:
    for m in _JSONLD_RE.finditer(page):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and "@graph" in data:
            nodes = data["@graph"]
        for n in nodes:
            if not isinstance(n, dict):
                continue
            t = str(n.get("@type", "")).lower()
            if not any(k in t for k in ("article", "book", "thesis", "report", "creativework", "chapter")):
                continue
            item_type = ("book" if "book" == t else "bookSection" if "chapter" in t else
                         "thesis" if "thesis" in t else "journalArticle")
            f = _empty_fields(item_type)

            def names(v) -> List[str]:
                if not v:
                    return []
                v = v if isinstance(v, list) else [v]
                return [x.get("name", "") if isinstance(x, dict) else str(x) for x in v if x]

            part = n.get("isPartOf") or {}
            f.update({
                "title": n.get("headline") or n.get("name") or "",
                "authors": names(n.get("author")),
                "editors": names(n.get("editor")),
                "publisher": (n.get("publisher") or {}).get("name", "") if isinstance(n.get("publisher"), dict) else str(n.get("publisher") or ""),
                "year": _year(str(n.get("datePublished") or "")),
                "doi": _DOI_RE.search(str(n.get("sameAs") or n.get("identifier") or "")).group(0)
                       if _DOI_RE.search(str(n.get("sameAs") or n.get("identifier") or "")) else "",
                "isbn": normalize_isbn(str(n.get("isbn") or "")),
                "url": n.get("url") or "",
                "language": str(n.get("inLanguage") or "").upper(),
                "abstract": n.get("abstract") or n.get("description") or "",
                "publication_title": part.get("name", "") if isinstance(part, dict) else "",
                "num_pages": n.get("pagination") or "",
            })
            return f
    return None


def _html_fields(page: str, url: str) -> Tuple[Optional[Dict], str]:
    meta = _parse_meta(page)
    f = None
    if any(k.startswith("citation_") for k in meta):
        ctype = _first(meta, "citation_type", "dc.type").lower()
        item_type = ("thesis" if "thesis" in ctype or meta.get("citation_dissertation_institution") else
                     "conferencePaper" if meta.get("citation_conference_title") else
                     "book" if meta.get("citation_isbn") and not meta.get("citation_journal_title") else
                     "journalArticle")
        f = _empty_fields(item_type)
        f.update({
            "title": _first(meta, "citation_title"),
            "authors": meta.get("citation_author", []),
            "publisher": _first(meta, "citation_publisher", "citation_dissertation_institution", "dc.publisher"),
            "year": _year(_first(meta, "citation_publication_date", "citation_date", "citation_online_date", "citation_year")),
            "publication_title": _first(meta, "citation_journal_title", "citation_conference_title", "citation_book_title", "citation_inbook_title"),
            "volume": _first(meta, "citation_volume"),
            "issue": _first(meta, "citation_issue"),
            "num_pages": (f"{_first(meta, 'citation_firstpage')}-{_first(meta, 'citation_lastpage')}".strip("-")),
            "isbn": normalize_isbn(_first(meta, "citation_isbn")),
            "issn": _first(meta, "citation_issn"),
            "doi": _first(meta, "citation_doi").replace("https://doi.org/", ""),
            "url": _first(meta, "citation_abstract_html_url", "citation_fulltext_html_url") or url,
            "language": _first(meta, "citation_language", "dc.language").upper(),
            "abstract": _first(meta, "citation_abstract", "dc.description", "description", "og:description"),
            "extra": ("Cuvinte-cheie: " + "; ".join(meta.get("citation_keywords", [])))
                     if meta.get("citation_keywords") else "",
            "confidence": 0.9,
        })
        f["pdf_url"] = _first(meta, "citation_pdf_url")
    elif any(k.startswith(("dc.", "dcterms.")) for k in meta):
        f = _empty_fields("document")
        f.update({
            "title": _first(meta, "dc.title", "dcterms.title"),
            "authors": meta.get("dc.creator", []) or meta.get("dcterms.creator", []),
            "publisher": _first(meta, "dc.publisher", "dcterms.publisher"),
            "year": _year(_first(meta, "dc.date", "dcterms.issued", "dcterms.date")),
            "language": _first(meta, "dc.language", "dcterms.language").upper(),
            "abstract": _first(meta, "dc.description", "dcterms.abstract", "description"),
            "url": url,
        })
        ident = " ".join(meta.get("dc.identifier", []) + meta.get("dcterms.identifier", []))
        if _DOI_RE.search(ident):
            f["doi"] = _DOI_RE.search(ident).group(0)
        f["isbn"] = normalize_isbn(ident) if "isbn" in ident.lower() else ""

    ld = _jsonld_fields(page)
    if ld:
        f = merge_fields(f, ld) if f else ld

    if f is None and (meta.get("og:title") or re.search(r"<title>(.*?)</title>", page, re.I | re.S)):
        f = _empty_fields("webpage")
        tm = re.search(r"<title>(.*?)</title>", page, re.I | re.S)
        f["title"] = _first(meta, "og:title") or (html.unescape(tm.group(1)).strip() if tm else "")
        f["abstract"] = _first(meta, "og:description", "description")
        f["url"] = url
        f["confidence"] = 0.5

    if f is not None:
        if not f.get("doi"):
            m = _DOI_RE.search(page)
            if m:
                f["doi"] = m.group(0).rstrip(".,;)")
        if not f.get("isbn"):
            m = re.search(r"ISBN[:\s]*([0-9Xx][0-9Xx\-\s]{8,20}[0-9Xx])", page, re.I)
            if m:
                f["isbn"] = normalize_isbn(m.group(1))
        if not f.get("pdf_url"):
            m = _PDF_LINK_RE.search(page)
            if m:
                f["pdf_url"] = urljoin(url, html.unescape(m.group(1)))
    return f, ""


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9ăâîșşțţ]+", " ", (s or "").lower()).strip()


def match_by_title(title: str, year: str = "") -> Optional[Dict]:
    """
    Căutare CrossRef după titlu; acceptă doar potriviri aproape exacte (>= 0.92)
    și, dacă se cunoaște, anul egal — evită fișele greșite.
    """
    from difflib import SequenceMatcher
    from zotero.lookup import search_crossref
    if len(_norm_title(title)) < 15:
        return None
    results, _ = search_crossref(title, rows=5)
    best, best_score = None, 0.0
    for r in results:
        score = SequenceMatcher(None, _norm_title(title), _norm_title(r.get("title", ""))).ratio()
        if year and r.get("year") and r["year"] != year:
            score -= 0.1
        if score > best_score:
            best, best_score = r, score
    if best and best_score >= 0.92:
        log.info("Fișă identificată după titlu în CrossRef (%.2f): %s", best_score, best.get("doi"))
        return lookup_doi(best["doi"])[0] if best.get("doi") else best
    return None


# ---------------------------------------------------------------------------
# API public
# ---------------------------------------------------------------------------

def resolve_url(url: str) -> Tuple[Optional[Dict], str, str]:
    """
    Pagină web -> (fields, pdf_url, err).
    Reunește: registre după DOI (prioritate) + metadatele paginii (completare).
    """
    url = url.strip()
    page_fields: Optional[Dict] = None
    err = ""

    # 1. DOI direct în URL
    doi = _DOI_RE.search(url).group(0).rstrip(".,;)") if "doi.org/" in url and _DOI_RE.search(url) else ""

    # 2. DSpace
    if not doi:
        page_fields, _ = _dspace_fields(url)

    # 3-4. HTML generic
    if page_fields is None:
        r, err = _fetch(url)
        if r is not None and "html" in (r.headers.get("content-type") or "").lower():
            page_fields, _ = _html_fields(r.text, str(r.url))
        elif r is not None and "pdf" in (r.headers.get("content-type") or "").lower():
            return _empty_fields("document"), str(r.url), ""

    if page_fields and page_fields.get("doi") and not doi:
        doi = page_fields["doi"]

    # Registrele sunt sursa autoritativă; pagina completează (rezumat, PDF, ISBN…)
    reg_fields = None
    if doi:
        reg_fields, _ = lookup_doi(doi)
    if reg_fields is None and page_fields and page_fields.get("title"):
        # Fără DOI pe pagină: căutăm fișa în CrossRef după titlu (potrivire strictă)
        reg_fields = match_by_title(page_fields["title"], page_fields.get("year", ""))
    if reg_fields is None and page_fields and page_fields.get("isbn"):
        reg_fields, _ = lookup_isbn(page_fields["isbn"])

    if reg_fields and page_fields:
        fields = merge_fields(reg_fields, page_fields)
    else:
        fields = reg_fields or page_fields

    if not fields:
        return None, "", err or "Pagina nu conține metadate bibliografice recunoscute"

    pdf_url = fields.pop("pdf_url", "") or (page_fields or {}).get("pdf_url", "") or ""
    if not fields.get("url"):
        fields["url"] = url
    return fields, pdf_url, ""
