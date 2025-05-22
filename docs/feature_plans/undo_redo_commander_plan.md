# Project Plan: Undo/Redo and Command Palette Implementation

**Overall Goal:** Implement a robust undo/redo system and a command palette (Commander) for the Iromo application, allowing for greater user control and discoverability of actions.

**Core Concepts:**

1.  **Command Pattern:** Each user operation will be encapsulated as a `Command` object.
    *   `execute()`: Performs the action.
    *   `undo()`: Reverts the action.
    *   `redo()`: (Often) Re-executes the action.
    *   `description`: User-friendly text for display in UI or logs.
2.  **Undo Manager:** A central class (`UndoManager`) will manage a stack of executed commands, providing `undo()` and `redo()` methods.
3.  **Command Registry:** A central place to register all available commands, their names, default shortcuts, and how to instantiate them. This will be used by the Command Palette and Shortcut Manager.

---

## Phase 1: Core Undo/Redo Framework

**Objective:** Establish the foundational classes for the command pattern and undo/redo management.

**Steps:**

1.  **Define `BaseCommand` Abstract Class:**
    *   Location: New file, e.g., `src/commands/base_command.py`
    *   Abstract methods: `execute(self)`, `undo(self)`, `redo(self)` (can default to `execute()`), `description(self)`.
2.  **Implement `UndoManager` Class:**
    *   Location: New file, e.g., `src/undo_manager.py`
    *   Attributes: `undo_stack`, `redo_stack`.
    *   Methods: `execute_command(self, command)`, `undo(self)`, `redo(self)`, `can_undo(self)`, `can_redo(self)`, `clear_stacks(self)`.
    *   PyQt Signals: `undo_text_changed`, `redo_text_changed`, `can_undo_changed`, `can_redo_changed`.
3.  **Integrate `UndoManager` into `MainWindow`:**
    *   In `src/main_window.py`:
        *   Instantiate `UndoManager`.
        *   Add "Undo" and "Redo" `QAction`s to "Edit" menu, connect to `UndoManager`.
        *   Connect signals to enable/disable actions and update text.
        *   Assign standard shortcuts (Ctrl+Z, Ctrl+Y/Ctrl+Shift+Z).

**Mermaid Diagram: Core Undo/Redo**
```mermaid
graph TD
    subgraph MainWindow
        UndoAction[QAction("Undo")]
        RedoAction[QAction("Redo")]
        UndoMgrInstance[UndoManager]
    end

    subgraph UndoManager
        direction LR
        UndoStack["undo_stack (list)"]
        RedoStack["redo_stack (list)"]
        execute_command["execute_command(cmd)"]
        undo_op["undo()"]
        redo_op["redo()"]
    end

    BaseCmd["BaseCommand (ABC)"]
    ConcreteCmd1["ConcreteCommand1"]

    MainWindow -- instantiates & uses --> UndoMgrInstance
    UndoAction -- triggers --> undo_op
    RedoAction -- triggers --> redo_op
    UndoMgrInstance -- manages --> UndoStack
    UndoMgrInstance -- manages --> RedoStack
    execute_command -- calls --> ConcreteCmd1.execute()
    undo_op -- calls --> ConcreteCmd1.undo()
    redo_op -- calls --> ConcreteCmd1.redo()
    ConcreteCmd1 -- inherits from --> BaseCmd
    UndoStack -- contains --> BaseCmd
    RedoStack -- contains --> BaseCmd
```

---

## Phase 2: Implementing Concrete Commands & `DataManager` Enhancements

**Objective:** Create command classes for existing functionalities and add necessary `DataManager` methods.

**Sub-Phase 2.1: `DataManager` Enhancements**
*   In `src/data_manager.py`:
    *   **Implement `delete_topic(self, topic_id)`:**
        *   Delete associated text file.
        *   Delete row from `topics` table.
        *   Handle child topics (e.g., prevent deletion if children exist, or define cascading behavior).
        *   Handle associated extractions.
    *   **Implement `delete_extraction(self, extraction_id)`:**
        *   Delete row from `extractions` table.
    *   **Implement `move_topic(self, topic_id, new_parent_id, new_display_order)`:**
        *   Update `parent_id` and `display_order` in `topics` table.
        *   Adjust `display_order` of sibling topics.

**Sub-Phase 2.2: Concrete Command Classes**
*   Create classes in `src/commands/` (e.g., `src/commands/topic_commands.py`).
1.  **`CreateTopicCommand(BaseCommand)`:**
    *   Uses `data_manager.create_topic()`.
    *   `undo()` uses `data_manager.delete_topic()`.
