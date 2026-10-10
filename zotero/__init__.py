"""
Integrarea cu Zotero: tipuri de documente, convertor de metadate,
și conector la API-ul local Zotero (127.0.0.1:23119).
"""

from zotero.item_types import ITEM_TYPES, type_key, type_label, all_labels, display_label
from zotero.convert import to_zotero_item

__all__ = [
    "ITEM_TYPES", "type_key", "type_label", "all_labels", "display_label",
    "to_zotero_item",
]
