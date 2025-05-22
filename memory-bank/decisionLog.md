# Decision Log

This file records architectural and implementation decisions using a list format.
2025-05-21 22:46:30 - Log of updates made.

*

## Decision

*   Initialize Memory Bank.

## Rationale

*   To maintain project context and facilitate collaboration between modes.

## Implementation Details

*   Created `memory-bank/` directory.
*   Created `productContext.md`, `activeContext.md`, `progress.md`.
---
2025-05-21 22:48:41 - Added decisions from MVP_PLAN.md.

## Decision: Data Storage for MVP (from MVP_PLAN.md)

*   Topic Content Files: Separate plain text files (`.txt`) in `iromo_data/text_files/`, named with UUIDs.
*   SQLite Database (`iromo.sqlite`): Central hub for metadata, KT structure, extractions.
    *   Core Tables: `topics` (id, parent_id, title, text_file_uuid, created_at, updated_at, display_order), `extractions` (id, parent_topic_id, child_topic_id, parent_text_start_char, parent_text_end_char).
*   Highlighting Mechanism: Dynamically applied by UI based on `extractions` table data.

## Rationale: Data Storage for MVP (from MVP_PLAN.md)

*   UUIDs for file naming prevent conflicts and simplify linking.
*   SQLite provides a structured way to manage metadata and relationships.
*   Dynamic highlighting keeps text files clean and relies on relational data for display.

## Implementation Details: Data Storage for MVP (from MVP_PLAN.md)

*   `DataManager` module to handle all data interactions.
*   Specific fields defined for `topics` and `extractions` tables.
*   UI queries `extractions` table to apply formatting.

## Decision: Application Architecture for MVP (from MVP_PLAN.md)

*   High-level components: MainWindow (UI), KnowledgeTreeWidget (UI), TopicEditorWidget (UI), AppLogic (Controller), DataManager (Data Persistence).
*   Data Store: SQLite Database and Text Files.
*   (Mermaid diagram included in MVP_PLAN.md, see systemPatterns.md for visual representation)

## Rationale: Application Architecture for MVP (from MVP_PLAN.md)

*   Separation of concerns between UI, application logic, and data management.
*   Qt's signals and slots for component communication.

## Implementation Details: Application Architecture for MVP (from MVP_PLAN.md)

*   `MainWindow` orchestrates UI and handles actions.
*   `KnowledgeTreeWidget` displays hierarchy and handles title edits.
*   `TopicEditorWidget` displays content and handles text selection/editing.
*   `AppLogic` (likely within MainWindow or separate controller) orchestrates `DataManager` and UI updates.
*   `DataManager` manages persistence to SQLite and text files.
---
2025-05-21 22:49:21 - Added decisions from DATABASE_ARCHITECTURE.md.

## Decision: Core Database Technology (from DATABASE_ARCHITECTURE.md)

*   Utilize the standard Python `sqlite3` library for all database interactions with `iromo.sqlite`.

## Rationale: Core Database Technology (from DATABASE_ARCHITECTURE.md)

*   **Simplicity & Minimal Dependencies:** `sqlite3` is built into Python.
*   **Direct SQL Control:** Allows fine-tuning and optimization.
*   **Sufficiency for Needs:** Capable for current and foreseeable schema/queries.
*   **Existing Solid Foundation:** `src/data_manager.py` already uses this approach robustly.
*   **Key Advantages:** No external dependencies, potential for high performance, widely understood.

## Implementation Details: Core Database Technology (from DATABASE_ARCHITECTURE.md)

*   Continue using `sqlite3` as implemented in `src/data_manager.py`.
*   Adhere to best practices outlined in `DATABASE_ARCHITECTURE.md` (connection handling, SQL injection prevention, migration management, error handling, code organization, transaction management, testing).

## Future Considerations: Database Technology (from DATABASE_ARCHITECTURE.md)

*   If data model or query complexity significantly increases, an ORM (SQLAlchemy, Peewee) could be revisited. For now, direct `sqlite3` is approved.
---
2025-05-21 22:49:56 - Added decisions from LOGGING_IMPLEMENTATION_PLAN.md.

