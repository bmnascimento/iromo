import json
import logging
import os
import sys

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .commands.topic_commands import (
    ChangeTopicTitleCommand,
    CreateTopicCommand,
    ExtractTextCommand,
    SaveTopicContentCommand,
)
from .data_manager import DB_FILENAME, TEXT_FILES_SUBDIR, DataManager
from .knowledge_tree_widget import KnowledgeTreeWidget
from .topic_editor_widget import TopicEditorWidget
from .undo_manager import UndoManager
# Import MoveTopicCommand when tree reordering is implemented
logger = logging.getLogger(__name__)
APP_ORGANIZATION_NAME = "IromoOrg" # For QSettings
APP_NAME = "Iromo" # For QSettings
COLLECTION_MANIFEST_FILE = "iromo_collection.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.data_manager = None
        self.active_collection_path = None
        self.undo_manager = UndoManager(self)

        self.setWindowTitle(f"{APP_NAME} - No Collection Open")
        self.setGeometry(100, 100, 1024, 768)

        self._create_menu_bar()
        self._create_tool_bar()
        self._setup_central_widget()
        self._connect_signals() # UndoManager signals connected here
        
        self._update_ui_for_collection_state() # Initial UI state
        self.undo_manager._update_signals() # Ensure initial state of undo/redo actions
        self._try_load_last_collection()
        self.undo_manager.command_executed.connect(self._handle_command_executed)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        new_collection_action = QAction("&New Collection...", self)
        new_collection_action.triggered.connect(self._handle_new_collection)
        file_menu.addAction(new_collection_action)

        open_collection_action = QAction("&Open Collection...", self)
        open_collection_action.triggered.connect(self._handle_open_collection)
        file_menu.addAction(open_collection_action)

        self.close_collection_action = QAction("&Close Collection", self)
        self.close_collection_action.triggered.connect(self._handle_close_collection)
        file_menu.addAction(self.close_collection_action)
        
        file_menu.addSeparator()

        self.new_topic_action = QAction("&New Topic", self)
        self.new_topic_action.triggered.connect(self._handle_new_topic_action)
        file_menu.addAction(self.new_topic_action)

        self.save_content_action = QAction("&Save Content", self)
        self.save_content_action.triggered.connect(self.save_current_topic_content)
        file_menu.addAction(self.save_content_action)
        
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) # QMainWindow.close
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) # Ctrl+Z
        self.undo_action.triggered.connect(self.undo_manager.undo)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo) # Ctrl+Y (Windows/Linux), Shift+Ctrl+Z (macOS)
        self.redo_action.triggered.connect(self.undo_manager.redo)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()
        # Add other edit actions like Cut, Copy, Paste here if needed

        view_menu = menu_bar.addMenu("&View")
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        self.extract_action_toolbar = QAction("Extract (Alt+X)", self)
        self.extract_action_toolbar.triggered.connect(self.extract_text)
        self.extract_action_toolbar.setShortcut("Alt+X")
        self.addAction(self.extract_action_toolbar) # Add shortcut to window context
        toolbar.addAction(self.extract_action_toolbar)

        self.save_content_action_toolbar = QAction("Save Content", self)
        self.save_content_action_toolbar.triggered.connect(self.save_current_topic_content)
        toolbar.addAction(self.save_content_action_toolbar)

    def _setup_central_widget(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree_widget = KnowledgeTreeWidget() # Will need update for DM
        self.editor_widget = TopicEditorWidget() # Will need update for DM
        
        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.editor_widget)
        self.splitter.setSizes([self.width() // 3, 2 * self.width() // 3])
        self.setCentralWidget(self.splitter)

    def _connect_signals(self):
        self.tree_widget.topic_selected.connect(self.handle_topic_selected)
        self.tree_widget.topic_title_changed.connect(self.handle_topic_title_changed)

        # Connect UndoManager signals
        self.undo_manager.can_undo_changed.connect(self.undo_action.setEnabled)
        self.undo_manager.can_redo_changed.connect(self.redo_action.setEnabled)
        self.undo_manager.undo_text_changed.connect(self.undo_action.setText)
        self.undo_manager.redo_text_changed.connect(self.redo_action.setText)

    def _update_ui_for_collection_state(self):
        collection_open = self.data_manager is not None
        
        self.close_collection_action.setEnabled(collection_open)
        self.new_topic_action.setEnabled(collection_open)
        self.save_content_action.setEnabled(collection_open)
        self.save_content_action_toolbar.setEnabled(collection_open)
        self.extract_action_toolbar.setEnabled(collection_open)
        
        # Undo/Redo actions are managed by UndoManager's signals primarily,
        # but should also be disabled if no collection is open.
        # The clear_stacks() call in _open_collection/_handle_close_collection
        # will trigger _update_signals in UndoManager, which correctly sets their state.
        if not collection_open:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)

        if collection_open and self.active_collection_path:
            collection_name = os.path.basename(self.active_collection_path)
            self.setWindowTitle(f"{APP_NAME} - {collection_name}")
        else:
            self.setWindowTitle(f"{APP_NAME} - No Collection Open")
            self.tree_widget.clear_tree() # Assumes method exists
            self.editor_widget.clear_content() # Assumes method exists
            
    def _save_last_collection_path(self, path):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        if path:
            settings.setValue("last_opened_collection", path)
        else:
            settings.remove("last_opened_collection")

    def _try_load_last_collection(self):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        last_path = settings.value("last_opened_collection")
        if last_path and os.path.isdir(last_path):
            logger.info(f"Attempting to load last opened collection: {last_path}")
            self._open_collection(last_path)
        else:
            logger.info("No last opened collection path found or path is invalid.")

    def _handle_new_collection(self):
        dir_path = QFileDialog.getSaveFileName(
            self, 
            "Create New Collection Folder", 
            os.path.expanduser("~"), # Start in home directory
            "Folders" # This is a bit of a hack for QFileDialog to act like a folder creator
                      # A better way might be to get a directory and then append a new folder name.
                      # For now, user selects/creates a folder.
        )[0] # getSaveFileName returns a tuple (filePath, selectedFilter)

        if not dir_path:
            return # User cancelled

        # Ensure the directory exists, QFileDialog for saving might not create it.
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {dir_path}\n{e}")
                return
        elif not os.path.isdir(dir_path):
             QMessageBox.critical(self, "Error", f"Selected path is not a directory: {dir_path}")
             return

        # Check if it's already a collection or contains conflicting files
        manifest_path = os.path.join(dir_path, COLLECTION_MANIFEST_FILE)
        db_path = os.path.join(dir_path, DB_FILENAME)
        text_dir_path = os.path.join(dir_path, TEXT_FILES_SUBDIR)

        if os.path.exists(manifest_path) or os.path.exists(db_path) or os.path.exists(text_dir_path):
            reply = QMessageBox.question(self, "Warning",
                                         "The selected directory is not empty or might already be an Iromo collection. "
                                         "Do you want to try to initialize it as a new collection anyway? "
                                         "(Existing Iromo data might be overwritten or lead to errors)",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Create manifest file
        try:
            with open(manifest_path, 'w') as f:
                json.dump({
                    "type": "iromo_collection",
                    "version": "1.0",
                    "created_at": QSettings().value("app_version", "unknown") # Placeholder for app version
                }, f, indent=2)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not create manifest file: {manifest_path}\n{e}")
            return

        self._open_collection(dir_path, is_new=True)


    def _handle_open_collection(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Iromo Collection", os.path.expanduser("~"))
        if dir_path:
            self._open_collection(dir_path)

    def _open_collection(self, collection_path, is_new=False):
        manifest_path = os.path.join(collection_path, COLLECTION_MANIFEST_FILE)
        
        if not is_new and not os.path.exists(manifest_path):
            QMessageBox.warning(self, "Not an Iromo Collection",
                                f"The selected folder '{collection_path}' does not appear to be a valid Iromo collection (missing '{COLLECTION_MANIFEST_FILE}').")
            return

        if self.data_manager: # Close existing collection first
            self._handle_close_collection()

        try:
            self.data_manager = DataManager(collection_path)
            self.data_manager.initialize_collection_storage() # Creates DB, text_files dir, applies migrations
            self.active_collection_path = collection_path
            
            # Load data into UI
            self.tree_widget.load_tree_data(self.data_manager) # Assumes method exists
            self.editor_widget.clear_content() # Clear editor for new collection
            self.undo_manager.clear_stacks()

            self._save_last_collection_path(collection_path)
            logger.info(f"Successfully opened collection: {collection_path}")
        except Exception as e:
            logger.error(f"Failed to open or initialize collection at {collection_path}: {e}")
            QMessageBox.critical(self, "Error Opening Collection", f"Could not open or initialize collection: {collection_path}\n{e}")
            self.data_manager = None
            self.active_collection_path = None
        
        self._update_ui_for_collection_state()

    def _handle_close_collection(self):
        if not self.data_manager:
            return

        # Potentially prompt to save unsaved changes if any
        logger.info(f"Closing collection: {self.active_collection_path}")
        self.data_manager = None
        self.active_collection_path = None
        self._save_last_collection_path(None) # Clear last opened path
        self.undo_manager.clear_stacks()
        self._update_ui_for_collection_state()


    # --- Command Execution Handlers & Signal Handlers ---

    def _handle_command_executed(self, command):
        """
        Slot connected to UndoManager.command_executed signal.
        Performs any necessary UI updates after a command has been successfully executed.
        """
        if isinstance(command, SaveTopicContentCommand):
            if self.editor_widget.current_topic_id == command.topic_id:
                self.editor_widget.mark_as_saved()
        # Add other command-specific UI updates here if needed

    def _handle_new_topic_action(self):
        if not self.data_manager:
            QMessageBox.information(self, "New Topic", "No collection is open.")
            return

        # Determine parent_id (e.g., currently selected in tree, or None for root)
        current_tree_selection = self.tree_widget.get_current_selected_topic_id() # Assumes method exists
        parent_id = current_tree_selection if current_tree_selection else None
        
        # For simplicity, new topics are created with default title and empty content initially.
        # A dialog could be shown here to get title/content from user.
        cmd = CreateTopicCommand(
            data_manager=self.data_manager,
            tree_widget=self.tree_widget,
            editor_widget=self.editor_widget,
            parent_id=parent_id,
            custom_title="New Topic", # Or prompt user
            text_content=""
        )
        try:
            self.undo_manager.execute_command(cmd)
            # Optionally, select the new topic in the tree/editor if not handled by command's UI update
            if cmd.new_topic_id:
                 self.tree_widget.select_topic_item(cmd.new_topic_id) # Assumes method exists
                 self.handle_topic_selected(cmd.new_topic_id) # To load it in editor
        except Exception as e:
            logger.error(f"Error executing New Topic command: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not create new topic: {e}")

    def handle_topic_selected(self, topic_id):
        if not self.data_manager:
            logger.warning("handle_topic_selected called but no collection is open.")
            return

        logger.info(f"Topic selected - ID: {topic_id}")
        # Prompt to save if current editor is dirty
        if self.editor_widget.current_topic_id and \
           self.editor_widget.current_topic_id != topic_id and \
           self.editor_widget.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         f"Topic '{self.editor_widget.current_topic_id}' has unsaved changes. Save before switching?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_current_topic_content(prompt_if_no_topic=False)
                if self.editor_widget.is_dirty(): # If save failed or was cancelled by user somehow
                    return # Don't switch topic
            elif reply == QMessageBox.StandardButton.Cancel:
                return # Don't switch topic
            # If Discard, proceed to load new topic

        # Original logic for saving (now part of the dirty check above)
        # if self.editor_widget.current_topic_id and self.editor_widget.current_topic_id != topic_id:
        #     logger.info(f"Saving content for {self.editor_widget.current_topic_id} before switching to {topic_id}.")
        #     self.save_current_topic_content(prompt_if_no_topic=False)
        
        # Pass data_manager to load_topic_content
        self.editor_widget.load_topic_content(topic_id, self.data_manager) # Assumes method signature updated

    def handle_topic_title_changed(self, topic_id, old_title, new_title): # Assuming old_title is now provided
        if not self.data_manager:
            logger.warning("handle_topic_title_changed called but no collection is open.")
            return

        if old_title == new_title:
            return # No change

        logger.info(f"Topic title change requested - ID: {topic_id}, Old: '{old_title}', New: '{new_title}'")
        
        cmd = ChangeTopicTitleCommand(
            data_manager=self.data_manager,
            tree_widget=self.tree_widget,
            topic_id=topic_id,
            old_title=old_title,
            new_title=new_title
        )
        try:
            self.undo_manager.execute_command(cmd)
        except Exception as e:
            logger.error(f"Error executing Change Topic Title command: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not change topic title: {e}")
            # Optionally, revert UI change in tree_widget if command failed
            if hasattr(self.tree_widget, 'update_topic_item_title'):
                self.tree_widget.update_topic_item_title(topic_id, old_title)
            
    def save_current_topic_content(self, prompt_if_no_topic=True): # prompt_if_no_topic might be less relevant now
        if not self.data_manager or not self.editor_widget.current_topic_id:
            if prompt_if_no_topic: # Keep for direct calls if any, though mostly driven by dirty state
                QMessageBox.information(self, "Save Content", "No topic loaded or collection open.")
            return

        if not self.editor_widget.is_dirty() and prompt_if_no_topic: # prompt_if_no_topic to allow force save for non-dirty
            logger.info(f"Content for topic {self.editor_widget.current_topic_id} is not modified. Save not required.")
            # QMessageBox.information(self, "Save Content", "No changes to save.") # Optional user feedback
            return

        topic_id = self.editor_widget.current_topic_id
        new_content = self.editor_widget.get_current_content()
        old_content = self.editor_widget.original_content
        
        # Get topic title for command description
        topic_details = self.data_manager.get_topic_details(topic_id)
        topic_title = topic_details['title'] if topic_details else topic_id

        cmd = SaveTopicContentCommand(
            data_manager=self.data_manager,
            topic_id=topic_id,
            old_content=old_content,
            new_content=new_content,
            topic_title=topic_title
        )
        try:
            self.undo_manager.execute_command(cmd)
            # self.editor_widget.mark_as_saved() # This is now handled by _handle_command_executed
        except Exception as e:
            logger.error(f"Error executing Save Content command for topic {topic_id}: {e}", exc_info=True)
            QMessageBox.critical(self, "Save Error", f"Could not save content for topic {topic_id}: {e}")
            
    def extract_text(self):
        if not self.data_manager or not self.editor_widget.current_topic_id:
            QMessageBox.information(self, "Extract Text", "No topic loaded or collection open to extract from.")
            return

        parent_topic_id = self.editor_widget.current_topic_id
        selected_text, start_char, end_char = self.editor_widget.get_selected_text_and_offsets()

        if not selected_text:
            QMessageBox.information(self, "Extract Text", "Please select text to extract.")
            return

        # If the current editor content is dirty, prompt to save first.
        # Extraction modifies the parent (by adding a highlight), so it's good practice.
        if self.editor_widget.is_dirty():
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "The current topic has unsaved changes. Save before extracting?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_current_topic_content(prompt_if_no_topic=False)
                if self.editor_widget.is_dirty(): # Save failed
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
            # If Discard, proceed with extraction using current (unsaved) content state for offsets.

        logger.info(f"Attempting to extract: '{selected_text}' from parent {parent_topic_id} (chars {start_char}-{end_char})")

        cmd = ExtractTextCommand(
            data_manager=self.data_manager,
            tree_widget=self.tree_widget,
            editor_widget=self.editor_widget,
            parent_topic_id=parent_topic_id,
            selected_text=selected_text,
            start_char=start_char,
            end_char=end_char
        )
        try:
            self.undo_manager.execute_command(cmd)
            # UI updates are handled by the command itself
        except Exception as e:
            logger.error(f"Error executing Extract Text command: {e}", exc_info=True)
            QMessageBox.critical(self, "Extraction Error", f"Could not extract text: {e}")

    def closeEvent(self, event):
        # Override QMainWindow's closeEvent to handle unsaved changes or other cleanup
        if self.data_manager and self.editor_widget.is_dirty():
            reply = QMessageBox.question(self, 'Unsaved Changes',
                                         "The current topic has unsaved changes. Save before closing?",
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                self.save_current_topic_content(prompt_if_no_topic=False)
                if self.editor_widget.is_dirty(): # Save failed or was cancelled
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            # If Discard, proceed to close
        
        # Original close logic (now after dirty check)
        if self.data_manager:
             self._handle_close_collection() # This already clears undo_manager stacks
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Ensure MIGRATIONS_DIR exists for testing, as DataManager expects it
    if not os.path.exists(DataManager.migrations_dir): # Access class variable for default
        os.makedirs(DataManager.migrations_dir)
        logger.info(f"Created dummy migrations directory for main_window test: {DataManager.migrations_dir}")
    
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())