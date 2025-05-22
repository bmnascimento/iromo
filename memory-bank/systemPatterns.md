# System Patterns *Optional*

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-05-21 22:46:37 - Log of updates made.

*

## Coding Patterns

*   

## Architectural Patterns

*   
### MVP Application Architecture (from MVP_PLAN.md)

**High-Level Components:**

```mermaid
graph TD
    User --&gt;|Interacts with| MainWindow
    MainWindow --&gt;|Displays| KnowledgeTreeWidget
    MainWindow --&gt;|Displays| TopicEditorWidget
    MainWindow --&gt;|Handles Actions: e.g. Alt+X, Edit Title| AppLogic

    KnowledgeTreeWidget --&gt;|Requests/Updates Data, Signals Title Edit| DataManager
    TopicEditorWidget --&gt;|Requests/Updates Data| DataManager
    TopicEditorWidget --&gt;|Signals Extraction| AppLogic

    AppLogic --&gt;|Orchestrates| DataManager
    AppLogic --&gt;|Updates UI via Signals/Slots| MainWindow
    AppLogic --&gt;|Updates UI via Signals/Slots| KnowledgeTreeWidget
    AppLogic --&gt;|Updates UI via Signals/Slots| TopicEditorWidget

    DataManager --&gt;|Reads/Writes| SQLiteDatabase
    DataManager --&gt;|Reads/Writes| TextFiles

    subgraph UI [Qt6]
        MainWindow
        KnowledgeTreeWidget["Knowledge Tree - QTreeView displays &amp; allows title edit"]
        TopicEditorWidget["Topic Editor - QTextEdit displays content, allows selection"]
    end

    subgraph CoreLogic [Python]
        AppLogic["Application Logic/Controller"]
        DataManager["Data Persistence &amp; Management - handles title generation/update"]
    end

    subgraph DataStore
        SQLiteDatabase["SQLite DB - iromo.sqlite"]
        TextFiles["Topic Text Files - *.txt"]
    end
```

**Component Descriptions (from MVP_PLAN.md):**

*   **UI (Qt6):**
    *   `MainWindow`: Main application window.
    *   `KnowledgeTreeWidget`: `QTreeView` for displaying hierarchy and allowing title edits.
    *   `TopicEditorWidget`: `QTextEdit` for displaying content and allowing selection/editing.
*   **CoreLogic (Python):**
    *   `AppLogic`: Application Logic/Controller.
    *   `DataManager`: Handles data persistence and management, including title generation/updates.
*   **DataStore:**
    *   `SQLiteDatabase`: `iromo.sqlite` for metadata.
    *   `TextFiles`: `*.txt` files for topic content.

---
2025-05-21 22:48:59 - Added MVP architecture details from MVP_PLAN.md.

### Logging Flow (from LOGGING_IMPLEMENTATION_PLAN.md)

```mermaid
graph TD
    A[Application Startup (e.g., main.py)] -- Calls --&gt; Z[setup_logging()];
    Z -- Configures --&gt; B[Root Logger / App Logger (e.g., 'iromo_app')];
    B -- Sets Level --&gt; BL[INFO Level];
    B -- Adds Handler --&gt; D[RotatingFileHandler];
    D -- Uses --&gt; DF[Formatter ('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')];
    D -- Configured with --&gt; DS[Log File: app.log, MaxBytes: 10MB, BackupCount: 5];
    D -- Writes to --&gt; E[app.log (in chosen user data directory)];
    D -- Manages Rotation --&gt; F[app.log.1 ... app.log.5];

    M1[Module 1 (e.g., data_manager.py)] -- Gets Logger --&gt; L1[logging.getLogger(__name__)];
    M1 -- Log Event (e.g., logger.info(...)) --&gt; L1;
    L1 -- Forwards to --&gt; B;

    M2[Module 2 (e.g., main_window.py)] -- Gets Logger --&gt; L2[logging.getLogger(__name__)];
    M2 -- Log Event (e.g., logger.error(...)) --&gt; L2;
    L2 -- Forwards to --&gt; B;
```

---
2025-05-21 22:50:13 - Added Logging Flow diagram from LOGGING_IMPLEMENTATION_PLAN.md.
### Database Conceptual Architectural Overview (from DATABASE_ARCHITECTURE.md)

```mermaid
graph TD
    A["Application Logic (e.g., UI, Services)"] --&gt; B[src/data_manager.py]
    B -- Uses sqlite3 module --&gt; C["iromo.sqlite Database File"]
    B -- Manages Schema via --&gt; D["migrations/*.sql Files"]
```

---
2025-05-21 22:49:34 - Added Database architecture details from DATABASE_ARCHITECTURE.md.

### Coding Patterns (Logging - from LOGGING_IMPLEMENTATION_PLAN.md)

*   **Log Format String:**
    *   `%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s`
    *   Example: `2025-05-21 21:50:00,123 - my_app.module_name - INFO - specific_module:42 - This is an informational message.`
*   **Obtaining Logger Instances:**
    *   In each Python module:
      ```python
      import logging
      logger = logging.getLogger(__name__)
      ```
*   **Usage:**
    *   Replace `print()` statements with:
        *   `logger.debug("Detailed diagnostic information.")`
        *   `logger.info("General operational information.")`
        *   `logger.warning("Unexpected event or potential problem.")`
        *   `logger.error("Serious problem preventing an operation.")`
        *   `logger.critical("Very serious error, program stability at risk.")`

---
2025-05-21 22:50:29 - Added Logging coding patterns from LOGGING_IMPLEMENTATION_PLAN.md.
## Coding Patterns (Database - from DATABASE_ARCHITECTURE.md)

*   **Consistent Connection Handling:**
    *   Use `get_db_connection()` for establishing connections.
    *   Ensure connections are reliably closed (e.g., `try...finally` or function-scoped open/close).
*   **Security (Prevent SQL Injection):**
    *   **Critically Important:** Always use parameterized queries (e.g., `cursor.execute("SELECT * FROM topics WHERE id = ?", (topic_id,))`). Do not use string formatting/concatenation with external input.
*   **Migration Management:**
    *   Use ordered SQL scripts in `migrations/`.
    *   Track applied migrations in `schema_migrations` table.
    *   All schema changes via new, documented migration files.
*   **Error Handling:**
    *   Implement `try...except sqlite3.Error as e:` for all database operations.
    *   Handle exceptions gracefully (logging, `conn.rollback()`).
*   **Code Organization (for `src/data_manager.py`):**
    *   Maintain clear, well-documented functions.
    *   Consider refactoring if it grows excessively large.
*   **Transaction Management:**
    *   Use `conn.commit()` explicitly for logical units of work.
    *   Use `conn.rollback()` in error handling.
*   **Testing (for `src/data_manager.py`):**
    *   Develop and maintain tests for data access functions.
    *   Consider in-memory SQLite (`:memory:`) for faster, isolated tests.
## Testing Patterns

*