# Product Context

This file provides a high-level overview of the project and the expected product that will be created. Initially it is based upon projectBrief.md (if provided) and all other available project-related information in the working directory. This file is intended to be updated as the project evolves, and should be used to inform all other modes of the project's goals and context.
2025-05-21 22:45:51 - Log of updates made will be appended as footnotes to the end of this file.

*

## Project Goal

*   To create an open-source, cross-platform incremental reading and spaced repetition tool, inspired by SuperMemo. The initial focus is on a desktop application with core incremental reading features.

## Key Features

*   Add topics.
*   Paste text into topics.
*   Extract portions of text from a topic into new child topics.
*   Visually see extracted text highlighted (light blue background) in the parent topic.
*   Edit topic titles (initially auto-generated from the first X characters of content).

## Overall Architecture

*   (To be defined)
## MVP Goal (from MVP_PLAN.md)

* Implement a system with a hierarchical Knowledge Tree (KT) where users can add topics, paste text into them, and extract portions of that text into new child topics. Extracted text in the parent should be visually highlighted. Topic titles will initially be the first X characters of their content, editable by the user.

## MVP Feature Breakdown (from MVP_PLAN.md)

1.  **Project Setup &amp; Basic Window:**
    *   Set up Python project environment.
    *   Install `PyQt6`.
    *   Create the main application window class.
    *   Basic menu bar / ribbon placeholder.
2.  **Data Manager Implementation:**
    *   Python module to handle all interactions with `iromo.sqlite` and text files.
    *   Functions for:
        *   Initializing the database and creating tables.
        *   Creating a new topic (DB entry + new empty `.txt` file, initial title generation).
        *   Fetching topic hierarchy.
        *   Fetching/Saving topic text content.
        *   Recording an extraction (new child topic, entry in `extractions` table).
        *   Fetching extraction data.
        *   Updating topic titles.
3.  **Knowledge Tree Widget:**
    *   Custom widget using `QTreeView`.
    *   Load and display topic hierarchy.
    *   Handle selection changes.
    *   Allow inline editing of topic titles, persisting changes via `DataManager`.
4.  **Topic Editor Widget:**
    *   Custom widget using `QTextEdit`.
    *   Load topic text content.
    *   Apply highlighting for existing extractions.
    *   Allow text pasting and editing.
    *   Save changes back to the text file.
5.  **Extraction Logic (`AppLogic`):**
    *   Implement the "extract" action.
    *   Get selected text and character offsets.
    *   Instruct `DataManager` to create a new child topic (with its initial title) and record the extraction.
    *   Refresh the `KnowledgeTreeWidget`.
    *   Re-apply highlighting in the `TopicEditorWidget` for the parent topic.
6.  **Connecting Components:**
    *   Use Qt's signals and slots mechanism.

---
2025-05-21 22:47:57 - Added MVP Goal and Feature Breakdown from MVP_PLAN.md.