from __future__ import annotations

from kivy.properties import StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivymd.uix.label import MDLabel


class MenuEntryLabel(ButtonBehavior, MDLabel):
    """Clickable label used for the splash "menu" row."""

    entry_name = StringProperty("")
