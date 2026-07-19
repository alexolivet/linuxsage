# Linux Knowledge Base App

A lightweight Linux terminal assistant app built with KivyMD and ONNX Runtime for offline Linux command assistance.

## Description

This app provides a Linux helpdesk/trainer that answers command-line questions offline using a specialized language model. It features a tabbed interface with Linux command reference, news feed, chat assistant, and command lookup—all working without internet after the initial model download.

## Interesting Techniques

- **Conditional Import Handling**: The app adapts its import paths based on whether it's run as a module or standalone script, ensuring compatibility across different execution contexts (direct Python execution vs. Android packaging). This avoids `ModuleNotFoundError` when the `app` package isn't importable in certain build environments.

- **Kivy Resource Bundling**: Uses Kivy's resource system (`resource_add_path`, `resource_find`) to bundle assets like images and fonts, making them accessible via relative paths in both development and Android builds without hardcoded absolute paths.

- **KV Language UI Separation**: Defines the entire user interface in `.kv` files, cleanly separating presentation logic from application code. This follows MVVM-like patterns where UI designers and developers can work independently.

- **ONNX Runtime Inference**: Runs a quantized language model entirely on-device using ONNX Runtime for privacy and offline functionality, avoiding API dependencies and latency.

- **Keyword-Based Topic Gating**: Before processing user questions, the app checks for Linux-related keywords to prevent off-topic responses from the small model, conserving computational resources on mobile devices.

## Technologies and Libraries

- [Kivy](https://kivy.org/#home) - Open-source Python framework for multitouch applications
- [KivyMD](https://kivymd.readthedocs.io/en/latest/) - Material Design components for Kivy
- [ONNX Runtime](https://onnxruntime.ai/docs/) - Cross-platform inference accelerator for machine learning models
- [HuggingFace tokenizers](https://huggingface.co/docs/tokenizers/python/latest/) - Fast tokenizer implementation
- [requests](https://requests.readthedocs.io/en/latest/) - Simple HTTP library for downloading model assets
- [PyYAML](https://pyyaml.org/) - Used by Buildozer for configuration (seen in `buildozer.spec`)
- [Android Spinner](https://developer.android.com/guide/topics/ui/controls/spinner) - Used in settings for dropdown menus (KivyMD's `MDDropDownItem` wraps this)
- Fonts:
  * [Arcade.ttf](assets/fonts/Arcade.ttf) - Retro-style font for headers
  * [PlusJakartaSans-Medium.ttf](assets/fonts/PlusJakartaSans-Medium.ttf) - Primary app font (Medium weight)

## Project Structure
linuxsage/
├── app/                 # Main application package
│   ├── __init__.py
│   ├── main.py          # App entry point and MDApp subclass
│   ├── screens/         # Screen definitions (Splash, Tabs, Settings)
│   ├── services/        # Backend services (model, database, paths)
│   │   ├── __init__.py
│   │   ├── db_initializer.py
│   │   ├── db_service.py
│   │   ├── onllm_engine.py  # Offline language model engine
│   │   └── paths.py
│   ├── ui/              # KV language files
│   │   └── main.kv      # Main UI layout (screens, theme, widgets)
│   └── widgets/         # Custom Kivy widgets
│       ├── __init__.py
│       ├── lottie_or_image.py
│       ├── matrix_flicker.py
│       └── menu_entry_label.py
├── assets/              # Bundled resources
│   ├── fonts/
│   │   ├── Arcade.ttf
│   │   └── PlusJakartaSans-Medium.ttf
│   └── images/
│       ├── Linux_mascot_tux.png
│       └── logo.png
├── buildozer.spec       # Buildozer configuration for Android/iOS
├── main.py              # Bootstrap script (adds repo to sys.path)
├── p4a-recipes/         # Custom Python-for-Android recipes
├── README.md            # This file
├── sitecustomize.py     # Python path configuration
└── .python-version      # Pyenv version file