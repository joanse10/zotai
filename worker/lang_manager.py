"""
Managerul pachetelor de limbi Tesseract pentru Zotai.

Pachetele (*.traineddata) sunt descărcate la cerere din tesseract-ocr/tessdata_fast
în directorul bin/tessdata al aplicației.
Extractorul descoperă acest director automat (vezi worker/extractor.py).

Adaptor CLI:
    python -m worker.lang_manager list              # listează tot cu starea de instalare
    python -m worker.lang_manager installed         # doar cele instalate
    python -m worker.lang_manager install ron ukr   # descarcă pachetele
    python -m worker.lang_manager remove osd        # elimină pachetul
"""

import os
import urllib.request
from typing import Callable, Dict, List, Optional

TESSDATA_FAST_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"
TESSDATA_BEST_URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main"

# Dimensiunea minimă validă pentru traineddata (~50 KB)
MIN_TRAINEDDATA_BYTES = 50 * 1024

# Directorul limbilor Tesseract: cod -> nume afișat
LANGUAGES: Dict[str, str] = {
    "afr": "Afrikaans", "amh": "Amharic", "ara": "Arabic", "asm": "Assamese",
    "aze": "Azerbaijani", "aze_cyrl": "Azerbaijani (Cyrillic)", "bel": "Belarusian",
    "ben": "Bengali", "bho": "Bhojpuri", "bod": "Tibetan", "bos": "Bosnian",
    "bre": "Breton", "bul": "Bulgarian", "cat": "Catalan", "ceb": "Cebuano",
    "ces": "Czech", "chi_sim": "Chinese (Simplified)", "chi_sim_vert": "Chinese Simplified (Vert.)",
    "chi_tra": "Chinese (Traditional)", "chi_tra_vert": "Chinese Traditional (Vert.)",
    "chr": "Cherokee", "cos": "Corsican", "cym": "Welsh", "dan": "Danish",
    "deu": "German", "deu_latf": "German (Fraktur)", "div": "Divehi",
    "dzo": "Dzongkha", "ell": "Greek", "eng": "English", "enm": "English (Middle)",
    "epo": "Esperanto", "equ": "Math / Equations", "est": "Estonian",
    "eus": "Basque", "fao": "Faroese", "fas": "Persian", "fil": "Filipino",
    "fin": "Finnish", "fra": "French", "frm": "French (Middle)",
    "fry": "Western Frisian", "gla": "Scottish Gaelic", "gle": "Irish",
    "glg": "Galician", "grc": "Greek (Ancient)", "guj": "Gujarati",
    "hat": "Haitian Creole", "heb": "Hebrew", "hin": "Hindi", "hrv": "Croatian",
    "hun": "Hungarian", "hye": "Armenian", "iku": "Inuktitut",
    "ind": "Indonesian", "isl": "Icelandic", "ita": "Italian",
    "ita_old": "Italian (Old)", "jav": "Javanese", "jpn": "Japanese",
    "jpn_vert": "Japanese (Vert.)", "kan": "Kannada", "kat": "Georgian",
    "kat_old": "Georgian (Old)", "kaz": "Kazakh", "khm": "Khmer",
    "kir": "Kyrgyz", "kmr": "Kurdish (Kurmanji)", "kor": "Korean",
    "kor_vert": "Korean (Vert.)", "lao": "Lao", "lat": "Latin",
    "lav": "Latvian", "lit": "Lithuanian", "ltz": "Luxembourgish",
    "mal": "Malayalam", "mar": "Marathi", "mkd": "Macedonian",
    "mlt": "Maltese", "mon": "Mongolian", "mri": "Maori", "msa": "Malay",
    "mya": "Burmese", "nep": "Nepali", "nld": "Dutch", "nor": "Norwegian",
    "oci": "Occitan", "ori": "Oriya", "osd": "Orientation & Script Detection",
    "pan": "Punjabi", "pol": "Polish", "por": "Portuguese", "pus": "Pashto",
    "que": "Quechua", "ron": "Romanian", "rus": "Russian", "san": "Sanskrit",
    "sin": "Sinhala", "slk": "Slovak", "slk_frak": "Slovak (Fraktur)",
    "slv": "Slovenian", "snd": "Sindhi", "spa": "Spanish",
    "spa_old": "Spanish (Old)", "sqi": "Albanian", "srp": "Serbian",
    "srp_latn": "Serbian (Latin)", "sun": "Sundanese", "swa": "Swahili",
    "swe": "Swedish", "syr": "Syriac", "tam": "Tamil", "tat": "Tatar",
    "tel": "Telugu", "tgk": "Tajik", "tgl": "Tagalog", "tha": "Thai",
    "tir": "Tigrinya", "ton": "Tonga", "tur": "Turkish", "uig": "Uyghur",
    "ukr": "Ukrainian", "urd": "Urdu", "uzb": "Uzbek",
    "uzb_cyrl": "Uzbek (Cyrillic)", "vie": "Vietnamese", "yid": "Yiddish",
    "yor": "Yoruba",
}


