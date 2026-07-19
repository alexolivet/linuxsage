"""Runtime path fixes for python-for-android / buildozer.

This project has historically switched between these layouts:

1) repo-root contains an `app/` package (preferred)
   - main.py
   - app/__init__.py
   - app/screens/...

2) repo-root is itself treated as the "app" and contains `screens/`, `services/`, ...
   - main.py
   - screens/...

Depending on buildozer `source.dir` and how code is copied into the APK, the
Python import path may not allow `import app...`.

Python automatically imports `sitecustomize` (if present on sys.path) at
startup, so we use it to ensure imports are robust.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _ensure_on_syspath(p: Path) -> None:
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


here = Path(__file__).resolve().parent
_ensure_on_syspath(here)

# Determine where the real sources live.
app_dir = here / "app"
flat_has_screens = (here / "screens").is_dir()

# Create/patch a package named `app` so `import app.screens...` works.
if "app" not in sys.modules:
    if app_dir.is_dir():
        pkg_path = app_dir
    elif flat_has_screens:
        # buildozer may have copied the *contents* of the app into the runtime
        # directory, so treat this directory as the `app` package.
        pkg_path = here
    else:
        pkg_path = None

    if pkg_path is not None:
        m = types.ModuleType("app")
        m.__path__ = [str(pkg_path)]  # type: ignore[attr-defined]
        sys.modules["app"] = m

# Also ensure the *parent* of the package path is on sys.path.
# (needed for normal package import machinery)
if app_dir.is_dir():
    _ensure_on_syspath(here)

# Minimal debug marker (shows up in logcat as "python" output)
print(f"[sitecustomize] sys.path[0:3]={sys.path[:3]} app_dir_exists={app_dir.is_dir()} flat_screens={flat_has_screens}")
