from __future__ import annotations

from kivy.logger import Logger
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.resources import resource_find
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image


class LottieOrImage(FloatLayout):
    """Render a Lottie JSON animation if available, otherwise fall back to an Image.

    This is intentionally defensive:
    - The optional dependency `kivy_garden.lottie` might not be installed yet.
    - Some platforms may be missing native libs needed by the Lottie renderer.

    KV can safely use this widget without crashing; if Lottie fails to load,
    the fallback image is shown.
    """

    lottie_file = StringProperty("")
    fallback_image = StringProperty("")

    loop = BooleanProperty(True)
    autoplay = BooleanProperty(True)
    speed = NumericProperty(1.0)

    _did_build = BooleanProperty(False)

    def on_kv_post(self, base_widget):  # noqa: ANN001
        # Build after KV rules and size/pos are applied.
        self._build()

    def on_lottie_file(self, *_):
        if self._did_build:
            self._build()

    def on_fallback_image(self, *_):
        if self._did_build:
            self._build()

    def _build(self) -> None:
        self._did_build = True
        self.clear_widgets()

        # Prefer Lottie if configured.
        if self.lottie_file:
            lottie_path = resource_find(self.lottie_file) or self.lottie_file
            try:
                # Garden package is optional.
                # Depending on how it was installed (pip vs legacy `garden install`),
                # the import path can vary.
                import_err = None
                try:
                    from kivy_garden.lottie import Lottie  # type: ignore
                except Exception as e1:  # pragma: no cover
                    import_err = e1
                    try:
                        from kivy.garden.lottie import Lottie  # type: ignore
                    except Exception as e2:  # pragma: no cover
                        raise ModuleNotFoundError(
                            "Could not import Lottie widget from 'kivy_garden.lottie' or 'kivy.garden.lottie'"
                        ) from (import_err or e2)

                lottie = Lottie()

                # Different versions use different property names.
                if hasattr(lottie, "file"):
                    lottie.file = lottie_path  # type: ignore[attr-defined]
                elif hasattr(lottie, "source"):
                    lottie.source = lottie_path  # type: ignore[attr-defined]
                elif hasattr(lottie, "filename"):
                    lottie.filename = lottie_path  # type: ignore[attr-defined]
                else:
                    # If we can't figure out how to set the file, force fallback.
                    raise AttributeError(
                        "Unsupported kivy_garden.lottie API: can't set animation file"
                    )

                # Common playback/config properties.
                if hasattr(lottie, "loop"):
                    lottie.loop = self.loop  # type: ignore[attr-defined]
                if hasattr(lottie, "autoplay"):
                    lottie.autoplay = self.autoplay  # type: ignore[attr-defined]
                if hasattr(lottie, "speed"):
                    lottie.speed = self.speed  # type: ignore[attr-defined]

                # Ensure it fills this widget.
                lottie.size_hint = (1, 1)
                lottie.pos_hint = {"x": 0, "y": 0}

                self.add_widget(lottie)

                # Some implementations require calling play().
                if self.autoplay and hasattr(lottie, "play"):
                    try:
                        lottie.play()  # type: ignore[misc]
                    except Exception:
                        # Not fatal; some versions auto-play.
                        pass

                return

            except Exception as exc:
                Logger.warning(
                    f"LinuxKB: Lottie failed to load '{lottie_path}', falling back to image. ({exc})"
                )

        # Fallback: show the existing splash image (or nothing).
        if self.fallback_image:
            image_path = resource_find(self.fallback_image) or self.fallback_image
            img = Image(
                source=image_path,
                allow_stretch=True,
                keep_ratio=True,
            )
            img.size_hint = (1, 1)
            img.pos_hint = {"x": 0, "y": 0}
            self.add_widget(img)
