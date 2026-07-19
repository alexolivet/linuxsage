from __future__ import annotations

import html
import re
import webbrowser
from typing import Any

from kivy.clock import Clock
from kivy.network.urlrequest import UrlRequest
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.uix.button import MDFlatButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.screen import MDScreen


class Tab2Screen(MDScreen):
    """Topics tab: single-article RSS reader (news source selectable in Settings)."""

    feed_name = StringProperty("Linux Today")
    feed_url = StringProperty("https://www.linuxtoday.com/feed/")

    # UI state
    is_loading = BooleanProperty(False)
    has_error = BooleanProperty(False)
    status_text = StringProperty("Linux Today: not loaded")
    error_text = StringProperty("")

    # Feed data
    items = ListProperty([])  # list[dict[str, Any]]
    current_index = NumericProperty(0)
    position_text = StringProperty("")  # e.g. "1 / 20"

    # Current article fields (bound to KV)
    current_title = StringProperty("")
    current_link = StringProperty("")
    current_pub_date = StringProperty("")
    current_author = StringProperty("")
    current_guid = StringProperty("")
    current_categories = StringProperty("")
    current_summary = StringProperty("")
    current_body = StringProperty("")

    # Internal
    _loaded_once = BooleanProperty(False)
    _req: UrlRequest | None = None
    _leave_dialog: MDDialog | None = None

    def on_view_ready(self) -> None:
        """Called from KV (on_kv_post) once ids exist.

        NOTE: Tab2Screen is embedded inside an MDBottomNavigationItem, so
        traditional Screen events like `on_pre_enter` are not reliable here.
        """

        if not self._loaded_once and not self.is_loading:
            Clock.schedule_once(lambda _dt: self.refresh(), 0)

    def on_pre_enter(self, *args):
        # Keep as a best-effort fallback for configurations where it does fire.
        if not self._loaded_once and not self.is_loading:
            Clock.schedule_once(lambda _dt: self.refresh(), 0)

    def refresh(self) -> None:
        if self.is_loading:
            return

        self.is_loading = True
        self.has_error = False
        self.error_text = ""
        self.status_text = f"Fetching {self.feed_name} RSS..."

        headers = {"User-Agent": "LinuxKnowledgeBaseApp (Kivy; RSS reader)"}

        # On some platforms HTTPS verification requires an explicit CA bundle.
        ca_file = None
        try:
            import certifi
            ca_file = certifi.where()
        except Exception:
            ca_file = None

        self._req = UrlRequest(
            self.feed_url,
            on_success=self._on_success,
            on_failure=self._on_failure,
            on_error=self._on_error,
            req_headers=headers,
            timeout=15,
            verify=True,
            ca_file=ca_file,
        )

    def next_article(self) -> None:
        if not self.items:
            return

        next_idx = (int(self.current_index) + 1) % len(self.items)
        self.set_current_index(next_idx)

    def open_current_article(self) -> None:
        link = (self.current_link or "").strip()
        if not link:
            return

        # Warn the user that we will leave the app (open external browser).
        if self._leave_dialog is not None:
            self._leave_dialog.dismiss()
            self._leave_dialog = None

        self._leave_dialog = MDDialog(
            title="Open article in browser?",
            text=(
                "You're about to leave the app and open this article in your browser.\n\n"
                "Continue?"
            ),
            buttons=[
                MDFlatButton(text="CANCEL", on_release=self._dismiss_leave_dialog),
                MDFlatButton(
                    text="OPEN",
                    on_release=lambda _btn: self._confirm_open_external(link),
                ),
            ],
        )
        self._leave_dialog.open()

    def _dismiss_leave_dialog(self, *_args) -> None:
        if self._leave_dialog is None:
            return
        self._leave_dialog.dismiss()
        self._leave_dialog = None

    def _confirm_open_external(self, link: str, *_args) -> None:
        import os, sys, webbrowser
        self._dismiss_leave_dialog()
        try:
            if sys.platform.startswith("linux"):
                # WSL (Windows Subsystem for Linux)
                if os.path.exists('/usr/bin/wslview'):
                    os.system(f'wslview "{link}"')
                    return
                elif os.system("which explorer.exe > /dev/null 2>&1") == 0:
                    os.system(f'explorer.exe "{link}"')
                    return
                elif os.system("which xdg-open > /dev/null 2>&1") == 0:
                    os.system(f'xdg-open "{link}"')
                    return
            webbrowser.open(link, new=2)
        except Exception as e:
            print(f"Failed to open URL: {e}")

    def set_current_index(self, idx: int) -> None:
        if not self.items:
            self._set_current_article({})
            self.position_text = "0 / 0"
            return

        idx = max(0, min(idx, len(self.items) - 1))
        self.current_index = idx
        self.position_text = f"{idx + 1} / {len(self.items)}"
        self._set_current_article(self.items[idx])

    def _set_current_article(self, item: dict[str, Any]) -> None:
        self.current_title = (item.get("title") or "").strip()
        self.current_link = (item.get("link") or "").strip()
        self.current_pub_date = (item.get("pubDate") or "").strip()
        self.current_author = (item.get("author") or "").strip()
        self.current_guid = (item.get("guid") or "").strip()

        cats = item.get("categories") or []
        if isinstance(cats, list):
            self.current_categories = ", ".join([c for c in cats if c]).strip()
        else:
            self.current_categories = (str(cats) or "").strip()

        self.current_summary = (item.get("summary") or "").strip()
        self.current_body = (item.get("body") or "").strip()

    def _on_success(self, _req: UrlRequest, result: Any) -> None:
        self.is_loading = False

        try:
            items = self._parse_rss(result)
        except Exception as exc:
            self._set_error(f"Parse error: {exc}")
            return

        self.items = items
        self._loaded_once = True

        if not items:
            self.status_text = f"{self.feed_name}: no items"
            self.set_current_index(0)
            return

        self.status_text = f"{self.feed_name}: loaded"
        self.set_current_index(0)

    def _on_failure(self, _req: UrlRequest, result: Any) -> None:
        self._set_error(f"Request failed: {result}")

    def _on_error(self, _req: UrlRequest, error: Any) -> None:
        self._set_error(f"Network error: {error}")

    def _set_error(self, message: str) -> None:
        self.is_loading = False
        self.has_error = True
        self.error_text = message
        self.status_text = f"{self.feed_name}: error"
        self.items = []
        self.current_index = 0
        self.position_text = "0 / 0"
        self._set_current_article({})

        # Close any pending dialog.
        self._dismiss_leave_dialog()

    @staticmethod
    def _parse_rss(payload: Any) -> list[dict[str, Any]]:
        """Parse RSS XML payload into a list of items.

        Enforces "English-only" when the feed provides a <language> tag.
        """

        if payload is None:
            return []

        if isinstance(payload, (bytes, bytearray)):
            xml_text = payload.decode("utf-8", "ignore")
        else:
            xml_text = str(payload)

        xml_text = xml_text.strip()
        first_lt = xml_text.find("<")
        if first_lt > 0:
            xml_text = xml_text[first_lt:]

        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_text)

        # English-only guard (Linux Today advertises en-US)
        lang = (root.findtext(".//language") or "").strip().lower()
        if lang and not lang.startswith("en"):
            return []

        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "content": "http://purl.org/rss/1.0/modules/content/",
        }

        parsed: list[dict[str, Any]] = []

        for item_el in root.findall(".//item"):
            title = (item_el.findtext("title") or "").strip()
            link = (item_el.findtext("link") or "").strip()
            pub_date = (item_el.findtext("pubDate") or "").strip()
            guid = (item_el.findtext("guid") or "").strip()

            author = (item_el.findtext("dc:creator", namespaces=ns) or "").strip()

            categories = [
                (c.text or "").strip() for c in item_el.findall("category") if c is not None
            ]

            desc_html = (item_el.findtext("description") or "").strip()
            content_html = (item_el.findtext("content:encoded", namespaces=ns) or "").strip()

            desc_text = Tab2Screen._html_to_text(desc_html)
            content_text = Tab2Screen._html_to_text(content_html)

            # Summary: prefer description; fall back to content.
            summary = desc_text or content_text
            summary = re.sub(r"\s+", " ", summary).strip()
            if len(summary) > 240:
                summary = summary[:237].rstrip() + "..."

            # Body: prefer full content if present; otherwise description.
            body = content_text or desc_text
            body = body.strip()

            parsed.append(
                {
                    "title": title,
                    "link": link,
                    "pubDate": pub_date,
                    "guid": guid,
                    "author": author,
                    "categories": categories,
                    "summary": summary,
                    "body": body,
                }
            )

        return parsed

    @staticmethod
    def _html_to_text(text: str) -> str:
        """Convert common HTML from RSS into readable plain text."""

        if not text:
            return ""

        s = text.replace("<![CDATA[", "").replace("]]>", "")
        s = html.unescape(s)

        # Preserve some structure before stripping tags
        s = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.IGNORECASE)
        s = re.sub(r"</\s*p\s*>", "\n\n", s, flags=re.IGNORECASE)
        s = re.sub(r"<\s*p\b[^>]*>", "", s, flags=re.IGNORECASE)
        s = re.sub(r"</\s*li\s*>", "\n", s, flags=re.IGNORECASE)
        s = re.sub(r"<\s*li\b[^>]*>", "• ", s, flags=re.IGNORECASE)

        # Strip the rest of tags
        s = re.sub(r"<[^>]+>", "", s)

        # Clean up whitespace
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()