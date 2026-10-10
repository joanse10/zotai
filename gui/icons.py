"""
Modul de încărcare și adaptare a pictogramelor pentru aplicația Zotai.
Oferă pictograme vector-scalate și raster în diverse dimensiuni,
și configurează pictogramele pentru bara de activități / bara de titlu Windows.
"""

import os
import ctypes
from typing import Dict, Tuple, Optional
from PIL import Image
import customtkinter as ctk

from core.paths import app_root
_BASE_DIR = app_root()
_ASSETS_DIR = os.path.join(_BASE_DIR, "assets")

_ICON_ICO = os.path.join(_ASSETS_DIR, "icon.ico")
_ICON_MASTER = os.path.join(_ASSETS_DIR, "icon_master.png")
_ICON_256 = os.path.join(_ASSETS_DIR, "icon_256.png")

# Cache pentru CTkImages generate
_ctk_image_cache: Dict[Tuple[int, int], ctk.CTkImage] = {}
_pil_image_cache: Dict[str, Image.Image] = {}


def get_ico_path() -> str:
    """Returnează calea către fișierul icon.ico."""
    if os.path.exists(_ICON_ICO):
        return _ICON_ICO
    fallback = os.path.join(_BASE_DIR, "icon.ico")
    if os.path.exists(fallback):
        return fallback
    return ""


def get_app_icon_image(size: int = 32) -> Optional[ctk.CTkImage]:
    """
    Returnează CTkImage de înaltă calitate pentru widgeturile CustomTkinter.
    Cachează automat imaginile generate.
    """
    key = (size, size)
    if key in _ctk_image_cache:
        return _ctk_image_cache[key]

    preferred_png = os.path.join(_ASSETS_DIR, f"icon_{size}.png")
    if not os.path.exists(preferred_png):
        preferred_png = _ICON_256 if os.path.exists(_ICON_256) else _ICON_MASTER

    if not os.path.exists(preferred_png):
        return None

    try:
        pil_img = Image.open(preferred_png)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(size, size))
        _ctk_image_cache[key] = ctk_img
        return ctk_img
    except Exception as e:
        print(f"[Icon] Nu s-a putut încărca pictograma {size}x{size}: {e}")
        return None


def setup_window_icon(window):
    """
    Setează pictograma nativă a ferestrei în Windows:
    1. Înregistrează un AppUserModelID unic pentru gruparea în bara de activități.
    2. Aplică iconbitmap (ICO multi-rezoluție 16x16 ... 256x256).
    3. Aplică iconphoto ca rezervă.
    """
    try:
        myappid = "zotai.pdf.metadata.bridge.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    ico_path = get_ico_path()
    if ico_path and os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
        except Exception as e:
            print(f"[Icon] avertisment iconbitmap: {e}")

    try:
        png_path = os.path.join(_ASSETS_DIR, "icon_64.png")
        if os.path.exists(png_path):
            from tkinter import PhotoImage
            img = PhotoImage(file=png_path)
            window.iconphoto(False, img)
            window._icon_photo_ref = img
    except Exception:
        pass
