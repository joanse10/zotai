"""
Configurarea jurnalizării Zotai.

Jurnalele se scriu în <rădăcina aplicației>/logs/zotai.log cu rotație
(3 fișiere câte 1 MB) și se dublează în stderr pentru depanare în consolă.
Nivelul: variabila de mediu ZOTAI_DEBUG=1 activează DEBUG.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "zotai.log"
_initialized = False


def default_log_dir() -> str:
    from core.paths import log_dir
    return log_dir()


def setup_logging() -> logging.Logger:
    """Inițializare idempotentă a loggerului rădăcină 'zotai'."""
    global _initialized
    log = logging.getLogger("zotai")
    if _initialized:
        return log
    _initialized = True

    level = logging.DEBUG if os.environ.get("ZOTAI_DEBUG") else logging.INFO
    log.setLevel(level)
    log.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de fișier cu rotație
    try:
        os.makedirs(default_log_dir(), exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(default_log_dir(), LOG_FILE_NAME),
            maxBytes=1024 * 1024, backupCount=3, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except Exception as e:
        print(f"[logging] Nu s-a putut deschide fișierul de jurnal: {e}")

    # Consolă (stderr)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    log.addHandler(sh)

    log.info("=== Zotai pornit ===")
    return log
