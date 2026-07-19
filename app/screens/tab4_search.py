from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from kivy.clock import Clock
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.utils import get_color_from_hex
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import TwoLineListItem
from kivymd.uix.screen import MDScreen

try:
    from app.services.db_initializer import DatabaseInitializer
    from app.services.db_service import DatabaseService
except ModuleNotFoundError:  # pragma: no cover
    # Fallback for packaging modes where `app` isn't a package.
    from services.db_initializer import DatabaseInitializer  # type: ignore
    from services.db_service import DatabaseService  # type: ignore


class Tab4SearchScreen(MDScreen):
    # UI state
    is_initializing = BooleanProperty(False)
    has_error = BooleanProperty(False)
    is_ready = BooleanProperty(False)

    status_text = StringProperty("DB: not initialized")
    error_text = StringProperty("")
    message_text = StringProperty("")

    # Internal
    _executor: ThreadPoolExecutor | None = None
    _db_path: Path | None = None
    _init_started = BooleanProperty(False)

    _debounce_event = None
    _search_generation = NumericProperty(0)
    _dialog: MDDialog | None = None

    def on_view_ready(self) -> None:
        """Called from KV once ids are available."""

        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1)

        # Kick off initialization early. If the user never opens the tab, it's
        # still safe; it happens in a worker thread.
        self._ensure_initialized()

    def on_pre_enter(self, *args):
        self._ensure_initialized()

    def retry_init(self) -> None:
        self.has_error = False
        self.error_text = ""
        self.status_text = "Retrying DB initialization..."
        self._init_started = False
        self.is_ready = False
        self._db_path = None
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if self._init_started:
            return
        self._init_started = True

        self.is_initializing = True
        self.has_error = False
        self.is_ready = False
        self.message_text = ""
        self.status_text = "Initializing DB..."

        assert self._executor is not None
        future = self._executor.submit(self._init_worker)
        future.add_done_callback(
            lambda f: Clock.schedule_once(partial(self._on_init_done, f))
        )

    def _init_worker(self) -> dict[str, Any]:
        initializer = DatabaseInitializer()
        writable_path = initializer.initialize()

        service = DatabaseService(writable_path)
        health = service.health_check()

        # The new DB schema uses (command, description, category). Older DBs may
        # have (command, description, examples). We only require command +
        # description to function.
        if not health.get("has_required_table", health.get("table_exists")):
            found_cols = ", ".join(health.get("columns", []) or [])
            raise RuntimeError(
                "Database does not contain a usable commands table. "
                "Required columns: command, description. "
                f"Found columns: {found_cols or '(unknown)'}"
            )

        return {"db_path": writable_path, "health": health}

    def _on_init_done(self, future, _dt) -> None:
        self.is_initializing = False

        try:
            payload = future.result()
        except Exception as exc:
            self.has_error = True
            self.is_ready = False
            self.error_text = f"DB init failed: {exc}"
            self.status_text = "DB: error"
            return

        self._db_path = payload["db_path"]
        health = payload["health"]
        self.is_ready = True
        self.has_error = False
        self.error_text = ""
        self.status_text = f"DB ready, rows: {health.get('row_count', 0)}"

    def on_search_text(self, text: str) -> None:
        if not self.is_ready:
            return

        if self._debounce_event is not None:
            self._debounce_event.cancel()

        self._debounce_event = Clock.schedule_once(
            lambda _dt: self._trigger_search(text), 0.3
        )

    def _trigger_search(self, text: str) -> None:
        if not self.is_ready or self._db_path is None:
            return

        q = (text or "").strip()
        if not q:
            self.message_text = ""
            self._render_results([])
            return

        self._search_generation += 1
        current_gen = int(self._search_generation)
        self.message_text = "Searching..."

        assert self._executor is not None
        future = self._executor.submit(self._search_worker, self._db_path, q)
        future.add_done_callback(
            lambda f: Clock.schedule_once(
                partial(self._on_search_done, f, current_gen, q)
            )
        )

    @staticmethod
    def _search_worker(db_path: Path, query: str) -> list[dict[str, Any]]:
        return DatabaseService(db_path).search_commands(query=query, limit=50)

    def _on_search_done(self, future, generation: int, query: str, _dt) -> None:
        if generation != int(self._search_generation):
            # Stale result from an older query.
            return

        try:
            results = future.result()
        except Exception as exc:
            self.message_text = f"Search failed: {exc}"
            self._render_results([])
            return

        if query.strip() and not results:
            self.message_text = "No results found"
        else:
            self.message_text = ""

        self._render_results(results)

    def _render_results(self, results: list[dict[str, Any]]) -> None:
        results_list = self.ids.get("results_list")
        if results_list is None:
            return

        results_list.clear_widgets()

        for r in results:
            cmd = (r.get("command") or "").strip() or "(unknown)"
            desc = (r.get("description") or "").strip() or "(no description)"
            category = (r.get("category") or "").strip()

            secondary = desc
            if category and desc:
                secondary = f"{category} — {desc}"
            elif category:
                secondary = category

            item = TwoLineListItem(
                text=cmd,
                secondary_text=secondary,
                on_release=partial(self._open_details_dialog, r),
            )

            # KivyMD list item coloring: apply after init for compatibility.
            # App background is light (#FDEB9E), so keep list text dark.
            primary = get_color_from_hex("#06202B")
            secondary = get_color_from_hex("#06202B")
            secondary[3] = 0.65

            if hasattr(item, "theme_text_color") and hasattr(item, "text_color"):
                item.theme_text_color = "Custom"
                item.text_color = primary

            # Primary label
            if hasattr(item, "theme_text_color"):
                item.theme_text_color = "Custom"
            if hasattr(item, "text_color"):
                item.text_color = primary

            # Secondary label (property names vary across KivyMD versions)
            for attr in ("theme_secondary_text_color", "secondary_theme_text_color"):
                if hasattr(item, attr):
                    setattr(item, attr, "Custom")

            for attr in ("secondary_text_color", "secondary_color"):
                if hasattr(item, attr):
                    setattr(item, attr, secondary)

            # Last-resort: force colors directly on the internal labels once
            # the KV template has been applied.
            def _apply_label_colors(_dt):
                ids = getattr(item, "ids", None) or {}

                for key in ("_lbl_primary", "lbl_primary", "primary_label"):
                    if key in ids and hasattr(ids[key], "color"):
                        ids[key].color = primary

                for key in ("_lbl_secondary", "lbl_secondary", "secondary_label"):
                    if key in ids and hasattr(ids[key], "color"):
                        ids[key].color = secondary

            results_list.add_widget(item)
            Clock.schedule_once(_apply_label_colors, 0.01)

    def _open_details_dialog(self, result: dict[str, Any], *_args) -> None:
        if self._dialog is not None:
            self._dialog.dismiss()
            self._dialog = None

        cmd = (result.get("command") or "").strip() or "(unknown)"
        desc = (result.get("description") or "").strip() or "(no description)"
        category = (result.get("category") or "").strip()
        examples = (result.get("examples") or "").strip()

        parts: list[str] = []
        if category:
            parts.append(f"Category:\n{category}")
        parts.append(f"Description:\n{desc}")
        if examples:
            parts.append(f"Examples:\n{examples}")

        text = "\n\n".join(parts)

        self._dialog = MDDialog(
            title=cmd,
            text=text,
            buttons=[],
        )
        self._dialog.open()

    def on_leave(self, *args):
        # Avoid leaving dialogs open when switching tabs.
        if self._dialog is not None:
            self._dialog.dismiss()
            self._dialog = None
