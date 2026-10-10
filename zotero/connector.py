"""
Client HTTP către serverul local Zotero (Zotero Connector API, 127.0.0.1:23119).

Endpointurile serverului local Zotero:
  /connector/ping                     — verifică dacă Zotero este pornit
  /connector/saveItems                — creează elemente din translator-JSON
  /connector/saveAttachment           — încarcă PDF ca atașament la un element
  /connector/saveStandaloneAttachment — PDF de sine stătător (Zotero recunoaște automat metadatele)
  /connector/import                   — doar formate text de import (BibTeX/RIS), NU PDF binar

Protocolul „fișă + PDF" (identic cu connectorul din browser):
  1) saveItems cu items[0].id + sessionID -> creează fișa de metadate
  2) saveAttachment cu X-Metadata {sessionID, parentItemID} -> atașează fișierul

Când Zotero este offline, sarcinile rămân în coada SQLite (zotero_status='queued')
și sunt golite automat când serverul devine accesibil (Zero Data Loss).
"""

import json
import os
import uuid
from typing import List, Optional, Tuple

import httpx

DEFAULT_URL = "http://127.0.0.1:23119"


class ZoteroConnector:
    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 5.0):
        self.base_url = (base_url or DEFAULT_URL).rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Verificarea disponibilității
    # ------------------------------------------------------------------
    def ping(self) -> bool:
        """Returnează True dacă Zotero este pornit și răspunde la /connector/ping."""
        for method in ("get", "post"):
            try:
                r = getattr(httpx, method)(f"{self.base_url}/connector/ping",
                                           timeout=self.timeout)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------
    # Deduplicare prin Local API (Zotero 7: Setări -> Avansat ->
    # „Permite altor aplicații de pe acest computer să comunice cu Zotero”)
    # ------------------------------------------------------------------
    def find_existing(self, doi: str = "", isbn: str = "", title: str = "") -> Optional[str]:
        """
        Caută în biblioteca locală un element cu același DOI / ISBN / titlu.
        Returnează cheia elementului sau None (inclusiv când Local API este dezactivat).
        """
        queries = [q for q in (doi, isbn) if q]
        if title and len(title) > 12:
            queries.append(title[:120])
        for q in queries:
            try:
                r = httpx.get(
                    f"{self.base_url}/api/users/0/items",
                    params={"q": q, "qmode": "everything", "limit": 5,
                            "format": "json", "itemType": "-attachment || note"},
                    timeout=self.timeout,
                )
                if r.status_code != 200:
                    return None  # Local API dezactivat -> nu putem verifica
                for it in r.json():
                    d = it.get("data", {})
                    if doi and (d.get("DOI") or "").lower() == doi.lower():
                        return it.get("key")
                    if isbn and isbn in (d.get("ISBN") or "").replace("-", ""):
                        return it.get("key")
                    if title and q == title[:120] and \
                            (d.get("title") or "").strip().lower() == title.strip().lower():
                        return it.get("key")
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Trimiterea documentelor
    # ------------------------------------------------------------------
    def save_items(self, items: List[dict], session_id: Optional[str] = None,
                   uri: str = "") -> Tuple[bool, str]:
        """Creează elemente din translator-JSON prin /connector/saveItems."""
        payload = {"items": items}
        if session_id:
            payload["sessionID"] = session_id
        if uri:
            payload["uri"] = uri
        try:
            r = httpx.post(
                f"{self.base_url}/connector/saveItems",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Zotero-Connector-API-Version": "3",
                },
                timeout=max(self.timeout, 15.0),
            )
            if 200 <= r.status_code < 300:
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, f"saveItems error: {e}"

    @staticmethod
    def _file_url(path: str) -> str:
        from urllib.parse import quote
        return "file:///" + quote(path.replace("\\", "/"))

    @staticmethod
    def _mime_for(path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        return {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".epub": "application/epub+zip",
        }.get(ext, "application/octet-stream")

    @staticmethod
    def _rfc2047(title: str) -> str:
        """Anteturile HTTP sunt latin-1; codificăm anteturile non-ASCII ale numelor de fișiere."""
        try:
            title.encode("latin-1")
            return title
        except UnicodeEncodeError:
            import base64
            return "=?utf-8?B?" + base64.b64encode(title.encode()).decode() + "?="

    def save_attachment(self, pdf_path: str, session_id: str,
                        parent_item_id: str, attachment_id: str) -> Tuple[bool, str]:
        """
        Atașează PDF la un element creat de saveItems în aceeași sessionID.
        """
        if not os.path.isfile(pdf_path):
            return False, f"Fișierul nu a fost găsit: {pdf_path}"
        x_meta = {
            "id": attachment_id,
            "url": self._file_url(pdf_path),
            "contentType": self._mime_for(pdf_path),
            "parentItemID": parent_item_id,
            "title": self._rfc2047(os.path.basename(pdf_path)),
        }
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
            r = httpx.post(
                f"{self.base_url}/connector/saveAttachment",
                params={"sessionID": session_id},
                content=data,
                headers={
                    "Content-Type": self._mime_for(pdf_path),
                    "Content-Length": str(len(data)),
                    "X-Metadata": json.dumps(x_meta),
                },
                timeout=max(self.timeout, 60.0),
            )
            if 200 <= r.status_code < 300:
                return True, ""
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, f"saveAttachment error: {e}"

    def save_standalone_attachment(self, pdf_path: str) -> Tuple[bool, str, Optional[bool]]:
        """
        PDF fără fișă părinte — Zotero recunoaște automat metadatele.
        Returnează (ok, error, can_recognize).
        """
        if not os.path.isfile(pdf_path):
            return False, f"Fișierul nu a fost găsit: {pdf_path}", None
        x_meta = {
            "url": self._file_url(pdf_path),
            "contentType": self._mime_for(pdf_path),
            "title": self._rfc2047(os.path.basename(pdf_path)),
        }
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
            r = httpx.post(
                f"{self.base_url}/connector/saveStandaloneAttachment",
                params={"sessionID": uuid.uuid4().hex},
                content=data,
                headers={
                    "Content-Type": self._mime_for(pdf_path),
                    "Content-Length": str(len(data)),
                    "X-Metadata": json.dumps(x_meta),
                },
                timeout=max(self.timeout, 60.0),
            )
            if 200 <= r.status_code < 300:
                can = None
                try:
                    can = r.json().get("canRecognize")
                except Exception:
                    pass
                return True, "", can
            return False, f"HTTP {r.status_code}: {r.text[:200]}", None
        except Exception as e:
            return False, f"saveStandaloneAttachment error: {e}", None

    def save_item_with_pdf(self, item: dict, pdf_path: str) -> Tuple[bool, str]:
        """
        Protocolul în doi pași al connectorului din browser:
        saveItems (element + declarație de atașament) -> saveAttachment (atașament binar).
        """
        session_id = uuid.uuid4().hex
        attachment_id = f"zotai-att-{uuid.uuid4().hex[:12]}"
        file_url = self._file_url(pdf_path)

        item = dict(item)
        item.setdefault("id", f"zotai-{uuid.uuid4().hex[:12]}")
        item.setdefault("tags", [])
        item.setdefault("collections", [])
        item["attachments"] = [{
            "id": attachment_id,
            "title": "Full Text PDF" if pdf_path.lower().endswith(".pdf") else os.path.basename(pdf_path),
            "url": file_url,
            "mimeType": self._mime_for(pdf_path),
            "parentItem": item["id"],
        }]

        ok, err = self.save_items([item], session_id=session_id, uri=file_url)
        if not ok:
            return False, f"saveItems: {err}"

        ok, err = self.save_attachment(pdf_path, session_id,
                                       item["id"], attachment_id)
        if not ok:
            return True, f"Fișă creată, atașament eșuat: {err}"
        return True, "Fișă + PDF atașat"

    def send_task(self, task, prefer_recognize: bool = True) -> Tuple[bool, str]:
        """
        Trimite datele sarcinii către Zotero.

        Prioritate: fișa noastră de metadate + atașament PDF (card garantat complet).
        Recunoașterea standalone de către Zotero este doar rezervă pentru fișierele
        fără metadate — este asincronă și nu creează întotdeauna fișa.
        """
        from zotero.convert import to_zotero_item

        item = to_zotero_item(task.metadata) if task.metadata else None
        has_meta = bool(item and (item.get("title") or item.get("creators")))
        has_file = os.path.isfile(task.file_path)
        errors = []

        # 0. Deduplicare: același DOI/ISBN/titlu există deja în bibliotecă
        if item and not getattr(task, "force_resend", False):
            key = self.find_existing(item.get("DOI", ""), item.get("ISBN", ""),
                                     item.get("title", ""))
            if key:
                return True, f"Există deja în Zotero (cheie {key}) — nu s-a dublat"

        # 1. Fișă de metadate + atașament PDF (calea principală)
        if has_meta and has_file:
            ok, info = self.save_item_with_pdf(item, task.file_path)
            if ok:
                return True, info
            errors.append(f"item+pdf: {info}")

        # 2. Doar fișa de metadate (fișe de căutare fără fișier)
        if has_meta:
            ok, err = self.save_items([item])
            if ok:
                return True, "Metadate (fără fișier)"
            errors.append(f"saveItems: {err}")

        # 3. Rezervă: PDF standalone — Zotero încearcă să-l recunoască singur
        if has_file and prefer_recognize:
            ok, err, _ = self.save_standalone_attachment(task.file_path)
            if ok:
                return True, "Atașament (auto-recunoaștere Zotero)"
            errors.append(f"standalone: {err}")

        if not errors:
            return False, "Nicio metadată sau fișier de trimis"
        return False, "; ".join(errors)
