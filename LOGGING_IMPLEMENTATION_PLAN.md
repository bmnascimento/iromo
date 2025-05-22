# Logging Implementation Plan

This document outlines the plan for implementing a robust logging system in the Python application, replacing `print` statements with a structured logging approach using Python's built-in `logging` module.

## 1. Core Decisions

*   **Library:** Utilize Python's built-in `logging` module.
*   **Primary Goal:** Implement cycling log files for easier debugging and log management.

## 2. Handler Configuration

*   **Handler Type:** `logging.handlers.RotatingFileHandler` will be used.
*   **Log File Name:** `app.log` (or a similar descriptive name, to be decided during implementation, e.g., `iromo_app.log`).
*   **Maximum File Size:** 10MB before rotation.
*   **Backup Files:** Keep 5 backup log files (e.g., `app.log.1`, `app.log.2`, ..., `app.log.5`).

## 3. Log Format

A clear and informative log message format will be used.
*   **Format String:** `%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s`
*   **Example:** `2025-05-21 21:50:00,123 - my_app.module_name - INFO - specific_module:42 - This is an informational message.`

## 4. Log Level

*   **Default Log Level:** `INFO`. This will capture:
    *   `INFO`
    *   `WARNING`
    *   `ERROR`
    *   `CRITICAL`
*   `DEBUG` messages will be suppressed by default but can be enabled for development/troubleshooting by changing the logger's level.

## 5. Initialization and Setup

*   **Central Configuration Function:** A dedicated function (e.g., `setup_logging()`) will be created.
    *   This function will be responsible for:
        1.  Getting the root logger or a specific application-wide logger (e.g., `logging.getLogger('iromo_app')`).
        2.  Creating an instance of `RotatingFileHandler` with the specified file name, `maxBytes`, and `backupCount`.
        3.  Creating an instance of `logging.Formatter` with the defined format string.
        4.  Setting the formatter on the handler.
        5.  Adding the handler to the logger.
        6.  Setting the logger's overall level (e.g., `logger.setLevel(logging.INFO)`).
*   **Invocation:** The `setup_logging()` function should be called once, early in the application's startup sequence (likely in [`src/main.py`](src/main.py:1)).

## 6. Usage in Application Modules

*   **Obtaining Logger Instances:** In each Python module (e.g., [`src/data_manager.py`](src/data_manager.py:1), [`src/knowledge_tree_widget.py`](src/knowledge_tree_widget.py:1), [`src/main_window.py`](src/main_window.py:1), [`src/topic_editor_widget.py`](src/topic_editor_widget.py:1)), a module-specific logger instance will be obtained using:
    ```python
    import logging
    logger = logging.getLogger(__name__)
    ```
    Using `__name__` automatically uses the module's path (e.g., `src.data_manager`) as the logger name, which is helpful for tracing log origins.
*   **Replacing `print` Statements:** All `print()` statements currently used for debugging, event tracking, or error reporting will be replaced with appropriate calls to the logger instance:
    *   `logger.debug("Detailed diagnostic information for troubleshooting.")`
    *   `logger.info("General operational information, milestones, successful operations.")`
    *   `logger.warning("Something unexpected happened, or an indication of a potential problem that doesn't stop execution.")`
    *   `logger.error("A more serious problem occurred that prevented a specific function/operation from performing as expected.")`
    *   `logger.critical("A very serious error, indicating the program itself may be unable to continue running or is in an unstable state.")`

## 7. Log File Location

*   **Strategy:** Log files should be stored in a user-accessible but non-intrusive location.
*   **Recommended Location:** A subdirectory within the user's standard application data folder.
    *   **Linux:** `~/.local/share/YourAppName/logs/` (e.g., `~/.local/share/iromo/logs/`)
    *   **Windows:** `%APPDATA%\YourAppName\logs\` (e.g., `C:\Users\YourUser\AppData\Roaming\iromo\logs\`)
    *   **macOS:** `~/Library/Application Support/YourAppName/logs/` (e.g., `~/Library/Application Support/iromo/logs/`)
*   **Implementation Detail:** The logging setup code should ensure that the chosen log directory exists, creating it if necessary.

## 8. Mermaid Diagram of Logging Flow

```mermaid
graph TD
    A[Application Startup (e.g., main.py)] -- Calls --> Z[setup_logging()];
    Z -- Configures --> B[Root Logger / App Logger (e.g., 'iromo_app')];
    B -- Sets Level --> BL[INFO Level];
    B -- Adds Handler --> D[RotatingFileHandler];
    D -- Uses --> DF[Formatter ('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')];
    D -- Configured with --> DS[Log File: app.log, MaxBytes: 10MB, BackupCount: 5];
    D -- Writes to --> E[app.log (in chosen user data directory)];
    D -- Manages Rotation --> F[app.log.1 ... app.log.5];

    M1[Module 1 (e.g., data_manager.py)] -- Gets Logger --> L1[logging.getLogger(__name__)];
    M1 -- Log Event (e.g., logger.info(...)) --> L1;
    L1 -- Forwards to --> B;

    M2[Module 2 (e.g., main_window.py)] -- Gets Logger --> L2[logging.getLogger(__name__)];
    M2 -- Log Event (e.g., logger.error(...)) --> L2;
    L2 -- Forwards to --> B;
```

This plan provides a comprehensive guide for implementing the logging system.