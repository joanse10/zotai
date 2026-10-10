"""
Stratul de persistență Zotai (SQLite, vezi TZ.md §7).
"""

from db.database import ZotaiDB, default_db_path
from db.repository import TaskRepository

__all__ = ["ZotaiDB", "TaskRepository", "default_db_path"]
