# Application Architecture and Distribution Plan

This document outlines the analysis and recommendations for import handling, standard practices for GUI application development, and strategies for distributing the Iromo application.

## 1. Import Handling Analysis & Recommendations

### Current State:
The project currently employs a mix of import styles:
*   **Absolute imports from `src` root:** Files like `src/main.py` and `src/main_window.py` use imports such as `from logger_config import ...` or `from commands.topic_commands import ...`.
*   **Relative imports within subpackages:** `src/commands/topic_commands.py` uses `from ..data_manager import ...` (to go up one level from `commands` to `src`) and `from .base_command import ...` (to import from the current `commands` package).

The application is executed using `python -m src.main` from the project root (`/home/bernardo/src/iromo/`), which correctly adds the root directory to Python's `sys.path`. This makes `src` available as a top-level package. The presence of `src/__init__.py` and `src/commands/__init__.py` correctly designates these directories as Python packages.

### Recommendations for Imports:

While the current system works, standardizing to **explicit relative imports** *within* the `src` package is recommended. This enhances clarity, maintainability, and makes the `src` package more self-contained.

**Proposed Import Strategy (Explicit Relative Imports):**

This strategy treats `src` as the primary application package, and all intra-package imports are relative.

*   In `src/main.py`:
    *   `from logger_config import APP_NAME, setup_logging` &rarr; `from .logger_config import APP_NAME, setup_logging`
    *   `from main_window import MainWindow` &rarr; `from .main_window import MainWindow`
*   In `src/main_window.py`:
    *   `from commands.topic_commands import ...` &rarr; `from .commands.topic_commands import ...`
    *   `from data_manager import ...` &rarr; `from .data_manager import ...`
    *   `from knowledge_tree_widget import ...` &rarr; `from .knowledge_tree_widget import ...`
    *   `from topic_editor_widget import ...` &rarr; `from .topic_editor_widget import ...`
    *   `from undo_manager import ...` &rarr; `from .undo_manager import ...`
*   In `src/commands/topic_commands.py`:
    *   `from ..data_manager import DataManager` (already correct)
    *   `from .base_command import BaseCommand` (already correct)
*   Similar adjustments would apply to other files within the `src` package importing sibling modules or modules from sub-packages.

**Visualizing the Recommended Import Structure:**
```mermaid
graph TD
    A[Project Root (/home/bernardo/src/iromo)] -- "python -m src.main" --> B((src Package));
    B --- C[main.py];
    C -- "from .logger_config import ..." --> D[logger_config.py];
    C -- "from .main_window import ..." --> E[main_window.py];
    E -- "from .data_manager import ..." --> F[data_manager.py];
    E -- "from .commands.topic_commands import ..." --> G[commands/];
    G --- H[topic_commands.py];
    H -- "from ..data_manager import ..." --> F;
    H -- "from .base_command import ..." --> I[base_command.py];
```

**Benefits of Explicit Relative Imports:**
*   **Clarity:** Explicitly shows that imports are occurring within the `src` package.
*   **Reduced Ambiguity:** Avoids potential conflicts if a module name in `src` clashes with a standard library module or a third-party installed module.
*   **Portability:** Makes the `src` package more self-contained. If the project root were moved or renamed, or if `src` were installed as part of a larger system, these relative imports would continue to work without modification.

## 2. Standard Way of Running GUI Applications (Python/PyQt6)

The project already adheres to many standard practices:

*   **Entry Point:** Running with `python -m src.main` is a robust and standard method for packaged applications.
*   **Project Structure:**
    *   **`src` layout:** Placing main source code in a `src` directory is a common and recommended pattern.
    *   **Package Structure:** Using `__init__.py` files to define packages (`src`, `src/commands`) is fundamental.
    *   **Separation of Concerns:** The file organization suggests good separation between UI (PyQt6 widgets), application logic (commands), and data handling.
