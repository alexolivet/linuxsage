from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

class HomeTabScreen(Screen):
    def __init__(self, **kwargs):
        super(HomeTabScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')

        # Add existing slideshow content here

        reset_db_button = Button(text='Reset Database', size_hint=(1, 0.1))
        reset_db_button.bind(on_press=self.reset_database)
        layout.add_widget(reset_db_button)

        reset_model_button = Button(text='Reset Model', size_hint=(1, 0.1))
        reset_model_button.bind(on_press=self.reset_model)
        layout.add_widget(reset_model_button)

        self.add_widget(layout)

    def reset_database(self, instance):
        # Function to reset the database
        from app.services.db_initializer import initialize_db
        initialize_db()
        print("Database reset successfully")

    def reset_model(self, instance):
        # Function to reset the model
        from app.services.onllm_engine import download_model
        download_model()
        print("Model reset successfully")