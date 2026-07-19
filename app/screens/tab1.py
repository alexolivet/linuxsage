from __future__ import annotations

import os
import re
import shutil
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.screen import MDScreen

SLIDES: list[dict[str, str]] = [
    {
        "id": "Slide 1",
        "title": "Welcome to Linux Pocket Oracle",
        "content": """
<h3>First-time? Here's the tour</h3>
<p>Search, explore, and save commands all without leaving your device.</p>
<p>Open Settings to personalise your experience.</p>
""",
    },
    {
        "id": "Slide 2",
        "title": "The Terminal Dilemma",
        "content": """
<h3>Knowledge gaps waste time</h3>
<p>Memorising obscure flags? Googling on a tiny screen? We built an open-source app to fix it.</p>
""",
    },
    {
        "id": "Slide 3",
        "title": "Instant Terminal Mastery",
        "content": """
<h3>Wizard-level commands at your fingertips</h3>
<p>Predictive search pulls instant explanations from our built-in Linux command database.</p>
<p>Every result is verified manually - no bots, just human-curated accuracy.</p>
""",
    },
    {
        "id": "Slide 4",
        "title": "Built for Speed and Safety",
        "content": """
<h3>Offline by design</h3>
<p>Command database and fully offline chat - private, local, secure with zero data leaving your device.</p>
<p>Works anywhere - on a train, in a server room, or on a plane.</p>
""",
    },
    {
        "id": "Slide 5",
        "title": "Your Linux Command Database",
        "content": """
<h3>Hand-crafted knowledge base</h3>
<p>Hundreds of thousands of commands, examples, and permission strings ready for instant lookup.</p>
<p>All data lives on-device; you never need a connection.</p>
""",
    },
    {
        "id": "Slide 6",
        "title": "Real-time Search Demo",
        "content": """
<h3>Try it now - chmod</h3>
<p>Type chmod, get an instant breakdown, then tap to copy the exact syntax.</p>
<p>Need more help? Open the offline chat and ask securely.</p>
""",
    },
    {
        "id": "Slide 7",
        "title": "Settings - Make It Yours",
        "content": """
<h3>Settings Page</h3>
<p>Switch themes, set language, toggle notifications.</p>
<p>Under RSS Feed Manager add, remove, or switch feeds to keep your knowledge current.</p>
""",
    },
    {
        "id": "Slide 8",
        "title": "RSS Feed Integration",
        "content": """
<h3>Stay Updated with RSS</h3>
<p>Subscribe to any RSS feed you trust - security advisories, distro release notes, dev blogs.</p>
<p>Select a feed in Settings; new entries automatically appear in your command list.</p>
""",
    },
    {
        "id": "Slide 9",
        "title": "Pure Open-Source, No Paywalls",
        "content": """
<h3>Free forever, built by hand</h3>
<p>No subscriptions, no ads, no hidden costs.</p>
<p>Contribute ideas on GitHub or simply enjoy the tool - it stays open and community-driven.</p>
""",
    },
    {
        "id": "Slide 10",
        "title": "Join the Movement",
        "content": """
<h3>Linux mastery, open and offline</h3>
<p>Use it, suggest improvements, expand the database.</p>
<p>Let's put safe, offline Linux power in every pocket - together.</p>
""",
    },
]


class Tab1Screen(MDScreen):
    """Home tab: auto-advancing pitch deck and settings menu."""

    slide_index = NumericProperty(0)  # 0-based
    slide_id = StringProperty("")
    slide_title = StringProperty("")
    slide_content = StringProperty("")

    autoplay_interval_s = NumericProperty(5.0)
    _settings_dialog = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._autoplay_event: Optional[object] = None

    def open_settings(self):
        """Navigate to the settings screen."""
        from kivy.app import App
        app = App.get_running_app()
        if app.root:
            app.root.current = "settings"

    def reset_database(self, *args):
        """Reset/refresh the writable DB by deleting it and copying the bundled DB again."""

        try:
            from app.services.db_initializer import DatabaseInitializer
            from app.services.paths import get_writable_db_path

            writable = get_writable_db_path()
            if writable.exists():
                writable.unlink()

            DatabaseInitializer().initialize()
            print("Database refreshed.")
        except Exception as e:
            print(f"Database refresh failed: {e}")

        if self._settings_dialog:
            self._settings_dialog.dismiss()

    def reset_model(self, *args):
        """Reset the offline model by deleting downloaded model files.

        After this, open the Chat tab and tap the download button to fetch the
        model again.
        """

        try:
            app = App.get_running_app()
            model_dir = os.path.join(app.user_data_dir, "onllm_models")

            # Delete model directory contents (best-effort)
            shutil.rmtree(model_dir, ignore_errors=True)
            os.makedirs(model_dir, exist_ok=True)

            print("Model files cleared. Re-download from the Chat tab.")
        except Exception as e:
            print(f"Model reset failed: {e}")

        if self._settings_dialog:
            self._settings_dialog.dismiss()

    def on_kv_post(self, base_widget):
        # Ensure initial slide content is set once KV ids exist.
        self.set_slide(0)
        self.start_autoplay()

    def set_slide(self, idx: int) -> None:
        idx = max(0, min(idx, len(SLIDES) - 1))
        self.slide_index = idx

        slide = SLIDES[idx]
        self.slide_id = slide["id"]
        self.slide_title = slide["title"]
        self.slide_content = self._html_to_markup(slide["content"])

    def start_autoplay(self) -> None:
        if self._autoplay_event is not None:
            return
        self._autoplay_event = Clock.schedule_interval(
            self._advance_slide, self.autoplay_interval_s
        )

    def stop_autoplay(self) -> None:
        if self._autoplay_event is None:
            return
        self._autoplay_event.cancel()
        self._autoplay_event = None

    def _advance_slide(self, _dt) -> None:
        next_idx = (self.slide_index + 1) % len(SLIDES)
        self.set_slide(next_idx)

    @staticmethod
    def _html_to_markup(html: str) -> str:
        """Convert a tiny subset of HTML to Kivy markup.

        KivyMD's MDLabel supports markup, not HTML.
        """

        s = html.strip()

        # Headings
        s = re.sub(
            r"<h3>(.*?)</h3>",
            lambda m: (
                f"[color=077a7d][size=22sp][b]{m.group(1).strip()}[/b][/size][/color]\n"
            ),
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Bold (also add a highlight color)
        s = re.sub(
            r"<strong>(.*?)</strong>",
            lambda m: f"[color=077a7d][b]{m.group(1).strip()}[/b][/color]",
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Paragraphs -> spacing
        s = re.sub(r"</?p>", "\n\n", s, flags=re.IGNORECASE)

        # Strip any remaining tags
        s = re.sub(r"<[^>]+>", "", s)

        # Clean up whitespace
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()
