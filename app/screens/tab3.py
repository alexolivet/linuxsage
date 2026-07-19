from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.anchorlayout import AnchorLayout
from kivy.utils import platform
from kivymd.uix.button import MDFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.screen import MDScreen

from app.services.db_service import DatabaseService
from app.services.onllm_engine import DEFAULT_MODELS, NON_LINUX_REFUSAL, OnnxChatEngine
from app.services.paths import get_writable_db_path


DEFAULT_MODEL_NAME = next(iter(DEFAULT_MODELS.keys()))


class Tab3Screen(MDScreen):
    """Offline chat screen (Tab 3) powered by the OnLLM repo approach (ONNX Runtime).

    Notes:
    - First run requires downloading model files.
    - Inference runs in a background thread; UI updates are scheduled via Clock.
    """

    status_text = StringProperty("Offline chat initializing…")
    selected_model = StringProperty(DEFAULT_MODEL_NAME)
    token_text = StringProperty("128")
    is_busy = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine: Optional[OnnxChatEngine] = None
        self._messages: List[Dict[str, str]] = []
        self._bot_stream_label: Optional[MDLabel] = None

        self._token_menu: Optional[MDDropdownMenu] = None
        self._download_dialog: Optional[MDDialog] = None
        self._auto_download_prompted: bool = False

    # ----------------------------
    # Screen init
    # ----------------------------

    def on_view_ready(self) -> None:
        """KV calls this via `on_kv_post`. Safe to call multiple times."""
        if self._engine is not None:
            return

        app = App.get_running_app()
        model_dir = os.path.join(app.user_data_dir, "onllm_models")
        os.makedirs(model_dir, exist_ok=True)

        self._engine = OnnxChatEngine(model_dir=model_dir, models=DEFAULT_MODELS)

        # Dropdown: token count
        token_sizes = [128, 256, 512, 1024]
        token_items = [
            {
                "text": str(t),
                "on_release": lambda x=str(t): self._on_token_selected(x),
            }
            for t in token_sizes
        ]
        self._token_menu = MDDropdownMenu(caller=self.ids.token_btn, items=token_items)

        # Auto-use a single smallest model for offline chat.
        if self._engine.check_model_files(DEFAULT_MODEL_NAME):
            self.status_text = f"Loading model: {DEFAULT_MODEL_NAME}…"
            self._load_model_async(DEFAULT_MODEL_NAME)
        else:
            self.status_text = (
                f"Model '{DEFAULT_MODEL_NAME}' not downloaded yet. Tap download to enable offline chat."
            )
            Clock.schedule_once(lambda *_: self._maybe_prompt_auto_download())

    # ----------------------------
    # Dropdown handlers
    # ----------------------------

    def open_token_menu(self) -> None:
        if self._token_menu:
            self._token_menu.open()

    def _on_token_selected(self, token_text: str) -> None:
        if self._token_menu:
            self._token_menu.dismiss()
        self.token_text = token_text

    def download_default_model(self) -> None:
        """Manual download button (also used as retry)."""
        spec = DEFAULT_MODELS[DEFAULT_MODEL_NAME]
        self._prompt_download(DEFAULT_MODEL_NAME, spec.size_label)

    # ----------------------------
    # Download + load
    # ----------------------------

    def _maybe_prompt_auto_download(self) -> None:
        """Prompt once on first Tab3 open to download the default model."""
        if self._auto_download_prompted:
            return
        self._auto_download_prompted = True

        if not self._engine:
            return

        # Don't prompt if it appeared during a race.
        if self._engine.check_model_files(DEFAULT_MODEL_NAME):
            return

        spec = DEFAULT_MODELS[DEFAULT_MODEL_NAME]
        self._prompt_download(DEFAULT_MODEL_NAME, spec.size_label)

    def _prompt_download(self, model_name: str, size_label: str) -> None:
        if self._download_dialog:
            self._download_dialog.dismiss()

        self._download_dialog = MDDialog(
            title="Download offline model",
            text=(
                f"The offline model '{model_name}' is not downloaded yet.\n"
                f"Download size: {size_label}\n\n"
                "Download now so chat works offline (recommended on Wi‑Fi)."
            ),
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda *_: self._download_dialog.dismiss()),
                MDFlatButton(
                    text="Download",
                    on_release=lambda *_: self._start_download(model_name),
                ),
            ],
        )
        self._download_dialog.open()

    def _start_download(self, model_name: str) -> None:
        if self._download_dialog:
            self._download_dialog.dismiss()

        if not self._engine:
            return

        if self.is_busy:
            self.status_text = "Busy. Please wait…"
            return

        self.is_busy = True
        self.status_text = f"Downloading {model_name}…"

        def _progress(downloaded: int, total: int) -> None:
            if total > 0:
                pct = 100.0 * downloaded / total
                Clock.schedule_once(
                    lambda *_: setattr(self, "status_text", f"Downloading {model_name}: {pct:.1f}%")
                )
            else:
                Clock.schedule_once(
                    lambda *_: setattr(self, "status_text", f"Downloading {model_name}: {downloaded} bytes")
                )

        def _work() -> None:
            try:
                # NOTE: download_and_extract() now also loads the model.
                self._engine.download_and_extract(model_name, progress_cb=_progress)

                def _on_ready(*_):
                    # Model is now loaded in-memory; allow chat immediately.
                    self.status_text = f"Model ready: {model_name}. You can chat offline."
                    self.is_busy = False

                Clock.schedule_once(_on_ready)
            except Exception as e:
                err = str(e)

                def _on_error(*_):
                    self.status_text = f"Download failed: {err}"
                    self.is_busy = False

                Clock.schedule_once(_on_error)

        threading.Thread(target=_work, daemon=True).start()

    def _load_model_async(self, model_name: str) -> None:
        if not self._engine:
            return

        if self.is_busy:
            # If we're already busy (download), load will happen after.
            return

        self.is_busy = True
        self.status_text = f"Loading model: {model_name}…"

        def _work() -> None:
            try:
                self._engine.load(model_name)
                Clock.schedule_once(
                    lambda *_: setattr(self, "status_text", f"Model loaded: {model_name}. You can chat offline.")
                )
            except Exception as e:
                err = str(e)
                Clock.schedule_once(
                    lambda *_args, m=err: setattr(self, "status_text", f"Load failed: {m}")
                )
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "is_busy", False))

        threading.Thread(target=_work, daemon=True).start()

    # ----------------------------
    # DB context (local knowledge base)
    # ----------------------------

    def _build_db_context(self, query: str, limit: int = 5) -> str:
        """Return a short context block from the local SQLite knowledge base.

        This is used for prompt augmentation ("RAG") so the model can prefer the
        app's curated command descriptions.
        """

        q = (query or "").strip()
        if not q:
            return ""

        try:
            db = DatabaseService(get_writable_db_path())
            rows = db.search_commands(q, limit=limit)
        except Exception as e:
            Logger.warning(f"Tab3: DB context lookup failed: {e}")
            return ""

        if not rows:
            return ""

        lines = ["Available Linux commands from local knowledge base:"]
        for r in rows:
            cmd = (r.get("command") or "").strip()
            desc = (r.get("description") or "").strip()
            cat = (r.get("category") or "").strip() or "general"
            if not cmd:
                continue
            lines.append(f"- {cmd} ({cat}): {desc}")

        return "\n".join(lines)

    # ----------------------------
    # Chat actions
    # ----------------------------

    def new_chat(self) -> None:
        """Clear conversation history and reset the chat interface."""
        if self._engine:
            self._engine.stop()  # Ensure any generation stops
        self._messages = []
        self.ids.chat_box.clear_widgets()
        self._bot_stream_label = None
        self.status_text = "New chat started."
    
        # Optional: add UI feedback (toast/snackbar)
        # You could add a visual indicator here if desired

    def full_reset(self) -> None:
        """Hard reset: reload model if needed + clear chat."""
        if not self._engine:
            self.status_text = "Engine not ready"
            return

        # Stop any generation
        self._engine.stop()
    
        # Clear chat
        self._messages = []
        self.ids.chat_box.clear_widgets()
        self._bot_stream_label = None
    
        # Validate model is still loaded
        if self._engine.check_model_files(DEFAULT_MODEL_NAME):
            try:
                self._engine.load(DEFAULT_MODEL_NAME)
                self.status_text = "Model reloaded. Ready for new chat."
            except Exception as e:
                self.status_text = f"Reset error: {e}"
        else:
            self.status_text = "Model not available. Please download first."

    def stop_generation(self) -> None:
        if self._engine:
            self._engine.stop()
        self.status_text = "Stopping…"

    def send_message(self) -> None:
        if not self._engine:
            self.status_text = "Engine not ready"
            return

        if not self._engine.decoder_session:
            if self._engine.check_model_files(DEFAULT_MODEL_NAME) and not self.is_busy:
                self.status_text = "Loading model…"
                self._load_model_async(DEFAULT_MODEL_NAME)
            else:
                self.status_text = "Model not ready. Download it first."
            return

        if self.is_busy:
            self.status_text = "Busy. Please wait for the current operation."
            return

        prompt = (self.ids.input_field.text or "").strip()
        if not prompt:
            return

        self.ids.input_field.text = ""

        # Add user bubble
        self._add_bubble(role="user", text=prompt)

        # UI pre-filter: refuse immediately for non-Linux questions (better UX and
        # avoids wasting tokens). Engine also enforces this as a backstop.
        if not OnnxChatEngine._looks_linux_related(prompt):
            self._add_bubble(role="assistant", text=NON_LINUX_REFUSAL)
            self.status_text = "Ready"
            return

        # Add streaming bot bubble
        bot_label = self._add_bubble(role="assistant", text="")
        self._bot_stream_label = bot_label

        # Update conversation state (keep it small for performance)
        self._messages.append({"role": "user", "content": prompt})

        # Snapshot recent history (excluding the current prompt) so the worker thread
        # sees a stable view even if the UI updates later.
        history_snapshot: List[Dict[str, str]] = list(self._messages[-6:-1])

        self.is_busy = True
        self.status_text = "Generating…"

        try:
            max_new_tokens = int(self.token_text)
        except ValueError:
            max_new_tokens = 128

        def _work() -> None:
            final_text_parts: List[str] = []
            try:
                # Option 2: keep the engine-level Linux system prompt injection,
                # and pass DB context as a *user* message to ground the answer.
                db_context = self._build_db_context(prompt, limit=5)
                if db_context:
                    user_content = (
                        f"Context (local knowledge base):\n{db_context}\n\n"
                        f"User question:\n{prompt}"
                    )
                else:
                    user_content = prompt

                messages_to_send: List[Dict[str, str]] = list(history_snapshot)
                messages_to_send.append({"role": "user", "content": user_content})

                for piece in self._engine.generate_stream(
                    messages_to_send,
                    max_new_tokens=max_new_tokens,
                    # Lower temperature reduces hallucinations for small models.
                    temperature=0.4,
                    top_p=0.85,
                ):
                    final_text_parts.append(piece)
                    Clock.schedule_once(lambda *_p, t=piece: self._append_bot_text(t))

                final_text = "".join(final_text_parts).strip()
                if final_text:
                    self._messages.append({"role": "assistant", "content": final_text})

                Clock.schedule_once(lambda *_: setattr(self, "status_text", "Ready"))
            except Exception as e:
                err = str(e)
                Clock.schedule_once(
                    lambda *_args, m=err: setattr(self, "status_text", f"Error: {m}")
                )
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "is_busy", False))

        threading.Thread(target=_work, daemon=True).start()

    # ----------------------------
    # UI helpers
    # ----------------------------

    def _add_bubble(self, role: str, text: str) -> MDLabel:
        """Add a chat bubble and return its internal MDLabel (for streaming updates)."""

        # Colors taken from app/ui/main.kv palette
        COLOR_BG = (0.992, 0.922, 0.620, 1)  # #FDEB9E
        COLOR_SURFACE = (0.478, 0.886, 0.812, 1)  # #7AE2CF
        COLOR_PRIMARY = (0.027, 0.478, 0.490, 1)  # #077A7D
        COLOR_TEXT = (0.024, 0.125, 0.169, 1)  # #06202B

        is_user = role == "user"

        anchor = AnchorLayout(
            anchor_x="right" if is_user else "left",
            size_hint_y=None,
            height=dp(10),  # will be updated after label texture is ready
        )

        bubble = MDCard(
            orientation="vertical",
            padding=(dp(12), dp(10), dp(12), dp(10)),
            radius=[12, 12, 12, 12],
            elevation=1,
            md_bg_color=COLOR_PRIMARY if is_user else COLOR_SURFACE,
            size_hint_x=0.88,
            size_hint_y=None,
        )

        label = MDLabel(
            text=text,
            theme_text_color="Custom",
            text_color=COLOR_BG if is_user else COLOR_TEXT,
            halign="left",
            valign="top",
            markup=False,
            size_hint_y=None,
        )

        def _sync_label_size(*_):
            # Keep text wrapped within the bubble.
            # (Avoid calling texture_update() inside a texture_size callback.)
            label.text_size = (bubble.width - dp(24), None)
            label.height = label.texture_size[1]
            bubble.height = label.height + dp(20)
            anchor.height = bubble.height

        bubble.bind(width=_sync_label_size)
        label.bind(texture_size=_sync_label_size)
        _sync_label_size()

        bubble.add_widget(label)
        anchor.add_widget(bubble)
        self.ids.chat_box.add_widget(anchor)

        Clock.schedule_once(lambda *_: self._scroll_to_bottom())
        return label

    def _append_bot_text(self, piece: str) -> None:
        if not self._bot_stream_label:
            return
        self._bot_stream_label.text = (self._bot_stream_label.text or "") + piece

    def _scroll_to_bottom(self) -> None:
        try:
            self.ids.chat_scroll.scroll_y = 0
        except Exception:
            pass
