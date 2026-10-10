"""
Integrarea meniului contextual Windows Explorer pentru Zotai (.pdf și .docx pe Windows 10 și 11).

Suportă două niveluri de integrare:
1. Meniul contextual modern Windows 11:
   Înregistrare prin asocierile de aplicații (Open with / Deschide cu):
   - HKCU\\Software\\Classes\\Applications\\Zotai.exe (FriendlyAppName, Icon, shell\\open\\command)
   - HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.pdf\\OpenWithList
   - HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.pdf\\OpenWithProgids
   Permite Zotai să apară în meniul de nivel întâi din Windows 11 la „Deschide cu".

2. Verb shell clasic (Windows 10 / Shift+F10 / Afișează mai multe opțiuni):
   HKCU\\Software\\Classes\\SystemFileAssociations\\.pdf\\shell\\Zotai
       (Default) = "Procesează cu Zotai"
       Icon      = <assets/icon.ico>
       \\command  = "<launcher>" "%1"
"""

import ctypes
import logging
import os
import sys

log = logging.getLogger("zotai")

SUPPORTED_EXTS = [".pdf", ".docx"]
MENU_TITLE = "Procesează cu Zotai"


def _menu_key(ext: str) -> str:
    return rf"Software\Classes\SystemFileAssociations\{ext}\shell\Zotai"


def _fileexts_key(ext: str) -> str:
    return rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\{ext}"


def _progid_key(ext: str) -> str:
    return rf"Software\Classes\Zotai.Document{ext}"