## Decision: Logging Implementation (from LOGGING_IMPLEMENTATION_PLAN.md)

*   **Library:** Python's built-in `logging` module.
*   **Primary Goal:** Implement cycling log files.
*   **Handler:** `logging.handlers.RotatingFileHandler`.
    *   Log File Name: `app.log` (or similar, e.g., `iromo_app.log`).
    *   Max File Size: 10MB.
    *   Backup Files: 5.
*   **Log Format:** `%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s`.
*   **Default Log Level:** `INFO`.
*   **Initialization:** Central `setup_logging()` function called early in `src/main.py`.
*   **Usage:** Module-specific loggers via `logging.getLogger(__name__)`. Replace `print` statements.
*   **Log File Location:** User-accessible application data folder (platform-specific paths provided in plan). Directory to be created if non-existent.

## Rationale: Logging Implementation (from LOGGING_IMPLEMENTATION_PLAN.md)

*   Utilize standard library for simplicity and no external dependencies.
*   Rotating files prevent logs from growing indefinitely and manage disk space.
*   Structured format aids in debugging and tracing.
*   `INFO` level provides a good balance of detail by default.
*   Central setup ensures consistency.
*   `getLogger(__name__)` provides good context for log messages.
*   Standard app data folders are appropriate for user-specific log files.

## Implementation Details: Logging Implementation (from LOGGING_IMPLEMENTATION_PLAN.md)

*   `setup_logging()` to configure root/app logger, handler, formatter, and level.
*   Modules obtain loggers using `logging.getLogger(__name__)`.
*   Specific log levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) to be used appropriately.
*   Code in `setup_logging()` to ensure log directory exists.
*   (Mermaid diagram of logging flow included in LOGGING_IMPLEMENTATION_PLAN.md, see systemPatterns.md for visual representation)
---
2025-05-21 23:41:53 - Resolved sqlite3 datetime DeprecationWarnings.

## Decision: Resolve `sqlite3` `DeprecationWarning`s for `datetime` handling.

*   Address warnings related to deprecated default `datetime` object handling in `sqlite3` with Python 3.12+.

## Rationale: Resolve `sqlite3` `DeprecationWarning`s.

*   Ensure future compatibility of the application with newer Python versions.
*   Adhere to `sqlite3` library best practices for type adaptation.
*   Prevent potential runtime errors if the deprecated default behavior is removed.

## Implementation Details: `sqlite3` `DeprecationWarning` Fix.

*   **File Modified:** `src/data_manager.py`
*   **Import Change:** Changed `from datetime import datetime` to `import datetime as dt`.
*   **Adapter Function:** Defined `adapt_datetime_iso(datetime_obj)` to convert `dt.datetime` objects to ISO 8601 strings.
    ```python
    def adapt_datetime_iso(datetime_obj):
        logger.debug(f"Adapting datetime: {datetime_obj} of type {type(datetime_obj)}")
        return datetime_obj.isoformat()
    ```
*   **Converter Function:** Defined `convert_timestamp_iso(val_bytes)` to convert ISO 8601 strings (retrieved as bytes) back to `dt.datetime` objects.
    ```python
    def convert_timestamp_iso(val_bytes):
        logger.debug(f"Converting timestamp bytes: {val_bytes} of type {type(val_bytes)}")
        val_str = val_bytes.decode() if isinstance(val_bytes, bytes) else val_bytes
        converted = dt.datetime.fromisoformat(val_str)
        logger.debug(f"Converted to datetime: {converted} of type {type(converted)}")
        return converted
    ```
*   **Registration:** Registered the adapter and converter globally for `sqlite3`.
    ```python
    sqlite3.register_adapter(dt.datetime, adapt_datetime_iso)
    sqlite3.register_converter("timestamp", convert_timestamp_iso)
    ```
*   **Connection Update:** Modified `get_db_connection` to include `detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES`.
    ```python
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    ```
*   **Timestamp Creation:** Updated all instances of `datetime.now()` to `dt.datetime.now()`.