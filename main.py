"""
Punctul de intrare principal al aplicației Zotai.
"""

import sys
import customtkinter as ctk
from core.logging_setup import setup_logging
from gui.main_window import MainWindow

log = setup_logging()

# Modul de aspect se adaptează la tema sistemului
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


def main():
    from core import single_instance

    args = sys.argv[1:]
    if not single_instance.try_acquire():
        # Aplicația rulează deja — îi transmitem fișierele și ne oprim
        single_instance.forward_to_existing(args)
        return

    app = MainWindow()
    if args:
        app._process_incoming_paths(args)
    app.mainloop()


if __name__ == "__main__":
    main()
