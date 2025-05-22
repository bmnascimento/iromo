# Iromo - Project Brief

## 1. Overview

**Project Name:** Iromo (Incremental Reading Of My Own)
**Core Technology:** Python & Qt6
**Goal:** To create an open-source, cross-platform incremental reading and spaced repetition tool, inspired by SuperMemo. The initial focus is on a desktop application with core incremental reading features.

## 2. MVP (Minimum Viable Product) Scope

The MVP aims to implement a system with a hierarchical Knowledge Tree (KT) where users can:
*   Add topics.
*   Paste text into topics.
*   Extract portions of text from a topic into new child topics.
*   Visually see extracted text highlighted (light blue background) in the parent topic.
*   Edit topic titles (initially auto-generated from the first X characters of content).

## 3. Data Storage and Structure

A hybrid approach is used:

*   **Topic Content Files:**
    *   Each topic's primary text content is stored in a separate plain text file (e.g., `.txt`).
    *   All text files reside within a `text_files/` subdirectory inside each collection folder (e.g., `MyCollection/text_files/`).
    *   Files are named using UUIDs (e.g., `abcdef12-3456-7890-abcd-ef1234567890.txt`) to prevent naming conflicts and simplify linking.
*   **SQLite Database (`iromo.sqlite`):**
    *   Each collection has its own `iromo.sqlite` database file located at the root of the collection folder (e.g., `MyCollection/iromo.sqlite`).
    *   This database serves as the central hub for metadata, KT structure, extraction information, and future features for that specific collection.
    *   **Key Tables (within each collection's database):**
        *   `schema_migrations`: Tracks applied database schema migrations for this collection's database.
            *   `version` (TEXT, PRIMARY KEY): Filename of the migration script.
            *   `applied_at` (TIMESTAMP): When the migration was applied.
        *   `topics`: Stores information about each piece of knowledge.
            *   `id` (TEXT, PRIMARY KEY, UUID): Unique identifier for the topic.
            *   `parent_id` (TEXT, FOREIGN KEY referencing `topics.id`, NULLable): Defines the hierarchy.
            *   `title` (TEXT, NOT NULL): User-defined or auto-generated title.
            *   `text_file_uuid` (TEXT, NOT NULL, UNIQUE): UUID linking to the topic's content file.
            *   `created_at` (TIMESTAMP, NOT NULL): Topic creation timestamp.
            *   `updated_at` (TIMESTAMP, NOT NULL): Topic last update timestamp.
            *   `display_order` (INTEGER, optional): For manual ordering of sibling topics.
        *   `extractions`: Links extracted text segments (child topics) to their source (parent topics).
            *   `id` (TEXT, PRIMARY KEY, UUID): Unique identifier for the extraction record.
            *   `parent_topic_id` (TEXT, NOT NULL, FOREIGN KEY referencing `topics.id`): ID of the source topic.
            *   `child_topic_id` (TEXT, NOT NULL, UNIQUE, FOREIGN KEY referencing `topics.id`): ID of the new topic created with extracted text.
            *   `parent_text_start_char` (INTEGER, NOT NULL): Start character offset of the extraction in the parent's text.
            *   `parent_text_end_char` (INTEGER, NOT NULL): End character offset (inclusive) of the extraction in the parent's text.
*   **Database Migrations:**
    *   Schema changes are managed via SQL scripts stored in the application's `migrations/` directory (e.g., `001_initial_schema.sql`).
    *   An instance of the `DataManager` class, specific to each collection, handles database initialization (including applying migrations) via its `initialize_collection_storage()` method.
*   **Highlighting Mechanism:**
    *   Extracted text in a parent topic is highlighted with a light blue background within the context of its collection.
    *   This is managed dynamically by the `TopicEditorWidget` by querying the `extractions` table and applying formatting based on character offsets.

## 4. Application Architecture

The application follows a model-view-controller like pattern. With the introduction of collections, data management is now handled by a `DataManager` class, instantiated per active collection.

```mermaid
graph TD
    User -->|Interacts with| MainWindowUI["MainWindow (UI Orchestrator, Manages Active Collection)"]
    
    MainWindowUI -->|Displays & Delegates to| KnowledgeTreeWidgetUI["KnowledgeTreeWidget (QTreeView)"]
    MainWindowUI -->|Displays & Delegates to| TopicEditorWidgetUI["TopicEditorWidget (QTextEdit)"]
    
    KnowledgeTreeWidgetUI -->|Emits Signals (Selection, Title Change)| MainWindowUI
    TopicEditorWidgetUI -->|Provides Data (Selected Text, Content)| MainWindowUI
    
    MainWindowUI -->|Handles User Actions & Events| AppLogic["Application Logic (in MainWindow methods)"]
    
    AppLogic -->|Uses| ActiveDM["Active DataManager Instance (per Collection)"]
    
    ActiveDM -->|Reads/Writes| CollectionSQLite["Collection's SQLite DB (e.g., MyCollection/iromo.sqlite)"]
    ActiveDM -->|Reads/Writes| CollectionTextFiles["Collection's Text Files (e.g., MyCollection/text_files/)"]

    subgraph UI_Layer [UI (PyQt6 - src/main_window.py, src/knowledge_tree_widget.py, src/topic_editor_widget.py)]
        MainWindowUI
        KnowledgeTreeWidgetUI
        TopicEditorWidgetUI
    end

    subgraph Core_Logic_Layer [Core Logic & Data (Python - src/data_manager.py)]
        AppLogic
        ActiveDM
    end

    subgraph Data_Storage_Layer [Data Store (Per Collection; App-level: migrations/)]
        CollectionSQLite
        CollectionTextFiles
    end
```

**Key Modules & Classes:**

*   **[`src/main.py`](src/main.py)**:
    *   `run_app()`: Entry point of the application. Initializes logging, `QApplication`, `MainWindow`, and starts the event loop.
*   **[`src/main_window.py`](src/main_window.py) (`MainWindow` class):**
    *   Main application window, inherits `QMainWindow`.
    *   Orchestrates UI components (`KnowledgeTreeWidget`, `TopicEditorWidget`) using a `QSplitter`.
    *   Sets up menus, toolbars, and connects signals from widgets to handler methods.
    *   Handles core application logic like text extraction (`extract_text()`), saving content (`save_current_topic_content()`), and responding to topic selection/title changes.
    *   Calls `data_manager.initialize_database()` on startup.
    *   Includes `_create_test_data_if_needed()` for consistent debugging of highlighting.
*   **[`src/data_manager.py`](src/data_manager.py)**:
    *   Handles all interactions with the SQLite database and topic text files.
    *   `initialize_database()`: Creates directories and applies database migrations.
    *   `_apply_migrations()`: Applies SQL scripts from the `migrations/` directory.
    *   `create_topic()`: Creates a new topic (DB record + text file), auto-generates initial title.
    *   `get_topic_content()`: Retrieves text content for a topic.
    *   `save_topic_content()`: Saves text content for a topic, updates `updated_at`.
    *   `update_topic_title()`: Updates a topic's title.
    *   `get_topic_hierarchy()`: Fetches data to build the Knowledge Tree.
    *   `create_extraction()`: Records an extraction event (links parent to new child topic, stores character offsets).
    *   `get_extractions_for_parent()`: Retrieves extraction records for highlighting.
    *   `_generate_initial_title()`: Helper to create default topic titles.
*   **[`src/knowledge_tree_widget.py`](src/knowledge_tree_widget.py) (`KnowledgeTreeWidget` class):**
    *   Custom widget inheriting `QTreeView`.
    *   Displays the topic hierarchy using `QStandardItemModel`.
    *   Loads data via `data_manager.get_topic_hierarchy()`.
    *   Allows inline editing of topic titles.
    *   Emits signals:
        *   `topic_selected(topic_id: str)`
        *   `topic_title_changed(topic_id: str, new_title: str)`
    *   Provides methods `add_topic_item()` and `update_topic_item_title()` for programmatic tree updates.
*   **[`src/topic_editor_widget.py`](src/topic_editor_widget.py) (`TopicEditorWidget` class):**
    *   Custom widget inheriting `QTextEdit`.
    *   Displays and allows editing of the selected topic's content.
    *   `load_topic_content()`: Fetches and displays topic text, then applies existing highlights.
    *   `_apply_existing_highlights()`: Highlights all previously extracted segments.
    *   `apply_extraction_highlight()`: Applies background color to a specified text range.
    *   `get_current_content()`: Returns current text.
    *   `get_selected_text_and_offsets()`: Returns selected text and its start/end character positions.
*   **[`src/logger_config.py`](src/logger_config.py)**:
    *   `setup_logging()`: Configures application-wide logging (file and console).
    *   `APP_NAME`: Constant for the logger name.

## 5. Core Functionality Flow (Extraction Example)

1.  User selects text in the `TopicEditorWidget`.
2.  User triggers "Extract" action (Alt+X or toolbar button).
3.  `MainWindow.extract_text()` is called:
    a.  Gets current parent topic ID and selected text/offsets from `TopicEditorWidget`.
    b.  Calls `MainWindow.save_current_topic_content()` to ensure parent content is up-to-date.
    c.  Calls `data_manager.create_topic()` to create a new child topic with the extracted text.
    d.  Calls `data_manager.create_extraction()` to link parent and child, storing offsets.
    e.  Calls `KnowledgeTreeWidget.add_topic_item()` to display the new child topic in the tree.
    f.  Calls `TopicEditorWidget._apply_existing_highlights()` to refresh highlights in the parent topic's view, now including the new extraction.

## 6. Future Considerations (Beyond MVP)

*   Cloud synchronization.
*   More advanced UI features (PDF rendering/extraction, WYSIWYG editor).
*   Full-text search.
*   Spaced repetition scheduling and review interface.
*   Robust "New Topic" functionality, topic deletion.
*   Refined ribbon UI.
*   Comprehensive unit and integration testing.
*   Packaging for Windows, Linux, macOS.

## 7. Architectural Design: Collections Feature

This document outlines the architectural changes required to implement the "Collections" feature in the Iromo application.

**Note: The "Collections" feature, as described below, has been implemented in the current version of the codebase. The `DataManager` is now a class, and data paths are relative to the active collection.**

### 1. File System Structure for Collections

**1.1. Collection Location:**
*   Users will be able to **save and open Iromo collection folders from any location** on their file system. This provides maximum flexibility, similar to how standard document-based applications (e.g., word processors, IDEs) handle project or document files.
*   The application may offer a default suggested location (e.g., in the user's "Documents" folder under an "Iromo Collections" subdirectory) when creating a new collection, but the user will have the final say.

**1.2. Internal Structure of a Collection Folder:**
Each Iromo collection will be a self-contained folder. The internal structure of a collection folder (e.g., `MyVacationNotes/`) will be:

```
MyVacationNotes/
├── iromo.sqlite              # The SQLite database for this specific collection
├── text_files/               # Directory containing all topic text files for this collection
│   ├── uuid1.txt
│   ├── uuid2.txt
│   └── ...
└── iromo_collection.json     # (Recommended) A manifest file (see section 5)
```

This structure mirrors the current `iromo_data/` layout but encapsulates it within each user-defined collection folder.

### 2. Module Impact Analysis

The introduction of collections will primarily impact modules responsible for data management and UI orchestration.

**2.1. [`src/data_manager.py`](src/data_manager.py)**

*   **Nature of Change:** This module will be refactored from a collection of functions operating on global, hardcoded paths to a **`DataManager` class**.
*   **Instantiation:** An instance of `DataManager` will be created for each active collection. The constructor will accept the base path of the collection folder as an argument (e.g., `collection_base_path`).
    ```python
    # Example:
    # class DataManager:
    #     def __init__(self, collection_base_path):
    #         self.collection_base_path = collection_base_path
    #         self.db_path = os.path.join(collection_base_path, "iromo.sqlite")
    #         self.text_files_dir = os.path.join(collection_base_path, "text_files")
    #         self.migrations_dir = "migrations" # This can remain relative to app install or be configurable
    #         # ...
    ```
*   **Path Handling:** All internal functions that currently use global constants like `DB_NAME` and `TEXT_FILES_DIR` (e.g., `get_db_connection()`, `create_topic()`, `_get_topic_text_file_path()`) will be modified to derive paths from the instance's `self.db_path` and `self.text_files_dir`.
*   **`initialize_database()`:** This method (or an equivalent instance method) will operate on the specific collection's `db_path` and `text_files_dir`. It will be responsible for creating these if they don't exist (e.g., for a new collection) and applying migrations to the collection's database. The `MIGRATIONS_DIR` path itself would likely remain relative to the application's installation directory, as migration scripts are part of the application code, not individual collections.

**2.2. [`src/main_window.py`](src/main_window.py) (`MainWindow` class)**

*   **DataManager Instance:** `MainWindow` will hold an instance of the `DataManager` class for the currently active collection (e.g., `self.active_collection_dm = DataManager(path_to_collection)`). This will be `None` if no collection is open.
*   **Data Operations:** All direct calls to `dm.some_function()` will be changed to `self.active_collection_dm.some_function()`. Logic must be added to handle cases where `self.active_collection_dm` is `None`.
*   **Initialization:** The current call to `dm.initialize_database()` in `MainWindow.__init__` will be removed. Database/collection initialization will occur when a user creates a new collection or opens an existing one.
*   **UI for Collection Management:**
    *   The "File" menu (`_create_menu_bar()`) will be extended with new `QAction`s:
        *   "New Collection..." (prompts for folder name/location, then creates structure and initializes `DataManager`).
        *   "Open Collection..." (shows a directory dialog, validates selection, then initializes `DataManager`).
        *   "Close Collection" (clears current `DataManager`, resets UI).
        *   "Recent Collections" (submenu to quickly reopen collections).
    *   The main window title should be updated to reflect the name or path of the currently active collection (e.g., "Iromo - MyVacationNotes").
*   **Widget State Management:**
    *   When a collection is opened, `MainWindow` will load data into `KnowledgeTreeWidget` and potentially `TopicEditorWidget` using the `self.active_collection_dm`.
    *   When a collection is closed, or if no collection is open, `MainWindow` will instruct these widgets to clear their views and potentially disable certain functionalities.
*   **Test Data:** The `_create_test_data_if_needed()` method will need to be re-evaluated. Test data might be part of a sample collection, or this logic might be removed/changed for production.

**2.3. [`src/main.py`](src/main.py) (`run_app()` function)**

*   **Startup Behavior:** The application will start without an active collection by default, unless it can load the path of the last-used collection from a preference file (see Section 3).
*   `MainWindow` will be instantiated, but it will initially be in a "no collection open" state (see Section 4). It will not immediately try to load data as it does now.

**2.4. [`src/knowledge_tree_widget.py`](src/knowledge_tree_widget.py) (`KnowledgeTreeWidget` class)**

*   **Data Loading:** Will need a method like `load_from_datamanager(dm_instance)` or `set_datamanager(dm_instance)` to populate the tree. It will call `dm_instance.get_topic_hierarchy()`.
*   **Clearing View:** Will need a `clear_tree()` method to empty its contents when a collection is closed or on startup if no collection is loaded.
*   **State Management:** UI elements might be disabled if no collection is active.

**2.5. [`src/topic_editor_widget.py`](src/topic_editor_widget.py) (`TopicEditorWidget` class)**

*   **Data Loading:** `load_topic_content(topic_id)` will need access to the active `DataManager` instance (likely passed from `MainWindow` or the `DataManager` instance itself is passed).
*   **Clearing View:** Will need a `clear_content()` method to empty the editor and reset its state.
*   **State Management:** The editor should be disabled or show placeholder text if no topic (or no collection) is active.

### 3. Active Collection Management

**3.1. Tracking the Active Collection Path:**
*   **In Memory:** `MainWindow` will store the file system path to the root of the currently active collection (e.g., `self.active_collection_path`). This path will be used to instantiate the `DataManager` for that collection.
*   **Persistence (Last Opened Collection):** To improve user experience, the path of the last successfully opened collection will be stored in a simple application configuration file.
    *   **Location:** This file could reside in a standard user-specific application data directory (e.g., `~/.config/Iromo/settings.json` on Linux, or platform-appropriate locations using `QSettings` from Qt).
    *   **Content:** A simple JSON structure like: `{"last_opened_collection": "/path/to/user/collection_folder"}`.
    *   On startup, the application will attempt to read this path and reopen the collection. If it fails (e.g., folder moved/deleted), it will start in the "no collection open" state.

**3.2. Passing to Modules:**
*   When a collection is opened or created, `MainWindow` will instantiate `DataManager(active_collection_path)`.
*   This `DataManager` instance (`self.active_collection_dm`) will then be used by `MainWindow` for its own data operations.
*   When `KnowledgeTreeWidget` or `TopicEditorWidget` need to perform data operations (e.g., load hierarchy, load topic content), they will either:
    1.  Be explicitly passed the `self.active_collection_dm` instance by `MainWindow` when calling their methods.
    2.  Have a reference to the `self.active_collection_dm` set by `MainWindow` when the collection becomes active.

### 4. "No Collection Open" State

This state occurs on the first launch after the feature is implemented, if the user explicitly closes a collection, or if the last-opened collection cannot be found.

**4.1. Application Behavior:**
*   Most data-dependent functionalities will be disabled (e.g., extract text, save content, new topic within a collection).
*   The primary available actions will be to create a new collection or open an existing one.

**4.2. UI Presentation:**
*   **`MainWindow` Title:** Could display "Iromo - No Collection Open".
*   **`KnowledgeTreeWidget`:** Will be empty. A placeholder message like "No collection open. Use File > New Collection or File > Open Collection." could be displayed.
*   **`TopicEditorWidget`:** Will be empty and likely read-only or disabled. A similar placeholder message could be shown.
*   **Menu Bar:**
    *   "File" menu: "New Collection...", "Open Collection...", "Recent Collections" (if any), and "Exit" will be enabled. Other actions like "Save Content" will be disabled.
    *   Other menus (Edit, View, etc.) might have most of their items disabled.
*   **Toolbar:** Actions on the toolbar will be disabled.

### 5. Collection File Extension / Manifest (Recommended)

Using a manifest file within each collection folder is **recommended** for better identification and future-proofing.

**5.1. Proposal: Manifest File (`iromo_collection.json`)**

*   **File:** A JSON file named `iromo_collection.json` (or similar, e.g., `.iromo_manifest`) will reside in the root of each collection folder.
*   **Purpose:**
    *   Allows the application to reliably identify a folder as an Iromo collection during the "Open Collection..." process.
    *   Can store metadata about the collection.
*   **Content (MVP):** For the initial implementation, it can be very simple:
    ```json
    {
      "type": "iromo_collection",
      "version": "1.0", // Iromo version that created/understands this collection format
      "created_at": "YYYY-MM-DDTHH:MM:SSZ", // Optional: timestamp of creation
      "collection_name": "My User-Friendly Collection Name" // Optional: if different from folder name
    }
    ```
    Even an empty file or just `{"type": "iromo_collection"}` would suffice initially for identification.
*   **Benefits:**
    *   Makes the "Open Collection" dialog potentially filterable if the OS supports filtering by contained files (though direct folder selection is primary).
    *   Provides a clear indicator to users that a folder is an Iromo collection.
    *   Allows for future expansion with more metadata without changing core file structures (e.g., collection-specific settings, last modified date by Iromo).

**5.2. Alternative (Not Recommended for MVP): Bundled Package**
A single file with a custom extension (e.g., `.iromocoll`) that is internally a package (like a ZIP archive or macOS .app bundle) could be considered for a more "document-like" feel. However, this adds significant implementation complexity for managing the archive and is not recommended for the MVP. The folder-based approach with a manifest is simpler and more transparent.