# Zotai

**Zotai** (Zotero + AI) — aplicație desktop pentru Windows care automatizează catalogarea documentelor PDF/DOCX: extrage metadate bibliografice cu AI și baze online, le scrie direct în fișier (XMP Dublin Core) și le trimite în Zotero.

## Funcționalități

- **Ingestion multiplă**: drag & drop, selectare fișiere/foldere, argumente CLI, meniul contextual Windows („Procesează cu Zotai" pentru `.pdf`/`.docx`, inclusiv „Deschide cu" din Windows 11).
- **Detecția tipului de document**: strat de text digital vs. scan; OCR automat prin Tesseract cu pachete de limbi descărcabile la cerere (ron/rus/eng + catalog complet).
- **Metadate hibride**:
  - DOI/ISBN din text → metadate exacte din **CrossRef / OpenLibrary / Google Books**;
  - **AI CLI** (Antigravity `agy`, Claude Code sau comandă personalizată) completează doar câmpurile goale — inclusiv câmpuri specifice de catalogare (CZU, LBC, tiraj, bibliografie) în `Extra`.
- **Căutare online**: bară de căutare pentru DOI / ISBN / titlu / link direct către PDF — creează fișe fără fișier local.
- **Injectare metadate**: PDF Info Dictionary + XMP Dublin Core + PRISM; pentru DOCX — `docProps/core.xml`. Copie de rezervă `*.xmpbak` înainte de scriere.
- **Zotero Connector** (`127.0.0.1:23119`): `saveItems` + `saveAttachment`, sau trimitere standalone cu auto-recunoaștere Zotero când există DOI/ISBN.
- **Zero Data Loss**: coadă offline în SQLite — sarcinile se trimit automat când Zotero revine online.
- **Notificări toast Windows**, jurnalizare rotativă, datele utilizatorului în `%LOCALAPPDATA%\Zotai`.
- **Instalator unic** `ZotaiSetup.exe` (PyInstaller + Inno Setup, wizard în română) cu dezinstalare și păstrarea datelor utilizatorului.

## Instalare

Descărcați `dist_installer/ZotaiSetup-1.0.0.exe` și rulați-l (necesită drepturi de administrator). La instalare puteți activa:

- comanda rapidă pe desktop;
- „Procesează cu Zotai" în meniul contextual pentru PDF/DOCX.

Datele aplicației (baza de date, jurnale, pachete de limbi OCR) se păstrează în `%LOCALAPPDATA%\Zotai` și nu se șterg la dezinstalare.

## Rulare din surse (dezvoltare)

```bash
pip install -r requirements.txt
python main.py
```

Utilitare CLI:

```bash
# Extragere text / OCR pentru un fișier
python -m worker document.pdf --lang ron+rus+eng --pretty

# Gestionarea pachetelor de limbi Tesseract
python -m worker.lang_manager list
python -m worker.lang_manager install ron ukr
```

## Construirea instalatorului

```bash
C:/Python314/python.exe -m PyInstaller zotai.spec --noconfirm
iscc installer/zotai.iss
```

Rezultatul: `dist_installer/ZotaiSetup-1.0.0.exe` (~48 MB, Python inclus — nu este necesar pe mașina țintă).

## Arhitectură

```
gui/      — interfața CustomTkinter (fereastra principală, componente, dialoguri)
worker/   — extractor (PyMuPDF + Tesseract OCR), adaptor AI, injectare XMP, manager limbi
zotero/   — tipuri de elemente, convertor metadate, connector HTTP, lookup online
db/       — SQLite (WAL), depozitul de sarcini cu maparea stărilor UI↔BD
core/     — căi centralizate, jurnalizare, notificări toast, meniu contextual Windows, i18n
locales/  — pachete de limbi externe JSON (ro, ru, en + detecție dinamică)
installer/— script Inno Setup
```

## Configurare necesară

- **Zotero** cu Connector activ (portul 23119) pentru export; altfel sarcinile așteaptă în coadă.
- **Agent AI CLI** (`agy` recomandat) sau cheie API — se configurează în Setări → Motor AI.
- **Tesseract OCR** pentru scanuri — `bin/tesseract` în distribuție sau instalare de sistem; limbile se descarcă din Setări → Limbi OCR.

