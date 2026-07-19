# Linux Sage — App Structure

This document breaks down every screen / page in the app and explains what each one is meant for.

The app is built with Kivy + KivyMD. Navigation is handled by a `ScreenManager` (`AppRoot`). On launch the user sees a **Splash** screen, then a **Main Menu** with 4 large buttons, each opening one of the functional tabs. Every tab also has a **“Back to Menu”** button at the top.

---

## 1. Splash Screen (`SplashScreen`)
**File:** `app/screens/splash.py`
**KV:** `<SplashScreen>` in `app/ui/main.kv`

**Purpose**
- First screen shown when the app starts.
- Displays the app logo and a letter-by-letter typing animation of the title (“linux sage”) with a blinking cursor.
- Shows a sub-header (“Your command-line sidekick”) that fades in after typing finishes.
- Contains the **“OPEN APP”** button which switches to the main menu (`app.root.current = "main"`).

**Meant for**
- Branding / first impression.
- A lightweight loading / entry point before the user reaches the navigation menu.

---

## 2. Main Menu (`MainRoot`)
**File:** `app/main.py` (class `MainRoot`)
**KV:** `<MainRoot>` in `app/ui/main.kv`

**Purpose**
- The home navigation page shown after the splash screen.
- Shows the app header (“The Linux Sage” + logo + restart icon).
- Displays a **2x2 grid of 4 large buttons** that fill the page:
  - **Home** → `home_tab`
  - **Topics** → `topics_tab`
  - **Favorites** → `favorites_tab`
  - **Search** → `search_tab`
- Shows the legal disclaimer at the bottom.

**Meant for**
- Letting the user pick any section immediately (simplified UI).
- Replacing the old bottom-tab navigation with a full-page menu.

---

## 3. Home Tab (`HomeTabScreen`)
**File:** `app/screens/home_tab.py`
**KV:** `<HomeTabScreen>` in `app/ui/main.kv`

**Purpose**
- An auto-advancing pitch / slideshow (“pocket oracle” deck).
- Cycles through 10 slides (cover, problem, solution, features, market, demo, business model, GTM, team, ask).
- Each slide’s HTML content is converted to Kivy markup and shown in a card.
- Auto-play advances every 5 seconds.
- **Settings Gear:** In the top-right toolbar, a gear icon opens a settings menu/dialog.
- The settings menu allows users to:
  - **Refresh Database:** Restores or reinitializes the bundled command database.
  - **Reset Model:** Redownloads/resets the offline model files used for the chat assistant.

**Meant for**
- Explaining the app’s value proposition / onboarding.
- A “landing page” style intro inside the app.
- Central quick-access for maintenance actions (Reset Database/Model).

---

## 4. Topics Tab (`TopicsTabScreen`)
**File:** `app/screens/topics_tab.py`
**KV:** `<TopicsTabScreen>` in `app/ui/main.kv`

**Purpose**
- A simple RSS reader for “Linux Today” (`https://www.linuxtoday.com/feed/`).
- Fetches and parses the RSS feed asynchronously (via `UrlRequest`).
- Shows **one article at a time** with title, date, author, categories, summary, and body.
- Controls: open article in external browser, skip to next article, refresh.
- Only loads English-language feeds.

**Meant for**
- Surfacing fresh Linux news / articles.
- A lightweight “read later” style viewer (no full list UI).

---

## 5. Favorites Tab (`FavoritesTabScreen`) — Offline Chat
**File:** `app/screens/favorites_tab.py`
**KV:** `<FavoritesTabScreen>` in `app/ui/main.kv`
**Engine:** `app/services/onllm_engine.py`

**Purpose**
- Offline AI chat assistant specialized for Linux help.
- Uses an on-device ONNX model (`smollm2-135m`) via OnLLM-style inference.
- On first run the user downloads the model; then chat works fully offline.
- System prompt enforces Linux-only answers; the app also injects relevant rows from the local command database as context (RAG).
- Controls: model/token selection, download, new chat (clear), stop generation, send.

**Meant for**
- Asking Linux command/questions and getting offline, DB-grounded replies.
- The “helpdesk” specialist screen.

---

## 6. Search Tab (`SearchTabScreen`)
**File:** `app/screens/search_tab.py`
**KV:** `<SearchTabScreen>` in `app/ui/main.kv`
**Services:** `app/services/db_service.py`, `app/services/db_initializer.py`

**Purpose**
- Local SQLite search over the bundled Linux command knowledge base (`knowledge_base_01.db`).
- On open it initializes / health-checks the DB in a background thread.
- Live search (debounced) by command, description, or category.
- Results shown as a list; tapping a result opens a details dialog (category, description, examples).

**Meant for**
- Fast lookup of specific Linux commands from the curated database.
- The primary “reference” / search tool of the app.

---

## 7. Shared App Root (`AppRoot`)
**File:** `app/main.py` (class `AppRoot`)
**KV:** `<AppRoot>` in `app/ui/main.kv`

**Purpose**
- The `ScreenManager` that holds all screens:
  - `splash`
  - `main` (menu)
  - `home_tab`, `topics_tab`, `favorites_tab`, `search_tab`
- Provides `app.root.current = "<name>"` navigation used by all buttons.

**Meant for**
- Central navigation/routing between splash, menu, and tabs.

---

## 8. Settings Tab (`SettingsScreen`)
**File:** `app/screens/settings.py`
**KV:** `<SettingsScreen>` in `app/ui/main.kv`

**Purpose**
- Allows users to configure app settings.
- Includes options for theme selection, notification preferences, and language settings.
- Provides a way to clear the chat history and manage downloaded models.
- **New Feature:** Added a dark mode toggle for better user experience in low-light conditions.

**Meant for**
- Customizing the app experience to user preferences.
- Managing app resources and settings.
- Enhancing user comfort with dark mode option.

---

## 9. About Tab (`AboutScreen`)
**File:** `app/screens/about.py`
**KV:** `<AboutScreen>` in `app/ui/main.kv`

**Purpose**
- Provides information about the app, including version, developer details, and contact information.
- Displays the app logo and a brief description of its purpose.
- Includes links to the app's website, support page, and privacy policy.

**Meant for**
- Informing users about the app's background and purpose.
- Offering support and contact options for users.
- Directing users to relevant external resources.

---

## Summary Table

| Screen | File | Goal |
|--------|------|------|
| Splash | `screens/splash.py` | Branding + entry |
| Main Menu | `main.py` (`MainRoot`) | 4-button navigation |
| Home | `screens/home_tab.py` | Pitch slides |
| Topics | `screens/topics_tab.py` | Linux Today RSS |
| Favorites | `screens/favorites_tab.py` | Offline Linux chat |
| Search | `screens/search_tab.py` | Local command DB search |
| AppRoot | `main.py` | Screen routing |
| Settings | `screens/settings.py` | App configuration |
| About | `screens/about.py` | App information |

---

## Notes
- All tabs contain a **“Back to Menu”** button returning to `MainRoot`.
- The offline model and the SQLite command DB are the two data sources that make the app useful without a server.
- UI colors follow the custom palette defined at the top of `app/ui/main.kv`.
- The app now includes a dark mode option for better user experience in low-light conditions.
- Added an About section to provide users with information about the app and its purpose.