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

*   **General Framework:** Use `pytest` for its flexibility and plugin ecosystem.
*   **Qt Specifics:** Utilize `pytest-qt` for testing PyQt6 components, especially the `qtbot` fixture for simulating user interactions and managing the Qt event loop.
*   **Mocking:** Employ `unittest.mock` (or `pytest-mock`) for isolating components during tests (e.g., mocking `DataManager` when testing UI logic).

### Levels of Testing & TDD Approach:

1.  **Unit Tests (High TDD Focus):**
    *   **Target:** `src/data_manager.py` (database interactions, file operations), business logic in `AppLogic` (if separated, or testable methods within `MainWindow`), internal logic of custom widgets (`KnowledgeTreeWidget`, `TopicEditorWidget`) not requiring full rendering.
    *   **Strategy:** Write tests first. Use in-memory SQLite (`:memory:`) or mocks for `DataManager` tests. For widgets, test data processing, model updates, and signal emissions in isolation.

2.  **Integration Tests (Moderate TDD Focus):**
    *   **Target:** Interactions between `AppLogic` and `DataManager`, `MainWindow` orchestrating widgets, signal/slot connections.
    *   **Strategy:** Define interaction contracts. Test that components correctly call each other and that data flows as expected. `qtbot.waitSignal` can be useful here.

3.  **UI/End-to-End (E2E) Tests (Selective, Less Pure TDD):**
    *   **Target:** Critical user workflows through the actual GUI.
    *   **Strategy:** Use `pytest-qt`'s `qtbot` to simulate user actions (clicks, typing). Focus on verifying behavior and key UI state changes, not pixel-perfect appearance. These are good for regression prevention.

### TDD for GUI Components:

*   **Architect for Testability:**
    *   Consider patterns like Model-View-Presenter (MVP) or Model-View-ViewModel (MVVM) to separate presentation logic from views, making the Presenter/ViewModel highly unit-testable with TDD.
    *   Strive to make `AppLogic` (or equivalent controller/presenter classes) testable in isolation from the actual UI rendering.
*   **Test Widget Behavior & API:**
    *   For custom widgets (`KnowledgeTreeWidget`, `TopicEditorWidget`):
        *   Test their public methods (e.g., `load_topic_content`).
        *   Verify correct signal emissions in response to internal logic or simulated events.
        *   Test how they update their internal models or state based on input.
*   **Focus on Behavior, Not Exact Appearance:** GUI tests should confirm functionality, not be overly sensitive to minor visual changes.

### Specific Recommendations for Iromo:

*   **`DataManager`:** Prime candidate for rigorous TDD.
*   **`AppLogic`:** If refactored into a separate class, TDD is highly applicable. If methods remain in `MainWindow`, test them by instantiating `MainWindow` and mocking its dependencies.
*   **Custom Widgets:** Use `pytest-qt` to test their data handling, model updates, and signal emissions.
*   **Critical Flows:** Implement UI tests for core functionalities like topic creation and text extraction using `qtbot`.

---
2025-05-21 22:57:54 - Added detailed GUI testing strategies and TDD recommendations.