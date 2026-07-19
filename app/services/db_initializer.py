from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

try:
    from app.services.paths import get_bundled_db_path, get_writable_db_path
except ModuleNotFoundError:  # pragma: no cover
    from services.paths import get_bundled_db_path, get_writable_db_path  # type: ignore


@dataclass(frozen=True)
class DatabaseInitializer:
    """First-run initialization: copy the bundled DB into a writable location."""

    bundled_db_path: Path = field(default_factory=get_bundled_db_path)
    writable_db_path: Path = field(default_factory=get_writable_db_path)

    def initialize(self) -> Path:
        """Ensure a writable DB exists and return its path.

        Behavior:
        - Creates the writable directory if needed.
        - Copies the bundled DB if writable DB is missing.
        - Does NOT overwrite an existing writable DB.
        - Validates that the DB file exists after initialization.
        """

        writable_dir = self.writable_db_path.parent
        writable_dir.mkdir(parents=True, exist_ok=True)

        if self.writable_db_path.exists():
            return self.writable_db_path

        if not self.bundled_db_path.exists():
            raise FileNotFoundError(
                "Bundled database not found. Expected at: " f"{self.bundled_db_path}"
            )

        try:
            shutil.copy2(self.bundled_db_path, self.writable_db_path)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Failed to copy bundled database to writable location: "
                f"{self.writable_db_path}"
            ) from exc

        if not self.writable_db_path.exists():
            raise RuntimeError(
                "Database initialization failed: writable DB missing after copy: "
                f"{self.writable_db_path}"
            )

        return self.writable_db_path