*   **Virtual Environments:** Using `venv` is a best practice for isolating project dependencies.
*   **Dependency Management:**
    *   It is standard to maintain a `requirements.txt` file in the project root, listing all dependencies (e.g., `PyQt6`). This file is typically generated using `pip freeze > requirements.txt` within the activated virtual environment. This allows others (or yourself on a new machine) to easily install all necessary dependencies using `pip install -r requirements.txt`.
*   **Application Configuration:** Using `QSettings` (as seen in `src/main_window.py`) is the standard Qt way to handle persistent application settings (like window size/position, last opened file).
*   **Logging:** Utilizing Python's built-in `logging` module (configured in `src/logger_config.py` and used throughout the application) is the standard approach for application logging.

## 3. Tools for Application Distribution

To distribute the Python GUI application as a standalone executable for Windows (.exe), Linux, and macOS (.app), several tools are commonly used:

*   **PyInstaller:**
    *   **What it does:** Bundles the Python application (interpreter, code, dependencies, and data files) into a single executable or a directory containing an executable.
    *   **Platforms:** Windows, Linux, macOS.
    *   **Usage:**
        *   Basic: `pyinstaller --onefile --windowed src/main.py`
        *   `--onefile`: Creates a single executable file.
        *   `--windowed`: Prevents a console window from appearing for GUI apps on Windows.
        *   **Spec Files:** For complex projects, PyInstaller uses a `.spec` file (e.g., `main.spec`) for customization (including data files, hidden imports, etc.).
    *   **Considerations:** May need explicit configuration for data files and hidden imports. Code signing might be necessary for macOS.

*   **cx_Freeze:**
    *   **What it does:** Similar to PyInstaller, creates standalone executables.
    *   **Platforms:** Windows, Linux, macOS.
    *   **Usage:** Typically involves creating a `setup.py` script to configure the build process.

*   **Briefcase (BeeWare Project):**
    *   **What it does:** Aims to simplify packaging Python applications for distribution on various platforms, including desktop and mobile, focusing on native-feeling application bundles.
    *   **Platforms:** Windows, Linux, macOS, iOS, Android.
    *   **Usage:** Involves commands like `briefcase create`, `briefcase build`, `briefcase package`.

*   **Nuitka (More Advanced):**
    *   **What it does:** Compiles Python code into C code, then into an executable. Can offer performance benefits and better code obfuscation.
    *   **Platforms:** Windows, Linux, macOS.
    *   **Considerations:** Can be more complex to set up and debug.

**General Distribution Workflow:**
```mermaid
graph TD
    subgraph DevelopmentPhase
        A[Your Python Code (src/)]
        B[Dependencies (from venv/requirements.txt)]
        C[Assets (e.g., icons, docs/project_brief.md, migrations/)]
    end

    DevelopmentPhase --> D{Packaging Tool Selected (e.g., PyInstaller)};

    subgraph PackagingProcess
        D -- "Configuration (e.g., .spec file / setup.py)" --> E[Tool Configuration];
        E --> F[Bundling Application + Python Interpreter + Dependencies];
        F --> G[Handling Assets/Data Files];
    end

    PackagingProcess --> H[Platform-Specific Bundles];
    H --> I[Windows (.exe)];
    H --> J[Linux (Executable)];
    H --> K[macOS (.app)];

    subgraph OptionalPostPackaging
        I --> L[Create Windows Installer (e.g., Inno Setup, NSIS)];
        K --> M[Create macOS Disk Image (.dmg) (e.g., dmgbuild)];
    end
```

**Key Considerations for Distribution:**
*   **Data Files:** Ensure all necessary non-Python files (images, icons, database schema files like those in `migrations/`, documentation if needed) are included.
*   **Icons:** Specify an application icon for executables.
*   **Testing:** Thoroughly test the bundled application on each target platform, ideally on clean machines without Python installed.
*   **Code Signing:** For macOS and Windows, consider signing your application to avoid security warnings and enhance trust. This often involves obtaining a developer certificate.
*   **Installers:** For a better user experience, especially on Windows and macOS, consider creating an installer (e.g., using Inno Setup for Windows, or `dmgbuild` for macOS `.dmg` files).