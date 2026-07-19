from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.utils import platform


APP_DIR_NAME = "linux_knowledge_base"
# NOTE:
# The bundled database was updated to `knowledge_base_01.db` and its schema is:
#   command (text), description (text), category (text)
# We keep the filename here as the single source of truth.
DB_FILENAME = "knowledge_base_01.db"


def get_user_data_dir() -> Path:
    """Return a writable per-user app data directory.

    Uses Kivy's `App.user_data_dir` when available (works well on desktop and
    Android). Falls back to `~/.linux_knowledge_base` when called before the app
    is running.
    """

    app = App.get_running_app()
    if app is not None and getattr(app, "user_data_dir", None):
        return Path(app.user_data_dir)

    # Fallback for non-app contexts (e.g., unit tests or early imports).
    return Path.home() / f".{APP_DIR_NAME}"


def get_writable_db_path() -> Path:
    """Single source of truth for the DB path used by the app."""

    base = get_user_data_dir() / "databases"
    return base / DB_FILENAME


def get_bundled_db_path() -> Path:
    """Path to the DB shipped with the app source/bundle.

    Expected location (in this repo):
      assets/databases/knowledge_base_01.db

    Note: We keep assets at the repository root.
    """

    here = Path(__file__).resolve()

    # If this file lives at app/services/paths.py -> repo_root is 2 levels up.
    # If it lives at services/paths.py (flattened) -> repo_root is 1 level up.
    candidates = [here.parents[2], here.parents[1]]
    for repo_root in candidates:
        p = repo_root / "assets" / "databases" / DB_FILENAME
        if p.exists():
            return p

    # Last-resort: return the most likely path (helps error messages).
    return candidates[0] / "assets" / "databases" / DB_FILENAME


def is_android() -> bool:
    return platform == "android"
