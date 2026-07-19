"""Buildozer entrypoint.

Keep this file at the repository root.
The real app lives in the `app/` package.

We also ensure the directory containing this file is on `sys.path` so the
`sibling` package directory `app/` can always be imported on Android.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Reduce noisy/non-fatal provider errors on minimal Linux installs.
# - mtdev requires libmtdev; disable it if not present.
os.environ.setdefault("KIVY_NO_MTDEV", "1")

_root_dir = Path(__file__).resolve().parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from app.main import LinuxKnowledgeBaseApp


if __name__ == "__main__":
    LinuxKnowledgeBaseApp().run()