def default_tessdata_dir() -> str:
    """Directorul tessdata: dev -> bin/tessdata, frozen -> %LOCALAPPDATA%\\Zotai\\tessdata."""
    from core.paths import tessdata_dir
    return tessdata_dir()


def installed_languages(tessdata_dir: Optional[str] = None) -> Dict[str, int]:
    """Returnează {cod: dimensiune_în_octeți} pentru toate pachetele de limbi instalate."""
    directory = tessdata_dir or default_tessdata_dir()
    found: Dict[str, int] = {}
    if os.path.isdir(directory):
        for f in os.listdir(directory):
            if f.endswith(".traineddata"):
                found[f[:-len(".traineddata")]] = os.path.getsize(os.path.join(directory, f))
    return found


def download_language(
    code: str,
    tessdata_dir: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    quality: str = "fast",
) -> str:
    """
    Descarcă <cod>.traineddata în tessdata_dir.
    Returnează calea către fișierul instalat.
    """
    code = code.strip()
    if not code or any(c in code for c in '/\\..'):
        raise ValueError(f"Cod de limbă invalid: {code!r}")

    base_url = TESSDATA_BEST_URL if quality == "best" else TESSDATA_FAST_URL
    url = f"{base_url}/{code}.traineddata"
    directory = tessdata_dir or default_tessdata_dir()
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, f"{code}.traineddata")

    req = urllib.request.Request(url, headers={"User-Agent": "Zotai/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise

    if os.path.getsize(dest) < MIN_TRAINEDDATA_BYTES:
        os.remove(dest)
        raise RuntimeError(f"Pachetul descărcat '{code}' este prea mic — codul poate să nu existe")
    return dest


def remove_language(code: str, tessdata_dir: Optional[str] = None) -> bool:
    """Elimină un pachet de limbă instalat. Returnează True dacă fișierul a fost șters."""
    directory = tessdata_dir or default_tessdata_dir()
    path = os.path.join(directory, f"{code}.traineddata")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def resolve_ocr_languages(requested: str, tessdata_dir: Optional[str] = None) -> str:
    """
    Filtrează limbile solicitate ('ron+rus+eng') după pachetele efectiv instalate.
    Returnează șirul pentru Tesseract sau '' dacă niciun pachet nu este instalat.
    """
    installed = set(installed_languages(tessdata_dir))
    usable = [c for c in requested.split("+") if c in installed]
    return "+".join(usable)


def _cli() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="lang_manager",
                                     description="Zotai: managerul pachetelor de limbi Tesseract")
    parser.add_argument("--tessdata", default="", help="Directorul tessdata (implicit: bin/tessdata)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="Listează catalogul de limbi cu starea de instalare")
    sub.add_parser("installed", help="Doar pachetele de limbi instalate")
    p_install = sub.add_parser("install", help="Descarcă pachetele de limbi")
    p_install.add_argument("codes", nargs="+", help="Codurile de limbă (ex. ron ukr)")
    p_install.add_argument("--best", action="store_true", help="Modele de înaltă calitate în locul celor rapide")
    p_remove = sub.add_parser("remove", help="Elimină pachetele de limbi")
    p_remove.add_argument("codes", nargs="+")
    args = parser.parse_args()

    tdir = args.tessdata or None

    if args.cmd == "installed":
        for code, size in sorted(installed_languages(tdir).items()):
            print(f"{code}\t{size / 1024 / 1024:.1f} MB")
        return 0

    if args.cmd == "list":
        installed = installed_languages(tdir)
        for code, name in sorted(LANGUAGES.items(), key=lambda kv: kv[1]):
            mark = f"[instalat {installed[code] / 1024 / 1024:.1f} MB]" if code in installed else ""
            print(f"{code}\t{name} {mark}")
        return 0

    if args.cmd == "install":
        failed = []
        for code in args.codes:
            print(f">>> {code}: se descarcă...", file=sys.stderr)
            try:
                path = download_language(
                    code, tdir,
                    progress=lambda d, t: print(
                        f"    {d / 1024 / 1024:.1f} / {t / 1024 / 1024:.1f} MB" if t else f"    {d / 1024 / 1024:.1f} MB",
                        file=sys.stderr),
                    quality="best" if args.best else "fast",
                )
                print(f"OK {code}: {path}")
            except Exception as e:
                failed.append(code)
                print(f"EȘUAT {code}: {e}", file=sys.stderr)
        return 1 if failed else 0

    if args.cmd == "remove":
        for code in args.codes:
            print(f"{'OK' if remove_language(code, tdir) else 'NEGĂSIT'} {code}")
        return 0

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli())
