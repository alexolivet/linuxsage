from __future__ import annotations

import random

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.widget import Widget


class MatrixFlickerOverlay(Widget):
    """A lightweight "matrix-style" flicker overlay.

    This is not a full matrix rain implementation; it's a stylized screen effect:
    - random green vertical strips
    - occasional scanline
    - subtle full-screen brightness flicker

    It is designed to be cheap enough to run on mobile.
    """

    active = BooleanProperty(True)

    # How often to update the flicker pattern.
    update_interval = NumericProperty(0.06)

    # Probability that a given update shows visible flicker.
    flicker_probability = NumericProperty(0.55)

    # Maximum alpha for the full-screen flash.
    flash_max_alpha = NumericProperty(0.10)

    # Maximum alpha for column strips.
    strip_max_alpha = NumericProperty(0.14)

    # How many vertical strips to manage.
    strip_count = NumericProperty(22)

    _event = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas:
            # Full-screen subtle flash
            self._flash_color = Color(0.1, 1.0, 0.35, 0)
            self._flash_rect = Rectangle(pos=self.pos, size=self.size)

            # Optional scanline
            self._scan_color = Color(0.1, 1.0, 0.35, 0)
            self._scan_rect = Rectangle(pos=self.pos, size=(self.width, 2))

            # Vertical strips
            self._strip_colors: list[Color] = []
            self._strip_rects: list[Rectangle] = []
            for _ in range(int(self.strip_count)):
                c = Color(0.1, 1.0, 0.35, 0)
                r = Rectangle(pos=self.pos, size=(1, 1))
                self._strip_colors.append(c)
                self._strip_rects.append(r)

        self.bind(pos=self._sync_geometry, size=self._sync_geometry)
        self.bind(active=self._on_active)
        self.bind(strip_count=self._rebuild)

        Clock.schedule_once(lambda _dt: self._on_active(self, self.active), 0)

    def _rebuild(self, *_):
        # Simple: don't rebuild dynamically (keeps code small). If you change
        # strip_count at runtime, restart app.
        pass

    def _sync_geometry(self, *_):
        self._flash_rect.pos = self.pos
        self._flash_rect.size = self.size

        # Scanline width should always match.
        self._scan_rect.size = (self.width, max(1, self.height * 0.003))

    def _on_active(self, _inst, value: bool):
        if value:
            if self._event is None:
                self._event = Clock.schedule_interval(self._update, self.update_interval)
        else:
            if self._event is not None:
                self._event.cancel()
                self._event = None
            self._clear_visuals()

    def _clear_visuals(self) -> None:
        self._flash_color.a = 0
        self._scan_color.a = 0
        for c in self._strip_colors:
            c.a = 0

    def _update(self, _dt: float) -> None:
        if not self.active or self.width <= 0 or self.height <= 0:
            self._clear_visuals()
            return

        # Decide whether this frame flickers.
        if random.random() > float(self.flicker_probability):
            self._clear_visuals()
            return

        # Full-screen subtle flash
        self._flash_color.a = random.random() * float(self.flash_max_alpha)

        # Scanline occasionally
        if random.random() < 0.35:
            self._scan_color.a = random.random() * (float(self.strip_max_alpha) * 0.9)
            self._scan_rect.pos = (self.x, self.y + random.random() * self.height)
        else:
            self._scan_color.a = 0

        # Vertical strips
        col_w = self.width / max(1, len(self._strip_rects))
        for i, (c, r) in enumerate(zip(self._strip_colors, self._strip_rects, strict=False)):
            if random.random() < 0.55:
                c.a = random.random() * float(self.strip_max_alpha)

                h = self.height * (0.15 + random.random() * 0.85)
                y = self.y + random.random() * (self.height - h)

                r.pos = (self.x + i * col_w, y)
                r.size = (max(1, col_w * (0.35 + random.random() * 0.9)), h)
            else:
                c.a = 0
