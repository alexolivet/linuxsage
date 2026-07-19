from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivymd.uix.screen import MDScreen


class SplashScreen(MDScreen):
    """Splash screen with a simple letter-by-letter typing animation.

    Features:
    - Header types in letter-by-letter.
    - Blinking cursor '_' that blinks independently.
    - A sub-header/menu fades in once typing finishes.
    """

    header_full_text = StringProperty("linux sage")

    # Seconds between characters (smaller = faster typing)
    typing_interval = NumericProperty(0.04)

    # Cursor blink speed
    cursor_blink_interval = NumericProperty(0.45)

    _typing_event = None
    _cursor_event = None
    _typing_index = 0
    _typed_text = ""
    _cursor_on = BooleanProperty(True)
    _post_shown = BooleanProperty(False)
    _started_once = BooleanProperty(False)

    def on_kv_post(self, base_widget):  # noqa: ANN001
        # When the app starts, the SplashScreen is often the initial current
        # screen and some lifecycle events can be timing-sensitive. Ensure we
        # start once after KV ids exist.
        if not self._started_once:
            self._started_once = True
            Clock.schedule_once(lambda _dt: self._start_animations_if_visible(), 0)

    def on_pre_enter(self, *args):  # noqa: ANN002
        super().on_pre_enter(*args)
        self._start_animations_if_visible(force=True)

    def on_leave(self, *args):  # noqa: ANN002
        self.stop_typing()
        self.stop_cursor()
        return super().on_leave(*args)

    def start_typing(self) -> None:
        """Start or restart the typing animation."""
        self.stop_typing()

        # Start at 1 so the first tick shows the first character.
        self._typing_index = 1

        label = self.ids.get("header_label")
        if not label:
            Logger.warning("LinuxKB: header_label not found; typing animation skipped")
            return

        # Reset the fade-in elements (we fade them in once typing is complete).
        self._post_shown = False
        post_box = self.ids.get("post_typing_box")
        if post_box is not None:
            post_box.opacity = 0

        self._typed_text = ""
        self._render_header()

        # Show the first character immediately so it doesn't feel "delayed".
        self._type_next_char(0.0)

        self._typing_event = Clock.schedule_interval(
            self._type_next_char, self.typing_interval
        )

    def stop_typing(self) -> None:
        if self._typing_event is not None:
            self._typing_event.cancel()
            self._typing_event = None

    def start_cursor(self) -> None:
        """Start blinking the cursor '_' independently of typing."""
        self.stop_cursor()
        self._cursor_on = True

        # Ensure the header exists before scheduling.
        if not self.ids.get("header_label"):
            Logger.warning("LinuxKB: header_label not found; cursor blink skipped")
            return

        self._render_header()

        self._cursor_event = Clock.schedule_interval(
            self._toggle_cursor, self.cursor_blink_interval
        )

    def stop_cursor(self) -> None:
        if self._cursor_event is not None:
            self._cursor_event.cancel()
            self._cursor_event = None

    def _toggle_cursor(self, _dt: float) -> None:
        if not self.ids.get("header_label"):
            self.stop_cursor()
            return

        self._cursor_on = not self._cursor_on
        self._render_header()

    def _fade_in_post_typing(self) -> None:
        """Fade in the sub-header/menu right after typing finishes."""
        if self._post_shown:
            return
        self._post_shown = True

        post_box = self.ids.get("post_typing_box")
        if not post_box:
            return

        Animation(opacity=1, d=0.35, t="out_quad").start(post_box)

    # def _start_animations_if_visible(self, force: bool = False) -> None:
    #     """Start cursor+typing when this screen is (or is about to be) visible."""
    #     # If we have a manager, only run when we're the current screen unless forced.
    #     if not force and self.manager is not None and self.manager.current != self.name:
    #         return

    #     self.start_cursor()
    #     self.start_typing()

    def _start_animations_if_visible(self, force=False):
        if not force and self.manager is not None and self.manager.current != self.name:
            return
        label = self.ids.get("header_label")
        if not label:
            return  # <-- silently skip if not ready
        self.start_cursor()
        self.start_typing()

    def _render_header(self) -> None:
        """Render typed text + blinking cursor into the single header label."""
        label = self.ids.get("header_label")
        if not label:
            return

        cursor = "_" if self._cursor_on else " "
        label.text = f"[b]{self._typed_text}{cursor}[/b]"

    def _type_next_char(self, _dt: float) -> None:
        label = self.ids.get("header_label")
        if not label:
            self.stop_typing()
            return

        if self._typing_index > len(self.header_full_text):
            self.stop_typing()
            self._fade_in_post_typing()
            return

        current = self.header_full_text[: self._typing_index]
        self._typed_text = current
        self._render_header()
        self._typing_index += 1
