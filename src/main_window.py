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
            new_data_manager = DataManager(collection_path)
            new_data_manager.initialize_collection_storage() # Creates DB, text_files dir, applies migrations
            
            self.data_manager = new_data_manager
            self.active_collection_path = collection_path
            
            # Connect DataManager signals
            self.data_manager.topic_created.connect(self._on_dm_topic_created)
            self.data_manager.topic_title_changed.connect(self._on_dm_topic_title_changed)
            self.data_manager.topic_content_saved.connect(self._on_dm_topic_content_saved)
            self.data_manager.topic_deleted.connect(self._on_dm_topic_deleted)
            self.data_manager.extraction_created.connect(self._on_dm_extraction_created)
            self.data_manager.extraction_deleted.connect(self._on_dm_extraction_deleted)
            self.data_manager.topic_moved.connect(self._on_dm_topic_moved)
            self.data_manager.data_changed_bulk.connect(self._on_dm_data_changed_bulk)

            # Load data into UI
            self.tree_widget.load_tree_data(self.data_manager)
            self.editor_widget.clear_content()
            self.undo_manager.clear_stacks()

            self._save_last_collection_path(collection_path)
            logger.info(f"Successfully opened collection: {collection_path}")
        except Exception as e:
            logger.error(f"Failed to open or initialize collection at {collection_path}: {e}", exc_info=True)
            QMessageBox.critical(self, "Error Opening Collection", f"Could not open or initialize collection: {collection_path}\n{e}")
            if self.data_manager: # Disconnect if connection partially failed
                try:
                    self.data_manager.topic_created.disconnect(self._on_dm_topic_created)
                    self.data_manager.topic_title_changed.disconnect(self._on_dm_topic_title_changed)
                    self.data_manager.topic_content_saved.disconnect(self._on_dm_topic_content_saved)
                    self.data_manager.topic_deleted.disconnect(self._on_dm_topic_deleted)
                    self.data_manager.extraction_created.disconnect(self._on_dm_extraction_created)
                    self.data_manager.extraction_deleted.disconnect(self._on_dm_extraction_deleted)
                    self.data_manager.topic_moved.disconnect(self._on_dm_topic_moved)
                    self.data_manager.data_changed_bulk.disconnect(self._on_dm_data_changed_bulk)
                except TypeError: # Signals might not be connected if DM init failed early
                    pass
            self.data_manager = None
            self.active_collection_path = None
        
        self._update_ui_for_collection_state()

    def _handle_close_collection(self):
        if not self.data_manager:
            return

        # Potentially prompt to save unsaved changes if any
        logger.info(f"Closing collection: {self.active_collection_path}")

        # Disconnect DataManager signals
        if self.data_manager:
            try:
                self.data_manager.topic_created.disconnect(self._on_dm_topic_created)
                self.data_manager.topic_title_changed.disconnect(self._on_dm_topic_title_changed)
                self.data_manager.topic_content_saved.disconnect(self._on_dm_topic_content_saved)
                self.data_manager.topic_deleted.disconnect(self._on_dm_topic_deleted)
                self.data_manager.extraction_created.disconnect(self._on_dm_extraction_created)
                self.data_manager.extraction_deleted.disconnect(self._on_dm_extraction_deleted)
                self.data_manager.topic_moved.disconnect(self._on_dm_topic_moved)
                self.data_manager.data_changed_bulk.disconnect(self._on_dm_data_changed_bulk)
            except TypeError: # Signals might not be connected if DM init failed early or already disconnected
                logger.warning("Error disconnecting DataManager signals, possibly already disconnected or never connected.")
                pass


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
        This can be used for UI actions not directly tied to DataManager state changes,
        or for actions that need to happen *after* DataManager signals have been processed.
        """
        # Example: If a command had a side effect like changing selection,
        # that wasn't a direct data change, it could be handled here.
        # For now, most UI updates are driven by DataManager signals.
        
        # The SaveTopicContentCommand's effect on editor's dirty state
        # is now handled by _on_dm_topic_content_saved.
        pass
        # Add other command-specific UI updates here if needed,
        # particularly those not covered by DataManager signals.

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
            parent_id=parent_id,
            custom_title="New Topic", # Or prompt user
            text_content=""
        )
        try:
            self.undo_manager.execute_command(cmd)
            # UI update (e.g., selecting the new topic) will be handled by DataManager signals
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
            topic_id=topic_id,
            old_title=old_title,
            new_title=new_title
        )
        try:
            self.undo_manager.execute_command(cmd)
            # UI update will be handled by DataManager signals.
            # If command execution fails, the DataManager signal won't be emitted,
            # so the UI won't change. If it succeeds, the signal will trigger the update.
            # The tree_widget itself handles the inline edit, if it fails, MainWindow
            # should catch the error from execute_command and could tell tree_widget to revert.
            # For now, the command failing will prevent the DataManager signal.
        except Exception as e:
            logger.error(f"Error executing Change Topic Title command: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Could not change topic title: {e}")
            # Revert optimistic UI update in tree_widget if the command failed
            # This assumes the tree_widget.topic_title_changed signal (which calls this handler)
            # was emitted *after* the tree widget visually changed the title.
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
            parent_topic_id=parent_topic_id,
            selected_text=selected_text,
            start_char=start_char,
            end_char=end_char
        )
        try:
            self.undo_manager.execute_command(cmd)
            # UI updates (new topic in tree, highlighting in editor) will be handled by DataManager signals
        except Exception as e:
            logger.error(f"Error executing Extract Text command: {e}", exc_info=True)
            QMessageBox.critical(self, "Extraction Error", f"Could not extract text: {e}")

    # --- DataManager Signal Handlers ---

    def _on_dm_topic_created(self, topic_id: str, parent_id: str, title: str, text_content: str):
        logger.info(f"DM SIGNAL: Topic Created - ID: {topic_id}, Parent: {parent_id}, Title: '{title}'")
        if self.tree_widget and hasattr(self.tree_widget, 'add_topic_item'):
            self.tree_widget.add_topic_item(
                topic_id=topic_id,
                title=title,
                parent_id=parent_id
            )
            # Optionally, select the new topic
            self.tree_widget.select_topic_item(topic_id) # Assumes method exists
            self.handle_topic_selected(topic_id) # To load it in editor
        else:
            logger.warning("Tree widget not available for UI update on topic_created.")

    def _on_dm_topic_title_changed(self, topic_id: str, new_title: str):
        logger.info(f"DM SIGNAL: Topic Title Changed - ID: {topic_id}, New Title: '{new_title}'")
        if self.tree_widget and hasattr(self.tree_widget, 'update_topic_item_title'):
            self.tree_widget.update_topic_item_title(topic_id, new_title)
        else:
            logger.warning("Tree widget not available for UI update on topic_title_changed.")
        # If the currently edited topic's title changed, update editor's state if necessary
        # (though title is usually not directly displayed in editor_widget itself for modification)

    def _on_dm_topic_content_saved(self, topic_id: str):
        logger.info(f"DM SIGNAL: Topic Content Saved - ID: {topic_id}")
        if self.editor_widget.current_topic_id == topic_id:
            self.editor_widget.mark_as_saved() # Update dirty status
            # Optionally, reload content if there's a chance it was modified externally
            # or if the save process itself normalizes content that should be re-shown.
            # For now, mark_as_saved is the primary action.

    def _on_dm_topic_deleted(self, deleted_topic_id: str, old_parent_id: str):
        logger.info(f"DM SIGNAL: Topic Deleted - ID: {deleted_topic_id}, Old Parent: {old_parent_id}")
        if self.editor_widget.current_topic_id == deleted_topic_id:
            self.editor_widget.clear_content() # Clear editor if current topic deleted
            self.editor_widget.current_topic_id = None # Reset current topic id

        if self.tree_widget and hasattr(self.tree_widget, 'remove_topic_item'):
            self.tree_widget.remove_topic_item(deleted_topic_id)
        else:
            logger.warning("Tree widget not available for UI update on topic_deleted.")
        
        # If the deleted topic was a child of the currently open topic in the editor,
        # the parent topic's highlights might need refreshing (if it had extractions to the deleted child)
        # This is a more complex scenario; for now, we rely on _apply_existing_highlights
        # being called when a topic is loaded or an extraction is made/deleted directly affecting it.
        # A simpler approach for now: if the editor shows the parent of the deleted topic, refresh its highlights.
        if self.editor_widget.current_topic_id == old_parent_id:
             if hasattr(self.editor_widget, '_apply_existing_highlights') and self.data_manager:
                self.editor_widget._apply_existing_highlights(self.data_manager)


    def _on_dm_extraction_created(self, extraction_id: str, parent_topic_id: str, child_topic_id: str, start_char: int, end_char: int):
        logger.info(f"DM SIGNAL: Extraction Created - ID: {extraction_id} for Parent: {parent_topic_id}")
        # The child topic itself is handled by _on_dm_topic_created.
        # Here, we primarily care about updating the parent topic's view if it's currently open.
        if self.editor_widget.current_topic_id == parent_topic_id:
            if hasattr(self.editor_widget, '_apply_existing_highlights') and self.data_manager:
                self.editor_widget._apply_existing_highlights(self.data_manager)
            # Or, more targeted: self.editor_widget.apply_extraction_highlight(start_char, end_char)
            # but _apply_existing_highlights is safer as it rebuilds all.
        else:
            logger.warning("Editor widget not showing parent of new extraction, or highlight method missing.")

    def _on_dm_extraction_deleted(self, extraction_id: str, parent_topic_id: str):
        logger.info(f"DM SIGNAL: Extraction Deleted - ID: {extraction_id} from Parent: {parent_topic_id}")
        # If the parent topic whose extraction was removed is currently in the editor, refresh its highlights.
        if self.editor_widget.current_topic_id == parent_topic_id:
            if hasattr(self.editor_widget, '_apply_existing_highlights') and self.data_manager:
                self.editor_widget._apply_existing_highlights(self.data_manager)
        else:
            logger.warning("Editor widget not showing parent of deleted extraction, or highlight method missing.")

    def _on_dm_topic_moved(self, topic_id: str, new_parent_id: str, old_parent_id: str, new_display_order: int):
        logger.info(f"DM SIGNAL: Topic Moved - ID: {topic_id} to Parent: {new_parent_id}")
        if self.tree_widget and hasattr(self.tree_widget, 'move_topic_item'):
            self.tree_widget.move_topic_item(
                topic_id=topic_id,
                new_parent_id=new_parent_id,
                # The tree widget might need to re-fetch children of old_parent_id and new_parent_id
                # or have a more sophisticated move_topic_item that handles reordering.
                # For now, we assume it can handle this or will be reloaded by data_changed_bulk if necessary.
                new_display_order=new_display_order # Pass this along
            )
        else:
            logger.warning("Tree widget not available for UI update on topic_moved.")
        # If the moved topic was open in the editor, its context (parent) changed.
        # No direct editor update needed unless it affects breadcrumbs or similar.

    def _on_dm_data_changed_bulk(self):
        """Handles a signal indicating a larger, non-specific change, often requiring a full UI refresh."""
        logger.info("DM SIGNAL: Bulk Data Change. Reloading tree data.")
        if self.data_manager and self.tree_widget:
            self.tree_widget.load_tree_data(self.data_manager)
            # Current topic in editor might become invalid or its content stale.
            # Consider reloading or clearing it.
            current_editor_topic = self.editor_widget.current_topic_id
            if current_editor_topic:
                # Check if topic still exists
                if self.data_manager.get_topic_details(current_editor_topic):
                    self.editor_widget.load_topic_content(current_editor_topic, self.data_manager)
                else:
                    self.editor_widget.clear_content()
                    self.editor_widget.current_topic_id = None
            else:
                self.editor_widget.clear_content()


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