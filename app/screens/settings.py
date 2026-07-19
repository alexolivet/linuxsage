from kivy.properties import ListProperty, StringProperty
from kivymd.uix.screen import MDScreen
from kivymd.uix.menu import MDDropdownMenu
from kivy.metrics import dp
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.label import MDLabel

class SettingsScreen(MDScreen):
    """Settings screen with full-page UI and feed dropdown selector."""

    # Feeds for news tab selection
    feeds = ListProperty([
        {"name": "Linux Today", "url": "https://www.linuxtoday.com/feed/"},
        {"name": "LWN", "url": "https://lwn.net/headlines/rss"},
    ])
    selected_feed_name = StringProperty("Linux Today")
    menu = None  # Keep reference to menu

    _snackbar = None

    def show_notification(self, message: str) -> None:
        # Dismiss any previous snackbar
        try:
            if self._snackbar is not None:
                self._snackbar.dismiss()
        except Exception:
            pass

        self._snackbar = MDSnackbar(
            MDLabel(
                text=str(message),
                theme_text_color="Custom",
                text_color="white",
            ),
            y=dp(24),
            pos_hint={"center_x": 0.5},
            size_hint_x=0.92,
        )
        self._snackbar.open()

    def open_feed_menu(self):
        # Close any old
        if self.menu:
            self.menu.dismiss()
        # Build items
        menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": f["name"],
                "height": dp(56),
                "on_release": lambda x=f["name"]: self.select_feed(x)
            }
            for f in self.feeds
        ]
        self.menu = MDDropdownMenu(
            caller=self.ids.feed_dropdown,
            items=menu_items,
            width_mult=4,
        )
        self.menu.open()

    def select_feed(self, feed_name):
        self.ids.feed_dropdown.text = feed_name
        self.on_feed_select(feed_name)
        if self.menu:
            self.menu.dismiss()

    def on_feed_select(self, feed_name):
        self.selected_feed_name = feed_name
        self.set_tab2_feed(feed_name)

    def set_tab2_feed(self, feed_name):
        # Find Tab2Screen and set its feed_url property
        try:
            from kivy.app import App
            app = App.get_running_app()
            if not app.root:
                return
            tab2 = app.root.get_screen("tab2")
            # Get feed URL
            url = "https://www.linuxtoday.com/feed/"
            for f in self.feeds:
                if f["name"] == feed_name:
                    url = f["url"]
                    break
            tab2.feed_name = feed_name
            tab2.feed_url = url
            tab2.status_text = f"{feed_name}: not loaded"
            tab2._loaded_once = False  # Force reload on next enter
        except Exception as e:
            print(f"Set feed exception: {e}")

    def clear_chat(self):
        """Clear the offline chat conversation (Tab3)."""
        try:
            from kivy.app import App

            app = App.get_running_app()
            if not app.root:
                return

            tab3 = app.root.get_screen("tab3")
            # Tab3Screen already implements new_chat()
            if hasattr(tab3, "new_chat"):
                tab3.new_chat()
            print("Chat cleared.")
            self.show_notification("Chat cleared successfully")
        except Exception as e:
            print(f"Clear chat failed: {e}")

    def reset_database(self):
        try:
            from app.services.db_initializer import DatabaseInitializer
            from app.services.paths import get_writable_db_path

            writable = get_writable_db_path()
            if writable.exists():
                writable.unlink()

            DatabaseInitializer().initialize()
            print("Database refreshed.")
            self.show_notification("Database refreshed successfully")
        except Exception as e:
            print(f"Database refresh failed: {e}")

    def reset_model(self):
        try:
            import os
            import shutil
            from kivy.app import App

            app = App.get_running_app()
            model_dir = os.path.join(app.user_data_dir, "onllm_models")

            shutil.rmtree(model_dir, ignore_errors=True)
            os.makedirs(model_dir, exist_ok=True)

            print("Model files cleared. Re-download from the Chat tab.")
            self.show_notification("Model reset successfully")
        except Exception as e:
            print(f"Model reset failed: {e}")

    def go_back(self):
        """Return to the About tab (Tab1) where Settings was opened from."""
        from kivy.app import App

        app = App.get_running_app()
        if app.root:
            app.root.current = "tab1"

