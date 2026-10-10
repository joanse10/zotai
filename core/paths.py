"""
Rezolvarea centrală a căilor pentru Zotai.

Două moduri:
- dev: toate datele în rădăcina proiectului (H:\\Dev\\Zotai)
- frozen (PyInstaller/Program Files): datele inscriptibile în %LOCALAPPDATA%\\Zotai
  (BD, jurnale, limbi descărcate), iar resursele read-only sunt lângă exe
  (bin/tessdata, assets).
"""

import os
import shutil
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_root() -> str:
    """Directorul rădăcină al aplicației (resurse read-only): lângă exe sau rădăcina proiectului."""
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass and os.path.isdir(meipass):
            return meipass
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """
    Directorul inscriptibil de date al aplicației.
    frozen -> %LOCALAPPDATA%\\Zotai; dev -> rădăcina proiectului.
    """
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        d = os.path.join(base, "Zotai")
    else:
        d = app_root()
    os.makedirs(d, exist_ok=True)
    return d


def db_path() -> str:
    return os.path.join(data_dir(), "zotai.db")


def log_dir() -> str:
    d = os.path.join(data_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def downloads_dir() -> str:
    d = os.path.join(data_dir(), "downloads")
    os.makedirs(d, exist_ok=True)
    return d


def bundled_tessdata_dir() -> str:
    """Pachete de limbi read-only din distribuție: <app_root>/bin/tessdata."""
    return os.path.join(app_root(), "bin", "tessdata")


def tessdata_dir() -> str:
    """
    Directorul pachetelor de limbi Tesseract pentru citire/scriere.
    frozen -> %LOCALAPPDATA%\\Zotai\\tessdata (cu copierea automată a pachetelor încorporate);
    dev -> bin/tessdata din proiect.
    """
    if not is_frozen():
        return bundled_tessdata_dir()
    d = os.path.join(data_dir(), "tessdata")
    os.makedirs(d, exist_ok=True)
    # La prima rulare copiem pachetele încorporate din distribuție
    bundled = bundled_tessdata_dir()
    if os.path.isdir(bundled):
        for f in os.listdir(bundled):
            if not f.endswith(".traineddata"):
                continue
            src, dst = os.path.join(bundled, f), os.path.join(d, f)
            if not os.path.exists(dst):
                try:
                    shutil.copyfile(src, dst)
                except OSError:
                    pass
    return d


def locales_dir() -> str:
    """Directorul fișierelor de localizare i18n."""
    bundled = os.path.join(app_root(), "locales")
    if os.path.isdir(bundled):
        return bundled
    custom = os.path.join(data_dir(), "locales")
    os.makedirs(custom, exist_ok=True)
    return custom

