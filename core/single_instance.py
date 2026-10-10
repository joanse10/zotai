"""
Instanță unică a aplicației (mutex Windows + cutie poștală de fișiere).

La pornire, procesul înregistrează un mutex numit. Al doilea proces:
- își depune căile într-un „inbox” din directorul de date,
- aduce fereastra existentă în față,
- se termină imediat.

Instanța principală citește inbox-ul periodic (_poll_inbox) și procesează
fișierele ca și cum ar fi fost lansate direct.
"""

import ctypes
import logging
import os
import sys
import time
import uuid

from core.paths import data_dir, is_frozen

log = logging.getLogger("zotai")

# Dev (python main.py) și versiunea instalată nu se blochează una pe alta
_MUTEX_NAME = r"Local\Zotai_SingleInstance" + ("" if is_frozen() else "_Dev")
_ERROR_ALREADY_EXISTS = 183

_mutex_handle = None  # păstrat viu pe durata procesului


def inbox_dir() -> str:
    d = os.path.join(data_dir(), "inbox")
    os.makedirs(d, exist_ok=True)
    return d


def try_acquire() -> bool:
    """Înregistrează instanța principală. Returnează False dacă aplicația rulează deja."""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != _ERROR_ALREADY_EXISTS


def forward_to_existing(paths):
    """Depune căile în inbox-ul instanței existente și o aduce în față."""
    if paths:
        try:
            name = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.txt"
            with open(os.path.join(inbox_dir(), name), "w", encoding="utf-8") as fh:
                fh.write("\n".join(paths))
        except OSError as e:
            log.warning("Nu am putut scrie în inbox: %s", e)
    _activate_existing_window()


def _activate_existing_window():
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    found = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith("Zotai"):
                found.append(hwnd)
        return True

    user32.EnumWindows(EnumProc(enum_cb), 0)
    if found:
        hwnd = found[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)


def drain_inbox() -> list:
    """Citește și șterge toate fișierele din inbox (doar instanța principală)."""
    paths = []
    try:
        names = os.listdir(inbox_dir())
    except OSError:
        return paths
    for name in names:
        if not name.endswith(".txt"):
            continue
        f = os.path.join(inbox_dir(), name)
        try:
            with open(f, encoding="utf-8") as fh:
                paths.extend(line.strip() for line in fh if line.strip())
            os.remove(f)
        except OSError:
            pass
    return paths
