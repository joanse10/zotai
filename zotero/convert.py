"""
Convertor din BookMetadata în formatul de element Zotero (API / import JSON).

Produce un dicționar compatibil cu schema elementului Zotero:
    {"itemType": "book", "title": ..., "creators": [...], ...}
Acest dicționar este folosit pentru cereri POST către connectorul local
și ca model de date țintă pentru etapa de extragere AI.
"""

import re
from typing import Dict, List

from gui.models import BookMetadata, iso639_1
from zotero.item_types import type_key

# Tipurile în care paginile se stochează în "pages", nu în "numPages"
_PAGES_FIELD_TYPES = {"journalArticle", "magazineArticle", "newspaperArticle",
                      "conferencePaper", "bookSection", "dictionaryEntry",
                      "encyclopediaArticle"}


def split_people(raw: str) -> List[Dict[str, str]]:
    """
    Parsează șirul de autori/editori în lista de persoane Zotero:
    - 'Ion Popescu, Vasile Ionescu' -> [{'firstName': 'Ion', 'lastName': 'Popescu'}, ...]
    - 'Popescu, Ion; Ionescu, Vasile' -> [{'lastName': 'Popescu', 'firstName': 'Ion'}, ...]
    - 'Popescu, Ion' -> [{'lastName': 'Popescu', 'firstName': 'Ion'}]
    - 'Ashish Vaswani, Noam Shazeer, and Niki Parmar' -> 3 persoane
    - 'Garomont-Studio' -> [{'name': 'Garomont-Studio'}] (mononime/organizații)
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    if ";" in raw:
        chunks = [c.strip() for c in raw.split(";") if c.strip()]
    elif re.search(r",?\s+(?:and|&)\s+", raw, re.I) and "," in raw:
        # e.g. 'A, B, and C' -> normalizează ', and ' / ' and ' la ', '
        raw = re.sub(r",?\s+(?:and|&)\s+", ", ", raw, flags=re.I)
        comma_chunks = [c.strip() for c in raw.split(",") if c.strip()]
        if all(" " in c for c in comma_chunks):
            chunks = comma_chunks
        else:
            if len(comma_chunks) % 2 == 0:
                chunks = [f"{comma_chunks[i]}, {comma_chunks[i+1]}" for i in range(0, len(comma_chunks), 2)]
            else:
                chunks = comma_chunks
    elif re.search(r"\s+(?:and|&)\s+", raw, re.I):
        # 'Ashish Vaswani and Noam Shazeer'
        chunks = [c.strip() for c in re.split(r"\s+(?:and|&)\s+", raw, flags=re.I) if c.strip()]
    else:
        comma_chunks = [c.strip() for c in raw.split(",") if c.strip()]
        if len(comma_chunks) <= 1:
            chunks = comma_chunks
        elif all(" " in c for c in comma_chunks):
            chunks = comma_chunks
        elif len(comma_chunks) == 2 and not any(" " in c for c in comma_chunks):
            chunks = [f"{comma_chunks[0]}, {comma_chunks[1]}"]
        elif len(comma_chunks) % 2 == 0 and not any(" " in c for c in comma_chunks):
            chunks = [f"{comma_chunks[i]}, {comma_chunks[i+1]}" for i in range(0, len(comma_chunks), 2)]
        else:
            chunks = comma_chunks

    people = []
    for chunk in chunks:
        if not chunk:
            continue
        if "," in chunk:
            sub = [p.strip() for p in chunk.split(",", 1)]
            last = sub[0]
            first = sub[1] if len(sub) > 1 else ""
            if first:
                people.append({"firstName": first, "lastName": last})
            else:
                people.append({"name": last})
        else:
            parts = chunk.split()
            if len(parts) == 1:
                people.append({"name": parts[0]})
            else:
                people.append({"firstName": " ".join(parts[:-1]), "lastName": parts[-1]})
    return people



def to_zotero_item(m: BookMetadata) -> Dict:
    """Construiește dicționarul de element Zotero din BookMetadata; câmpurile goale se omit."""
    item_type = type_key(m.doc_type)
    item: Dict = {"itemType": item_type}

    # Titlu: Zotero nu are câmp subtitle — concatenăm prin două puncte
    title = m.title.strip()
    if m.subtitle.strip() and m.subtitle.strip() not in title:
        title = f"{title}: {m.subtitle.strip()}" if title else m.subtitle.strip()

    creators = [{"creatorType": "author", **p} for p in split_people(m.authors)]
    creators += [{"creatorType": "editor", **p} for p in split_people(m.editors)]

    pages_field = "pages" if item_type in _PAGES_FIELD_TYPES else "numPages"
    url = m.url.strip()
    if url.lower().startswith("file:"):
        url = ""  # căile locale nu au ce căuta în câmpul URL al fișei

    field_map = {
        "title": title,
        "shortTitle": m.short_title,
        "publisher": m.publisher,
        "place": m.city,
        "date": m.year,
        "edition": m.edition,
        "series": m.series,
        "seriesNumber": m.series_number,
        "volume": m.volume,
        "issue": m.issue,
        "numVolumes": m.num_volumes,
        pages_field: m.num_pages,
        "ISBN": m.isbn,
        "ISSN": m.issn,
        "DOI": m.doi,
        "url": url,
        "accessDate": m.accessed,
        "abstractNote": m.abstract,
        "callNumber": m.call_number,
        "archive": m.archive,
        "archiveLocation": m.loc_in_archive,
        "libraryCatalog": m.library_catalog,
        "rights": m.license,
        "extra": m.extra,
        "citationKey": m.citation_key,
        "language": iso639_1(m.language),
    }

    # Publicația-părinte are câmp dedicat în funcție de tip; „series” rămâne doar
    # pentru colecții editoriale. Rezervă: valorile vechi stocate în `series`.
    parent = m.publication_title.strip()
    parent_field = {
        "journalArticle": "publicationTitle",
        "magazineArticle": "publicationTitle",
        "newspaperArticle": "publicationTitle",
        "conferencePaper": "proceedingsTitle",
        "bookSection": "bookTitle",
        "encyclopediaArticle": "encyclopediaTitle",
        "dictionaryEntry": "dictionaryTitle",
    }.get(item_type)
    if parent_field:
        if not parent and item_type in ("conferencePaper", "bookSection"):
            parent, field_map["series"] = m.series, ""
        field_map[parent_field] = parent

    # Câmpuri specifice: instituția la teze/rapoarte, repository la preprint
    if item_type == "thesis":
        field_map["university"] = field_map.pop("publisher")
    elif item_type == "report":
        field_map["institution"] = field_map.pop("publisher")
    elif item_type == "preprint":
        field_map["repository"] = field_map.pop("publisher")

    # Tipurile fără „publisher”/„place” în schema Zotero — informația se păstrează în Extra
    if item_type in ("journalArticle", "magazineArticle", "newspaperArticle", "webpage"):
        moved = [(lbl, field_map.pop(k, "")) for k, lbl in
                 (("publisher", "Publisher"), ("place", "Place"), ("edition", "Edition"))]
        field_map.pop("numVolumes", None)
        extra_lines = [l for l in (field_map.get("extra") or "").split("\n") if l.strip()]
        for lbl, val in moved:
            if str(val).strip() and not any(l.lower().startswith(lbl.lower() + ":") for l in extra_lines):
                extra_lines.append(f"{lbl}: {val}")
        field_map["extra"] = "\n".join(extra_lines)

    item.update({k: v for k, v in field_map.items() if str(v).strip()})
    if creators:
        item["creators"] = creators
    return item
