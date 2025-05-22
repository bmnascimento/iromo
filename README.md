# Iromo (Incremental Reading Of My Own)

## Description

Iromo is an open-source, cross-platform incremental reading and spaced repetition tool, inspired by SuperMemo. The initial focus is on a desktop application built with Python and Qt6, providing core incremental reading features. Users can manage a hierarchical Knowledge Tree, add topics, paste text, extract portions of text into new child topics, and see these extractions visually highlighted.

## Key Features

*   **Knowledge Tree Management:** Organize information hierarchically using a Knowledge Tree (KT).
*   **Topic Editing:** Create new topics, paste text content, and edit topic titles.
*   **Text Extraction:** Extract segments of text from a parent topic to create new, more focused child topics.
*   **Highlighting of Extracted Text:** Visually identify extracted text within parent topics through highlighting.
*   **Undo/Redo Functionality:** Support for undoing and redoing actions (details in `docs/feature_plans/undo_redo_commander_plan.md`).
*   **Data Storage:**
    *   Topic content is stored in individual plain text files.
    *   Metadata, Knowledge Tree structure, and extraction information are managed in an SQLite database.
*   **Database Migrations:** Schema changes are managed via SQL scripts.

## Getting Started / How to Run

### Prerequisites

*   Python 3.x
*   PyQt6 (and its dependencies)

### Running the Application

1.  Clone the repository (if you haven't already).
2.  Navigate to the project root directory.
3.  Ensure all dependencies are installed. You might need to install PyQt6:
    ```bash
    pip install PyQt6
    ```
4.  Run the application using:
    ```bash
    python src/main.py
    ```
5.  On first run, or if no previous collection is found, the application will start in a "No Collection Open" state. You will need to:
    *   Create a **New Collection** (File > New Collection...), which will prompt you to choose a folder name and location. This folder will become your Iromo collection.
    *   Or, **Open an Existing Collection** (File > Open Collection...) by navigating to a previously created Iromo collection folder.

## Project Structure

*   **`src/`**: Contains the main application source code, including UI components, data management, and core logic.
*   **`docs/`**: Includes project documentation, such as the project brief, feature plans, and architectural designs.
*   **`tests/`**: Houses test scripts for various parts of the application.
*   **`migrations/`**: Stores SQL scripts for database schema migrations, ensuring consistent database structure.
*   **`<YourCollectionName>/`** (created by the user via "File > New Collection..."): This is the root folder for an Iromo collection. Each collection is self-contained.
    *   **`text_files/`**: Stores the actual text content for each topic within this specific collection.
    *   **`iromo.sqlite`**: The SQLite database file for this specific collection.
    *   **`iromo_collection.json`**: A manifest file identifying the folder as an Iromo collection and storing metadata.

## License

This project is licensed under the terms found in the [`LICENSE`](LICENSE:1) file.