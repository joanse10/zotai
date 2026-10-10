"""
Injectarea metadatelor în PDF (TZ.md §6).

Scrie două straturi:
1. Document Information Dictionary: /Title, /Author, /Subject, /Keywords.
2. Flux XMP: Dublin Core (dc:*) + PRISM (edition, volume, isbn, issn, doi, pageCount).

Scrie incremental (saveIncr): structura originală a fișierului este păstrată.
Creează o copie de rezervă *.xmpbak înainte de scriere.
"""

import os
import shutil
from dataclasses import dataclass, field
from typing import List
from xml.sax.saxutils import escape

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from gui.models import BookMetadata, iso639_1
from zotero.item_types import type_key


@dataclass
class InjectResult:
    ok: bool = True
    error: str = ""
    fields_written: List[str] = field(default_factory=list)


def _xmp_packet(m: BookMetadata) -> str:
    """Generează pachetul XMP cu metadate Dublin Core + PRISM."""
    e = escape
    title = m.title.strip()
    if m.subtitle.strip() and m.subtitle.strip() not in title:
        title = f"{title}: {m.subtitle.strip()}" if title else m.subtitle.strip()

    authors = [a.strip() for a in m.authors.replace(";", ",").split(",") if a.strip()]
    creators = "".join(f"<rdf:li>{e(a)}</rdf:li>" for a in authors)
    lang = iso639_1(m.language)
    identifier = f"urn:isbn:{m.isbn}" if m.isbn else (m.doi or "")

    parts = []
    if title:
        parts.append(f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{e(title)}</rdf:li></rdf:Alt></dc:title>')
    if creators:
        parts.append(f'<dc:creator><rdf:Seq>{creators}</rdf:Seq></dc:creator>')
    if m.publisher.strip():
        parts.append(f'<dc:publisher><rdf:Bag><rdf:li>{e(m.publisher.strip())}</rdf:li></rdf:Bag></dc:publisher>')
    if m.year.strip():
        parts.append(f'<dc:date><rdf:Seq><rdf:li>{e(m.year.strip())}</rdf:li></rdf:Seq></dc:date>')
    if identifier:
        parts.append(f'<dc:identifier>{e(identifier)}</dc:identifier>')
    parts.append(f'<dc:type><rdf:Bag><rdf:li>{e(type_key(m.doc_type))}</rdf:li></rdf:Bag></dc:type>')
    if lang:
        parts.append(f'<dc:language><rdf:Seq><rdf:li>{e(lang)}</rdf:li></rdf:Seq></dc:language>')
    if m.abstract.strip():
        parts.append(f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{e(m.abstract.strip())}</rdf:li></rdf:Alt></dc:description>')
    if m.license.strip():
        parts.append(f'<dc:rights><rdf:Alt><rdf:li xml:lang="x-default">{e(m.license.strip())}</rdf:li></rdf:Alt></dc:rights>')

    # Câmpuri de metadate PRISM
    for tag, val in (("prism:edition", m.edition), ("prism:volume", m.volume),
                     ("prism:number", m.series_number), ("prism:pageCount", m.num_pages),
                     ("prism:isbn", m.isbn), ("prism:issn", m.issn),
                     ("prism:doi", m.doi)):
        if val.strip():
            parts.append(f"<{tag}>{e(val.strip())}</{tag}>")

    body = "\n      ".join(parts)
    return f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
      {body}
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


def _inject_docx_metadata(docx_path: str, meta: BookMetadata, backup: bool = True) -> InjectResult:
    """Scrie metadatele în DOCX (docProps/core.xml — Dublin Core)."""
    res = InjectResult()
    try:
        import docx
    except ImportError:
        res.ok = False
        res.error = "Injectarea metadatelor DOCX necesită python-docx"
        return res

    if backup:
        bak = docx_path + ".xmpbak"
        try:
            if not os.path.exists(bak):
                shutil.copyfile(docx_path, bak)
        except Exception as e:
            res.ok = False
            res.error = f"Nu s-a putut crea copia de rezervă: {e}"
            return res

    try:
        doc = docx.Document(docx_path)
        cp = doc.core_properties
        cp.title = meta.title + (f": {meta.subtitle}" if meta.subtitle else "")
        cp.author = meta.authors
        cp.last_modified_by = "Zotai"
        cp.subject = meta.abstract
        cp.keywords = "; ".join(filter(None, [
            f"Type: {type_key(meta.doc_type)}",
            f"ISBN: {meta.isbn}" if meta.isbn else "",
            f"DOI: {meta.doi}" if meta.doi else "",
            f"Publisher: {meta.publisher}" if meta.publisher else "",
        ]))
        cp.comments = meta.extra or ""
        cp.language = iso639_1(meta.language)
        cp.category = meta.doc_type
        doc.save(docx_path)
        res.fields_written.append("docx_core_props")
    except Exception as e:
        res.ok = False
        res.error = f"Eroare la scrierea metadatelor DOCX: {e}"
    return res


def inject_metadata(pdf_path: str, meta: BookMetadata, backup: bool = True) -> InjectResult:
    """
    Scrie metadatele direct în document.
    PDF -> Info Dict + XMP (salvare incrementală); DOCX -> docProps/core.xml.
    backup=True -> creează <fișier>.xmpbak înainte de modificare.
    """
    res = InjectResult()
    if not os.path.isfile(pdf_path):
        res.ok = False
        res.error = f"Fișierul nu a fost găsit: {pdf_path}"
        return res

    if pdf_path.lower().endswith(".docx"):
        return _inject_docx_metadata(pdf_path, meta, backup)

    if backup:
        bak = pdf_path + ".xmpbak"
        try:
            if not os.path.exists(bak):
                shutil.copyfile(pdf_path, bak)
        except Exception as e:
            res.ok = False
            res.error = f"Nu s-a putut crea copia de rezervă: {e}"
            return res

    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        res.ok = False
        res.error = f"Nu s-a putut deschide PDF: {e}"
        return res

    try:
        keywords = "; ".join(filter(None, [
            f"Type: {type_key(meta.doc_type)}",
            f"ISBN: {meta.isbn}" if meta.isbn else "",
            f"DOI: {meta.doi}" if meta.doi else "",
            f"Publisher: {meta.publisher}" if meta.publisher else "",
        ]))
        doc.set_metadata({
            "title": meta.title,
            "author": meta.authors,
            "subject": (meta.abstract or "").strip()[:1000],
            "keywords": keywords,
        })
        res.fields_written.append("info_dict")

        doc.set_xml_metadata(_xmp_packet(meta))
        res.fields_written.append("xmp")

        doc.saveIncr()
        res.fields_written.append("file_saved")
    except Exception as e:
        res.ok = False
        res.error = f"Eroare la scrierea metadatelor: {e}"
    finally:
        doc.close()

    return res