2.  **`ChangeTopicTitleCommand(BaseCommand)`:**
    *   Uses `data_manager.update_topic_title()`.
    *   `undo()` calls `data_manager.update_topic_title()` with the old title.
3.  **`SaveTopicContentCommand(BaseCommand)`:**
    *   Requires `TopicEditorWidget` to provide `old_content` and `new_content`.
    *   Uses `data_manager.save_topic_content()`.
    *   `undo()` calls `data_manager.save_topic_content()` with `old_content`.
4.  **`ExtractTextCommand(BaseCommand)`:**
    *   Uses `data_manager.create_topic()` for the new extract, `data_manager.create_extraction()`.
    *   `undo()` uses `data_manager.delete_extraction()`, then `data_manager.delete_topic()` for the created extract.
5.  **`MoveTopicCommand(BaseCommand)`:**
    *   Uses `data_manager.move_topic()`.
    *   `undo()` calls `data_manager.move_topic()` with old parent/position.

---

## Phase 3: Integrating Commands into `MainWindow` and Widgets

**Objective:** Refactor existing action handlers and widget logic to use the command system.

**Steps:**

1.  **Modify `MainWindow` methods** (e.g., `extract_text()`, `_handle_new_collection`, `save_current_topic_content`, etc.):
    *   Instead of direct calls, instantiate the appropriate command and execute via `self.undo_manager.execute_command(command)`.
2.  **Modify `KnowledgeTreeWidget`:**
    *   For title changes: Emit signal with `topic_id`, `old_title`, `new_title`.
    *   For reordering (when implemented): Emit signal with `topic_id`, `old_parent_id`, `old_display_order`, `new_parent_id`, `new_display_order`.
3.  **Modify `TopicEditorWidget`:**
    *   Implement `is_dirty` flag (e.g., via `textChanged` signal).
    *   Store `original_content` when a topic is loaded to provide to `SaveTopicContentCommand`.

---

## Phase 4: Command Palette ("Commander")

**Objective:** Implement a searchable, modal palette to execute commands.

**Steps:**

1.  **`CommandRegistry`:**
    *   Location: New file, e.g., `src/command_registry.py`.
    *   `register_command(command_class, name: str, default_shortcut: str = None, description: str = "")`.
    *   `get_commands()`, `find_command_by_name(name: str)`.
2.  **`CommanderDialog(QDialog)` (Modal):**
    *   Location: New file, e.g., `src/commander_dialog.py`.
    *   UI: `QLineEdit` for search, `QListWidget` for results.
    *   Functionality: Filter commands from `CommandRegistry`, instantiate and execute selected command via `MainWindow.undo_manager`.
3.  **Integrate Commander into `MainWindow`:**
    *   Add `QAction` ("Command Palette...") with shortcut (e.g., Ctrl+Shift+P) to show `CommanderDialog`.

**Mermaid Diagram: Commander**
```mermaid
graph TD
    MainWindow --> CommanderAction[QAction("Commander...")]
    CommanderAction -- triggers --> CommanderDialogInstance[CommanderDialog]

    subgraph CommanderDialog
        SearchInput[QLineEdit]
        ResultsList[QListWidget]
    end

    CommanderDialogInstance -- uses --> CommandRegistryInstance[CommandRegistry]
    CommandRegistryInstance -- stores info about --> ConcreteCmd1

    SearchInput -- filters --> ResultsList
    ResultsList -- on activation --> ExecuteCommandFlow

    subgraph ExecuteCommandFlow
        direction LR
        InstantiateCmd[Instantiate Selected Command] --> ExecuteViaUndoMgr[Execute via UndoManager]
    end

    ExecuteViaUndoMgr --> MainWindow.UndoMgrInstance
```

---

## Phase 5: Shortcut Management

**Objective:** Allow users to customize keyboard shortcuts for commands.

**Steps:**

1.  **Update `CommandRegistry`:** Store current shortcut, allow modification.
2.  **`ShortcutManagerDialog(QDialog)`:**
    *   Location: New file, e.g., `src/shortcut_manager_dialog.py`.
    *   UI: List commands and shortcuts, `QKeySequenceEdit` to change.
    *   Functionality: Load/save shortcuts (e.g., via `QSettings`), update `CommandRegistry`.
3.  **Integrate Shortcut Management into `MainWindow`:**
    *   Add `QAction` ("Customize Shortcuts...") to show `ShortcutManagerDialog`.
    *   Load custom shortcuts on startup.

---

## Phase 6: Advanced Commands & Edge Cases (Future Considerations)

*   **Complex `undo()` for `Open/New/CloseCollectionCommand`:** For now, these might just clear undo/redo stacks.
*   **Contextual command availability** in Commander.
*   **Asynchronous commands** (if needed later).