MENU_KEY = _menu_key(".pdf")
OPEN_WITH_APP_KEY = r"Software\Classes\Applications\Zotai.exe"
FILE_EXTS_PDF_KEY = _fileexts_key(".pdf")
PROGID_KEY = _progid_key(".pdf")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _launcher_command() -> str:
    """
    Comandă de lansare a aplicației cu calea fișierului în argv[1].
    În build frozen (PyInstaller) — exe-ul însuși; în dev — pythonw + main.py.
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" "%1"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    launcher = pythonw if os.path.isfile(pythonw) else sys.executable
    main_py = os.path.join(_PROJECT_ROOT, "main.py")
    return f'"{launcher}" "{main_py}" "%1"'


def _icon_path() -> str:
    try:
        from gui.icons import get_ico_path
        p = get_ico_path()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    p = os.path.join(_PROJECT_ROOT, "assets", "icon.ico")
    return p if os.path.isfile(p) else ""


def _notify_shell():
    """Notifică Windows Explorer despre actualizarea asocierilor de fișiere."""
    try:
        SHCNE_ASSOCCHANGED = 0x08000000
        SHCNF_IDLIST = 0x0000
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)
    except Exception:
        pass


def is_registered() -> bool:
    """Verifică dacă Zotai este înregistrat în registry-ul Windows."""
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_KEY):
            return True
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, OPEN_WITH_APP_KEY):
            return True
    except OSError:
        return False


def register_context_menu() -> str:
    """
    Înregistrează Zotai în meniul contextual Windows:
    - Meniul contextual clasic pentru .pdf/.docx (HKCU SystemFileAssociations)
    - Integrarea modernă „Deschide cu" din Windows 11
    """
    if os.name != "nt":
        return "Meniul contextual este suportat doar pe Windows"
    import winreg
    try:
        cmd = _launcher_command()
        icon = _icon_path()
        root = winreg.HKEY_CURRENT_USER

        # 1. Elementul shell clasic „Procesează cu Zotai" pentru SystemFileAssociations (.pdf + .docx)
        for ext in SUPPORTED_EXTS:
            with winreg.CreateKeyEx(root, _menu_key(ext), access=winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, MENU_TITLE)
                if icon:
                    winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
            with winreg.CreateKeyEx(root, _menu_key(ext) + r"\command", access=winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)

        # 2. Integrarea modernă „Deschide cu" din Windows 11 (Applications\Zotai.exe)
        with winreg.CreateKeyEx(root, OPEN_WITH_APP_KEY, access=winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, "Zotai — Procesare PDF")
            if icon:
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
        with winreg.CreateKeyEx(root, OPEN_WITH_APP_KEY + r"\SupportedTypes", access=winreg.KEY_SET_VALUE) as k:
            for ext in SUPPORTED_EXTS:
                winreg.SetValueEx(k, ext, 0, winreg.REG_SZ, "")
        with winreg.CreateKeyEx(root, OPEN_WITH_APP_KEY + r"\shell\open\command", access=winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)

        # 3. Adăugare în OpenWithList pentru fiecare extensie suportată
        for ext in SUPPORTED_EXTS:
            open_list_key = _fileexts_key(ext) + r"\OpenWithList"
            try:
                with winreg.CreateKeyEx(root, open_list_key, access=winreg.KEY_ALL_ACCESS) as k:
                    mru = ""
                    try:
                        mru, _ = winreg.QueryValueEx(k, "MRUList")
                    except OSError:
                        pass
                    existing = {}
                    idx = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(k, idx)
                            existing[name] = val
                            idx += 1
                        except OSError:
                            break
                    found_letter = None
                    for letter, prog in existing.items():
                        if str(prog).lower() == "zotai.exe":
                            found_letter = letter
                            break
                    if not found_letter:
                        for l in "abcdefghijklmnopqrstuvwxyz":
                            if l not in existing and l != "MRUList":
                                found_letter = l
                                break
                        if found_letter:
                            winreg.SetValueEx(k, found_letter, 0, winreg.REG_SZ, "Zotai.exe")
                            new_mru = found_letter + mru.replace(found_letter, "")
                            winreg.SetValueEx(k, "MRUList", 0, winreg.REG_SZ, new_mru)
            except Exception as e:
                log.warning("Nu s-a putut actualiza OpenWithList (%s): %s", ext, e)

        # 4. Asocierea Progid pentru fiecare extensie
        for ext in SUPPORTED_EXTS:
            try:
                progid = f"Zotai.Document{ext}"
                with winreg.CreateKeyEx(root, _fileexts_key(ext) + r"\OpenWithProgids", access=winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, progid, 0, winreg.REG_NONE, b"")
                with winreg.CreateKeyEx(root, _progid_key(ext), access=winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"Document {ext[1:].upper()} (Zotai)")
                    winreg.SetValueEx(k, "FriendlyTypeName", 0, winreg.REG_SZ, "Zotai — Procesare document")
                    if icon:
                        winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
                with winreg.CreateKeyEx(root, _progid_key(ext) + r"\shell\open\command", access=winreg.KEY_SET_VALUE) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
            except Exception as e:
                log.warning("Nu s-a putut configura Progid (%s): %s", ext, e)

        _notify_shell()
        log.info("Meniul contextual înregistrat (%s, Windows 10 + 11 Deschide cu): %s",
                 ", ".join(SUPPORTED_EXTS), cmd)
        return f"✓ S-a adăugat '{MENU_TITLE}' în meniul contextual pentru {'/'.join(SUPPORTED_EXTS)} (inclusiv „Deschide cu” din Windows 11)"
    except OSError as e:
        log.error("Înregistrarea meniului contextual a eșuat: %s", e)
        return f"✕ Eroare de registry: {e}"


def unregister_context_menu() -> str:
    """Elimină Zotai din meniul contextual și listele de asocieri."""
    if os.name != "nt":
        return "Suportat doar pe Windows"
    import winreg
    root = winreg.HKEY_CURRENT_USER

    # Elimină SystemFileAssociations și Progid pentru toate extensiile
    for ext in SUPPORTED_EXTS:
        for key in (_menu_key(ext) + r"\command", _menu_key(ext),
                    _progid_key(ext) + r"\shell\open\command",
                    _progid_key(ext) + r"\shell\open",
                    _progid_key(ext) + r"\shell",
                    _progid_key(ext)):
            try:
                winreg.DeleteKey(root, key)
            except OSError:
                pass

    # Elimină Applications\Zotai.exe
    for sub in (r"\shell\open\command", r"\shell\open", r"\shell", r"\SupportedTypes", ""):
        try:
            winreg.DeleteKey(root, OPEN_WITH_APP_KEY + sub)
        except OSError:
            pass

    _notify_shell()
    log.info("Meniul contextual eliminat")
    return "✓ Elementul a fost eliminat din meniul contextual"
