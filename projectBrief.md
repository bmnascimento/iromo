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
    *   All text files reside in a dedicated data directory: `iromo_data/text_files/`.
    *   Files are named using UUIDs (e.g., `abcdef12-3456-7890-abcd-ef1234567890.txt`) to prevent naming conflicts and simplify linking.
*   **SQLite Database (`iromo.sqlite`):**
    *   Serves as the central hub for metadata, KT structure, extraction information, and future features (search indexes, statistics).
    *   **Key Tables:**
        *   `schema_migrations`: Tracks applied database schema migrations.
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
    *   Schema changes are managed via SQL scripts stored in the `migrations/` directory (e.g., `001_initial_schema.sql`).
    *   The `data_manager.initialize_database()` function applies pending migrations.
*   **Highlighting Mechanism:**
    *   Extracted text in a parent topic is highlighted with a light blue background.
    *   This is managed dynamically by the `TopicEditorWidget` by querying the `extractions` table and applying formatting based on character offsets.

## 4. Application Architecture

The application follows a model-view-controller like pattern, with distinct components for UI, application logic, and data management.

```mermaid
graph TD
    User -->|Interacts with| MainWindowUI["MainWindow (UI Orchestrator)"]
    
    MainWindowUI -->|Displays & Delegates to| KnowledgeTreeWidgetUI["KnowledgeTreeWidget (QTreeView)"]
    MainWindowUI -->|Displays & Delegates to| TopicEditorWidgetUI["TopicEditorWidget (QTextEdit)"]
    
    KnowledgeTreeWidgetUI -->|Emits Signals (Selection, Title Change)| MainWindowUI
    TopicEditorWidgetUI -->|Provides Data (Selected Text, Content)| MainWindowUI
    
    MainWindowUI -->|Handles User Actions & Events| AppLogic["Application Logic (in MainWindow methods)"]
    
    AppLogic -->|Uses| DataManagerMod["DataManager Module"]
    
    DataManagerMod -->|Reads/Writes| SQLiteDatabaseStore["SQLite DB (iromo.sqlite)"]
    DataManagerMod -->|Reads/Writes| TextFilesStore["Topic Text Files (*.txt)"]

    subgraph UI_Layer [UI (PyQt6 - src/main_window.py, src/knowledge_tree_widget.py, src/topic_editor_widget.py)]
        MainWindowUI
        KnowledgeTreeWidgetUI
        TopicEditorWidgetUI
    end

    subgraph Core_Logic_Layer [Core Logic & Data (Python - src/data_manager.py)]
        AppLogic
        DataManagerMod
    end

    subgraph Data_Storage_Layer [Data Store (iromo_data/, migrations/)]
        SQLiteDatabaseStore
        TextFilesStore
    end
```

**Key Modules & Classes:**

*   **`src/main.py`**:
    *   `run_app()`: Entry point of the application. Initializes logging, `QApplication`, `MainWindow`, and starts the event loop.
*   **`src/main_window.py` (`MainWindow` class):**
    *   Main application window, inherits `QMainWindow`.
    *   Orchestrates UI components (`KnowledgeTreeWidget`, `TopicEditorWidget`) using a `QSplitter`.
    *   Sets up menus, toolbars, and connects signals from widgets to handler methods.
    *   Handles core application logic like text extraction (`extract_text()`), saving content (`save_current_topic_content()`), and responding to topic selection/title changes.
    *   Calls `data_manager.initialize_database()` on startup.
    *   Includes `_create_test_data_if_needed()` for consistent debugging of highlighting.
*   **`src/data_manager.py`**:
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
*   **`src/knowledge_tree_widget.py` (`KnowledgeTreeWidget` class):**
    *   Custom widget inheriting `QTreeView`.
    *   Displays the topic hierarchy using `QStandardItemModel`.
    *   Loads data via `data_manager.get_topic_hierarchy()`.
    *   Allows inline editing of topic titles.
    *   Emits signals:
        *   `topic_selected(topic_id: str)`
        *   `topic_title_changed(topic_id: str, new_title: str)`
    *   Provides methods `add_topic_item()` and `update_topic_item_title()` for programmatic tree updates.
*   **`src/topic_editor_widget.py` (`TopicEditorWidget` class):**
    *   Custom widget inheriting `QTextEdit`.
    *   Displays and allows editing of the selected topic's content.
    *   `load_topic_content()`: Fetches and displays topic text, then applies existing highlights.
    *   `_apply_existing_highlights()`: Highlights all previously extracted segments.
    *   `apply_extraction_highlight()`: Applies background color to a specified text range.
    *   `get_current_content()`: Returns current text.
    *   `get_selected_text_and_offsets()`: Returns selected text and its start/end character positions.
*   **`src/logger_config.py`**:
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