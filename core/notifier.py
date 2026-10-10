"""
Notificări de sistem Windows (Toast) pentru Zotai.

Backenduri în ordinea priorității:
1. windows-toasts (WinRT) — notificări native cu identitatea aplicației.
2. PowerShell + Windows Runtime XML — rezervă fără dependențe.
3. Doar jurnal — dacă niciuna dintre metode nu este disponibilă.

Se activează/dezactivează prin setarea 'toast' din SQLite
(Setări -> Windows & Integrare).
"""

import logging
import os
import subprocess
from typing import Optional

log = logging.getLogger("zotai")

APP_NAME = "Zotai"

# AUMID PowerShell — folosit pentru afișarea notificării de rezervă
_PS_APPID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_PS_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$nodes = $template.GetElementsByTagName("text")
$nodes.Item(0).AppendChild($template.CreateTextNode($env:ZOTAI_TOAST_TITLE)) | Out-Null
$nodes.Item(1).AppendChild($template.CreateTextNode($env:ZOTAI_TOAST_BODY)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:ZOTAI_TOAST_APPID).Show($toast)
"""


class Notifier:
    """Trimite notificări toast. Sigură pentru thread-uri, cu apeluri neblocante."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._toaster: Optional[object] = None
        self._backend = self._detect_backend()

    def _detect_backend(self) -> str:
        if os.name != "nt":
            return "none"
        try:
            from windows_toasts import WindowsToaster
            self._toaster = WindowsToaster(APP_NAME)
            return "winrt"
        except Exception as e:
            log.warning("windows-toasts indisponibil, revin la PowerShell: %s", e)
            return "powershell"

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    # ------------------------------------------------------------------
    def info(self, title: str, body: str = ""):
        self._notify(title, body)

    def success(self, title: str, body: str = ""):
        self._notify(f"✅ {title}", body)

    def error(self, title: str, body: str = ""):
        self._notify(f"❌ {title}", body)

    # ------------------------------------------------------------------
    def _notify(self, title: str, body: str):
        if not self.enabled:
            return
        try:
            if self._backend == "winrt":
                self._notify_winrt(title, body)
            elif self._backend == "powershell":
                self._notify_powershell(title, body)
            else:
                log.info("toast (off): %s — %s", title, body)
        except Exception as e:
            log.warning("Nu s-a putut afișa notificarea: %s", e)

    def _notify_winrt(self, title: str, body: str):
        from windows_toasts import Toast
        toast = Toast()
        toast.text_fields = [title, body]
        self._toaster.show_toast(toast)

    def _notify_powershell(self, title: str, body: str):
        env = dict(os.environ,
                   ZOTAI_TOAST_TITLE=title,
                   ZOTAI_TOAST_BODY=body,
                   ZOTAI_TOAST_APPID=_PS_APPID)
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_SCRIPT],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs
        )
