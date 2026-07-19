from __future__ import annotations

import sys
from pathlib import Path

# Allow running this file directly (`python app/main.py`) by ensuring the
# repository root is on sys.path so `import app...` works.
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


from kivy.lang import Builder
from kivy.logger import Logger
from kivy.resources import resource_add_path, resource_find
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager


class AppRoot(MDScreenManager):
    """Screen manager for splash -> main app."""


class MainRoot(MDScreen):
    """Root screen holding the bottom navigation."""


class LinuxKnowledgeBaseApp(MDApp):
    title = "Linux Knowledge Base"

    def build(self):
        # Ensure our project paths are on Kivy's resource search path.
        # This makes it safe to reference bundled images on Android.
        repo_root = Path(__file__).resolve().parents[1]
        resource_add_path(str(repo_root))
        resource_add_path(str(repo_root / "assets"))
        resource_add_path(str(Path(__file__).resolve().parent))

        # App theme (KivyMD base theme).
        # Main UI colors are defined explicitly in KV (app/ui/main.kv) using the
        # custom palette:
        #   #FDEB9E / #7AE2CF / #077A7D / #06202B
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.primary_hue = "700"

        # Set the app font to Plus Jakarta Sans
        self.theme_cls.font_name = "PlusJakartaSans-Medium.ttf"

        # Logo image (bundled)
        #
        # You said you placed an image in: assets/images/
        # We'll use that for both the splash screen and the main screen.
        self.logo_path = (
            resource_find("assets/images/Linux_mascot_tux.png")
            or resource_find("assets/images/logo.png")
            or resource_find("assets/logo.png")
            or ""
        )

        # Splash logo (shown above the OPEN APP button)
        self.splash_logo_path = self.logo_path

        if not self.logo_path:
            Logger.warning(
                "LinuxKB: Logo image not found. Add it as assets/images/Linux_mascot_tux.png"
            )


        # Register custom widget classes before loading KV.
        # These imports also make sure Kivy's Factory knows about the classes.
        #
        # NOTE:
        # We only want the "fallback" imports (from `screens...`) when the *app
        # package itself* is not importable (some Android/buildozer layouts).
        #
        # Do NOT swallow other ModuleNotFoundError cases (e.g. missing numpy),
        # otherwise real errors get masked and we crash later.
        try:
            import app  # noqa: F401
            app_pkg_available = True
        except ModuleNotFoundError:
            app_pkg_available = False

        if app_pkg_available:
            from app.screens.splash import SplashScreen  # noqa: F401
            from app.screens.tab1 import Tab1Screen  # noqa: F401
            from app.screens.tab2 import Tab2Screen  # noqa: F401
            from app.screens.tab3 import Tab3Screen  # noqa: F401
            from app.screens.tab4_search import Tab4SearchScreen  # noqa: F401
            from app.screens.settings import SettingsScreen  # noqa: F401
        else:
            from screens.splash import SplashScreen  # type: ignore # noqa: F401
            from screens.tab1 import Tab1Screen  # type: ignore # noqa: F401
            from screens.tab2 import Tab2Screen  # type: ignore # noqa: F401
            from screens.tab3 import Tab3Screen  # type: ignore # noqa: F401
            from screens.tab4_search import Tab4SearchScreen  # type: ignore # noqa: F401
            from screens.settings import SettingsScreen  # type: ignore # noqa: F401

        kv_path = Path(__file__).resolve().parent / "ui" / "main.kv"
        Builder.load_file(str(kv_path))
        return AppRoot()

    def open_main(self) -> None:
        """Called by the splash screen button."""
        if self.root is None:
            return
        self.root.current = "main"

    def go_to_splash(self) -> None:
        """Return to the splash screen ("reset" / start over)."""
        if self.root is None:
            return
        self.root.current = "splash"


if __name__ == "__main__":
    LinuxKnowledgeBaseApp().run()

