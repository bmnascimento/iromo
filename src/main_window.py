import json
import logging
import os
import sys

from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from .commands.topic_commands import (
    ChangeTopicTitleCommand,
    CreateTopicCommand,
    ExtractTextCommand,
)
from .data_manager import DB_FILENAME, TEXT_FILES_SUBDIR, DataManager
from .knowledge_tree_widget import KnowledgeTreeWidget
from .topic_editor_widget import TopicEditorWidget
from .undo_manager import UndoManager
from .settings_dialog import SettingsDialog
from .logger_config import setup_logging # For log level changes
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
        self.actions_map = {} # For managing QActions and their shortcuts

        self.setWindowTitle(f"{APP_NAME} - No Collection Open")
        self.setGeometry(100, 100, 1024, 768)

        self._create_menu_bar() # Populates self.actions_map with initial QActions and default shortcuts
        self._create_tool_bar() # Adds to self.actions_map
        self._setup_central_widget()
        self._connect_signals() # UndoManager signals connected here
        self.autosave_timer = QTimer(self) # For autosave functionality
        
        self._update_ui_for_collection_state() # Initial UI state (enables/disables actions)
        self.undo_manager._update_signals() # Ensure initial state of undo/redo actions
        self._apply_initial_settings() # Apply settings on startup
        self._try_load_last_collection() # This might load a DM and trigger shortcut updates via _open_collection
        
        # If no collection is loaded by _try_load_last_collection,
        # the shortcuts remain as set in _create_menu_bar and _create_tool_bar.
        # If a collection is loaded, _open_collection calls _update_all_action_shortcuts
        # which will then apply DM-managed shortcuts.
        self.undo_manager.command_executed.connect(self._handle_command_executed)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        new_collection_action = QAction("&New Collection...", self)
        new_collection_action.triggered.connect(self._handle_new_collection)
        new_collection_action.setShortcut(QKeySequence("Ctrl+Shift+N")) # Initial default
        file_menu.addAction(new_collection_action)
        self.actions_map["file.new_collection"] = new_collection_action

        open_collection_action = QAction("&Open Collection...", self)
        open_collection_action.triggered.connect(self._handle_open_collection)
        open_collection_action.setShortcut(QKeySequence("Ctrl+O")) # Initial default
        file_menu.addAction(open_collection_action)
        self.actions_map["file.open_collection"] = open_collection_action

        self.close_collection_action = QAction("&Close Collection", self)
        self.close_collection_action.triggered.connect(self._handle_close_collection)
        self.close_collection_action.setShortcut(QKeySequence("Ctrl+Shift+W")) # Initial default
        file_menu.addAction(self.close_collection_action)
        self.actions_map["file.close_collection"] = self.close_collection_action
        
        file_menu.addSeparator()

        self.new_topic_action = QAction("&New Topic", self)
        self.new_topic_action.triggered.connect(self._handle_new_topic_action)
        self.new_topic_action.setShortcut(QKeySequence("Ctrl+N")) # Initial default
        file_menu.addAction(self.new_topic_action)
        self.actions_map["file.new_topic"] = self.new_topic_action
        
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) # QMainWindow.close
        exit_action.setShortcut(QKeySequence("Ctrl+Q")) # Initial default
        file_menu.addAction(exit_action)
        self.actions_map["app.quit"] = exit_action

        edit_menu = menu_bar.addMenu("&Edit")

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo) # Default, will be managed by DM
        self.undo_action.triggered.connect(self.undo_manager.undo)
        edit_menu.addAction(self.undo_action)
        self.actions_map["edit.undo"] = self.undo_action

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo) # Default, will be managed by DM
        self.redo_action.triggered.connect(self.undo_manager.redo)
        edit_menu.addAction(self.redo_action)
        self.actions_map["edit.redo"] = self.redo_action

        edit_menu.addSeparator()
        
        self.preferences_action = QAction("Preferences...", self) # Made it self.
        if sys.platform == "darwin":
            self.preferences_action.setMenuRole(QAction.MenuRole.PreferencesRole)
            edit_menu.addAction(self.preferences_action) # Keep in Edit for consistency for now
        else: # Windows/Linux
            edit_menu.addAction(self.preferences_action)
        self.preferences_action.triggered.connect(self.open_settings_dialog)
        self.preferences_action.setShortcut(QKeySequence("Ctrl+,")) # Initial default
        self.actions_map["app.preferences"] = self.preferences_action
        
        view_menu = menu_bar.addMenu("&View")
        # Example for a view action if it were to be added:
        # self.toggle_tree_action = QAction("Toggle Knowledge Tree", self)
        # self.toggle_tree_action.setShortcut(QKeySequence("Ctrl+T")) # Initial default
        # view_menu.addAction(self.toggle_tree_action)
        # self.actions_map["view.toggle_knowledge_tree"] = self.toggle_tree_action


        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.setShortcut(QKeySequence("F1")) # Initial default
        help_menu.addAction(about_action)
        self.actions_map["help.about"] = about_action

    def _create_tool_bar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        self.extract_action_toolbar = QAction("Extract", self) # Name updated for consistency
        self.extract_action_toolbar.triggered.connect(self.extract_text)
        # Initial shortcut set here, will be managed by _update_all_action_shortcuts
        self.extract_action_toolbar.setShortcut(QKeySequence("Alt+X"))
        self.addAction(self.extract_action_toolbar)
        toolbar.addAction(self.extract_action_toolbar)
        self.actions_map["edit.extract_text"] = self.extract_action_toolbar

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
        self.editor_widget.dirty_changed.connect(self._update_window_title) # Connect dirty status to title update

        # Connect UndoManager signals
        self.undo_manager.can_undo_changed.connect(self.undo_action.setEnabled)
        self.undo_manager.can_redo_changed.connect(self.redo_action.setEnabled)
        self.undo_manager.undo_text_changed.connect(self.undo_action.setText)
        self.undo_manager.redo_text_changed.connect(self.redo_action.setText)

    def _update_window_title(self):
        title_parts = [APP_NAME]
        is_dirty = self.editor_widget.is_dirty() if self.editor_widget else False
        current_editor_topic_id = self.editor_widget.current_topic_id if self.editor_widget else None

        if self.active_collection_path and self.data_manager:
            collection_name = os.path.basename(self.active_collection_path)
            title_parts.append(collection_name)
            
            if current_editor_topic_id:
                details = self.data_manager.get_topic_details(current_editor_topic_id)
                if details and details.get('title'):
                    title_parts.append(details['title'])
                elif details: # Topic exists but maybe title is empty or None
                    title_parts.append("Editing Topic")
                # If details is None, means topic_id is invalid or not found, title remains collection level
        else:
            title_parts.append("No Collection Open")
        
        final_title = " - ".join(title_parts)
        if is_dirty and current_editor_topic_id: # Only show dirty if a topic is actually loaded and dirty
            final_title += " *"
        
        self.setWindowTitle(final_title)

    def _update_ui_for_collection_state(self):
        collection_open = self.data_manager is not None
        
        # Actions that require a collection to be open
        if hasattr(self, 'close_collection_action'): # Ensure actions are created
            self.close_collection_action.setEnabled(collection_open)
        if hasattr(self, 'new_topic_action'):
            self.new_topic_action.setEnabled(collection_open)
        if hasattr(self, 'extract_action_toolbar'):
            self.extract_action_toolbar.setEnabled(collection_open)
        if hasattr(self, 'preferences_action'):
            self.preferences_action.setEnabled(collection_open) # SettingsDialog now requires DataManager

        # Undo/Redo are enabled/disabled by UndoManager's signals directly,
        # but also depend on collection state for initial setup.
        if hasattr(self, 'undo_action'): # Check if undo_action exists
            self.undo_action.setEnabled(collection_open and self.undo_manager.can_undo())
        if hasattr(self, 'redo_action'): # Check if redo_action exists
            self.redo_action.setEnabled(collection_open and self.undo_manager.can_redo())
        
        if not collection_open:
            self.tree_widget.clear_tree()
            if self.editor_widget: # Ensure editor widget exists before clearing
                self.editor_widget.clear_content()

        self._update_window_title() # Centralized title update
            
    def _save_last_collection_path(self, path):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        if path:
            settings.setValue("last_opened_collection", path)
        else:
            settings.remove("last_opened_collection")

    def _try_load_last_collection(self):
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)
        last_path = settings.value("last_opened_collection")

        if not last_path:
            logger.info("No last opened collection path found in settings.")
            return

        if not os.path.isdir(last_path):
            logger.warning(
                f"Last opened collection path '{last_path}' is not a valid directory. "
                "Clearing setting."
            )
            self._save_last_collection_path(None) # Clear invalid path
            return

        manifest_path = os.path.join(last_path, COLLECTION_MANIFEST_FILE)
        if not os.path.exists(manifest_path):
            logger.warning(
                f"Last opened collection path '{last_path}' does not contain a manifest file "
                f"'{COLLECTION_MANIFEST_FILE}'. Clearing setting."
            )
            self._save_last_collection_path(None) # Clear invalid path
            return
        
        logger.info(f"Attempting to auto-load last opened collection: {last_path}")
        self._open_collection(last_path)
        # _open_collection handles its own errors, including logging and user messages.
        # If it fails, data_manager will be None, and UI will reflect no collection open.

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
            self.data_manager.shortcuts_changed.connect(self._update_all_action_shortcuts)


            # Load data into UI
            self.tree_widget.load_tree_data(self.data_manager)
            self.editor_widget.clear_content()
            self.undo_manager.clear_stacks()
            
            self._update_all_action_shortcuts() # Apply shortcuts for this collection

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
                    self.data_manager.shortcuts_changed.disconnect(self._update_all_action_shortcuts)
                except TypeError: # Signals might not be connected if DM init failed early
                    pass
            self.data_manager = None
            self.active_collection_path = None
        
        self._update_ui_for_collection_state()

    def _handle_close_collection(self):
        if not self.data_manager:
            return

        logger.info(f"Closing collection: {self.active_collection_path}")
        # Ensure current topic is saved if dirty
        if self.editor_widget and self.editor_widget.current_topic_id and self.editor_widget.is_dirty():
            logger.info(f"Collection close: Forcing save for dirty topic {self.editor_widget.current_topic_id}.")
            self.editor_widget.force_save_if_dirty(wait_for_completion=True) # Wait for save to finish

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
                self.data_manager.shortcuts_changed.disconnect(self._update_all_action_shortcuts)
            except TypeError:
                logger.warning("Error disconnecting DataManager signals during close, possibly already disconnected or never connected.")
                pass


        self.data_manager = None
        self.active_collection_path = None
        self._save_last_collection_path(None) # Clear last opened path
        self.undo_manager.clear_stacks()
        self._update_ui_for_collection_state()
        # Shortcuts will remain as they were from the last collection.
        # Or, if we want to revert to app defaults: self._update_all_action_shortcuts()
        # but this method currently does nothing if self.data_manager is None.
        # For now, they persist, which is acceptable.


    # --- Shortcut Management ---

    def _update_all_action_shortcuts(self):
        if not self.data_manager:
            # This means initial app state shortcuts (hardcoded or StandardKey) remain.
            # When a DM becomes active, they will be updated.
            logger.debug("_update_all_action_shortcuts: No DataManager, skipping dynamic update from DM.")
            return

        logger.info("Updating all action shortcuts from DataManager...")
        for action_id, action in self.actions_map.items():
            if not action:
                logger.warning(f"No action found for action_id '{action_id}' in actions_map.")
                continue

            shortcut_str = self.data_manager.get_shortcut(action_id)
            # get_shortcut returns custom, then default from DM's self.default_shortcuts,
            # then None if action_id is not in DM's defaults.
            
            target_sequence = QKeySequence(shortcut_str if shortcut_str is not None else "")

            if action.shortcut() != target_sequence:
                logger.info(f"Setting shortcut for '{action_id}': '{target_sequence.toString()}' (was: '{action.shortcut().toString()}')")
                action.setShortcut(target_sequence)
            # else:
                # logger.debug(f"Shortcut for '{action_id}' is already '{target_sequence.toString()}'. No change.")

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
            custom_title=None, # Use default timestamp placeholder
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

        # Before switching, ensure current topic is saved if dirty.
        if self.editor_widget.current_topic_id and \
           self.editor_widget.current_topic_id != topic_id and \
           self.editor_widget.is_dirty():
            logger.info(f"Switching topic: Forcing save for dirty topic {self.editor_widget.current_topic_id}.")
            self.editor_widget.force_save_if_dirty(wait_for_completion=True) # Wait for save to finish

        # Pass data_manager to load_topic_content
        self.editor_widget.load_topic_content(topic_id, self.data_manager)
        # The editor_widget.dirty_changed signal (emitted as False when new topic loads clean)
        # will call _update_window_title.

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
            
    # def save_current_topic_content(self, prompt_if_no_topic=True): # Manual save removed
    #     if not self.data_manager or not self.editor_widget.current_topic_id:
    #         if prompt_if_no_topic:
    #             QMessageBox.information(self, "Save Content", "No topic loaded or collection open.")
    #         return

    #     if not self.editor_widget.is_dirty() and prompt_if_no_topic:
    #         logger.info(f"Content for topic {self.editor_widget.current_topic_id} is not modified. Save not required.")
    #         return

    #     topic_id = self.editor_widget.current_topic_id
    #     new_content = self.editor_widget.get_current_content()
    #     old_content = self.editor_widget.original_content
        
    #     topic_details = self.data_manager.get_topic_details(topic_id)
    #     topic_title = topic_details['title'] if topic_details else topic_id

    #     cmd = SaveTopicContentCommand(
    #         data_manager=self.data_manager,
    #         topic_id=topic_id,
    #         old_content=old_content,
    #         new_content=new_content,
    #         topic_title=topic_title
    #     )
    #     try:
    #         self.undo_manager.execute_command(cmd)
    #     except Exception as e:
    #         logger.error(f"Error executing Save Content command for topic {topic_id}: {e}", exc_info=True)
    #         QMessageBox.critical(self, "Save Error", f"Could not save content for topic {topic_id}: {e}")
            
    def extract_text(self):
        if not self.data_manager or not self.editor_widget.current_topic_id:
            QMessageBox.information(self, "Extract Text", "No topic loaded or collection open to extract from.")
            return

        parent_topic_id = self.editor_widget.current_topic_id
        selected_text, start_char, end_char = self.editor_widget.get_selected_text_and_offsets()

        if not selected_text:
            QMessageBox.information(self, "Extract Text", "Please select text to extract.")
            return

        # If the current editor content is dirty or an auto-save is pending, force save it.
        # Extraction modifies the parent (by adding a highlight), so it's good practice
        # to ensure the state being highlighted is the saved state.
        if self.editor_widget.is_dirty():
            logger.info(f"Extract text: Forcing save for parent topic {parent_topic_id} due to dirty state.")
            self.editor_widget.force_save_if_dirty(wait_for_completion=True)
            if self.editor_widget.is_dirty(): # If save failed
                 QMessageBox.warning(self, "Extract Text", "Failed to save the current topic. Extraction aborted.")
                 return
        
        logger.info(f"Attempting to extract: '{selected_text}' from parent {parent_topic_id} (chars {start_char}-{end_char})")
        
        # Generate title from selected text
        custom_child_title = None
        if selected_text:
            first_50_chars = selected_text[:50]
            newline_index = first_50_chars.find('\n')
            if newline_index != -1:
                candidate_title = first_50_chars[:newline_index]
            else:
                candidate_title = first_50_chars
            
            candidate_title = candidate_title.strip()
            if candidate_title: # Only use if not empty after stripping
                custom_child_title = candidate_title
            # If candidate_title is empty, custom_child_title remains None,
            # and DataManager will use the timestamp placeholder.

        cmd = ExtractTextCommand(
            data_manager=self.data_manager,
            parent_topic_id=parent_topic_id,
            selected_text=selected_text,
            start_char=start_char,
            end_char=end_char,
            custom_child_title=custom_child_title # Pass the generated title
        )
        try:
            self.undo_manager.execute_command(cmd)
            # UI updates (new topic in tree, highlighting in editor) will be handled by DataManager signals
            # Potentially select the new child topic in the tree.
            if cmd.child_topic_id: # Check if command execution was successful and child_topic_id is set
                self.tree_widget.select_topic_item(cmd.child_topic_id)
                self.handle_topic_selected(cmd.child_topic_id) # Load it in editor
        except Exception as e:
            logger.error(f"Error executing Extract Text command: {e}", exc_info=True)
            QMessageBox.critical(self, "Extraction Error", f"Could not extract text: {e}")

    # --- Settings Dialog and Handlers ---

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.data_manager, self)
        # Connect signals from the dialog to MainWindow handlers
        dialog.theme_changed.connect(self.handle_theme_changed)
        dialog.editor_font_changed.connect(self.handle_editor_font_changed)
        dialog.tree_font_changed.connect(self.handle_tree_font_changed)
        dialog.extraction_highlight_color_changed.connect(self.handle_extraction_highlight_color_changed)
        # dialog.default_collection_path_changed.connect(self.handle_default_collection_path_changed) # Not directly applied, but good to know
        dialog.autosave_interval_changed.connect(self.handle_autosave_interval_changed)
        # dialog.recent_collections_count_changed.connect(self.handle_recent_collections_count_changed) # UI for this is in File menu, not directly applied here
        # dialog.default_topic_title_length_changed.connect(self.handle_default_topic_title_length_changed) # Used by DataManager
        # dialog.confirm_topic_deletion_changed.connect(self.handle_confirm_topic_deletion_changed) # Used before delete operations
        # dialog.open_last_collection_on_startup_changed.connect(self.handle_open_last_collection_on_startup_changed) # Affects startup
        # dialog.show_welcome_on_startup_changed.connect(self.handle_show_welcome_on_startup_changed) # Affects startup
        dialog.log_level_changed.connect(self.handle_log_level_changed)

        if dialog.exec(): # User clicked OK
            logger.info("Settings dialog accepted.")
            # Settings are applied via signals or by the dialog's apply_settings method.
            # If any settings need re-application after OK that aren't covered by signals, do it here.
        else:
            logger.info("Settings dialog cancelled.")
            # Optionally, revert any previewed changes if the dialog supported live preview + cancel.
            # For this dialog, Apply or OK saves, Cancel discards.

    def _apply_initial_settings(self):
        logger.info("Applying initial settings...")
        settings = QSettings(APP_ORGANIZATION_NAME, APP_NAME)

        theme = settings.value("ui/theme", "System Default")
        self.handle_theme_changed(theme)

        default_editor_font_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        editor_font_family = settings.value("ui/editor_font_family", default_editor_font_family)
        editor_font_size = settings.value("ui/editor_font_size", 12, type=int)
        self.handle_editor_font_changed(editor_font_family, editor_font_size)

        default_tree_font_family = QApplication.font().family()
        tree_font_family = settings.value("ui/tree_font_family", default_tree_font_family)
        tree_font_size = settings.value("ui/tree_font_size", 10, type=int)
        self.handle_tree_font_changed(tree_font_family, tree_font_size)

        extraction_color = settings.value("ui/extraction_highlight_color", "#ADD8E6")
        self.handle_extraction_highlight_color_changed(extraction_color)

        log_level = settings.value("logging/log_level", "INFO")
        self.handle_log_level_changed(log_level)
        
        autosave_interval_minutes = settings.value("data/autosave_interval_minutes", 5, type=int)
        self.handle_autosave_interval_changed(autosave_interval_minutes)
        
        # Other settings like default_collection_path, recent_collections_count, etc.,
        # are used by specific parts of the application (e.g., file dialogs, startup logic)
        # and don't require direct application to visual components here.
        logger.info("Initial settings applied.")

    def handle_theme_changed(self, theme_name: str):
        logger.info(f"Applying theme: {theme_name}")
        # Placeholder for theme application logic
        # This might involve:
        # - Loading a QSS stylesheet:
        #   with open(f"themes/{theme_name.lower()}.qss", "r") as f:
        #       self.setStyleSheet(f.read())
        # - Or using a library like qt_material:
        #   if theme_name == "Dark":
        #       apply_stylesheet(app, theme='dark_teal.xml')
        #   elif theme_name == "Light":
        #       apply_stylesheet(app, theme='light_blue.xml')
        #   else: # System Default
        #       app.setStyleSheet("") # Clear stylesheet
        # For now, just log.
        if theme_name == "Dark":
            # Example: self.setStyleSheet("QWidget { background-color: #333; color: white; }")
            pass
        elif theme_name == "Light":
            # Example: self.setStyleSheet("QWidget { background-color: #EEE; color: black; }")
            pass
        else: # System Default
            # Example: self.setStyleSheet("")
            pass
        QApplication.instance().setProperty("theme", theme_name) # Store for other components if needed


    def handle_editor_font_changed(self, font_family: str, font_size: int):
        logger.info(f"Applying editor font: {font_family}, {font_size}pt")
        if self.editor_widget and hasattr(self.editor_widget, 'set_font'):
            font = QFont(font_family, font_size)
            self.editor_widget.set_font(font)
        else:
            logger.warning("Editor widget not available or does not support set_font.")

    def handle_tree_font_changed(self, font_family: str, font_size: int):
        logger.info(f"Applying tree view font: {font_family}, {font_size}pt")
        if self.tree_widget and hasattr(self.tree_widget, 'set_font'):
            font = QFont(font_family, font_size)
            self.tree_widget.set_font(font) # Assumes tree_widget has set_font
        else:
            logger.warning("Tree widget not available or does not support set_font.")

    def handle_extraction_highlight_color_changed(self, color_str: str):
        logger.info(f"Applying extraction highlight color: {color_str}")
        if self.editor_widget and hasattr(self.editor_widget, 'set_extraction_highlight_color'):
            self.editor_widget.set_extraction_highlight_color(color_str)
        else:
            logger.warning("Editor widget not available or does not support set_extraction_highlight_color.")
        # This color might also be needed by DataManager or other parts if they render highlights.

    def handle_log_level_changed(self, level_str: str):
        logger.info(f"Updating log level to: {level_str}")
        # Assuming setup_logging can be called again or there's a specific function to update level
        # This might require reconfiguring the root logger or specific application loggers.
        # For a simple case, if setup_logging configures the root logger:
        try:
            # This is a simplified approach. A robust solution might involve
            # getting the root logger and setting its level, or specific handlers.
            log_level_enum = getattr(logging, level_str.upper(), logging.INFO)
            logging.getLogger().setLevel(log_level_enum) # Set root logger level
            # If you have specific handlers, you might need to iterate and set their levels too.
            for handler in logging.getLogger().handlers:
                handler.setLevel(log_level_enum)
            logger.info(f"Log level set to {level_str} in logging module.")
        except Exception as e:
            logger.error(f"Failed to update log level: {e}", exc_info=True)


    def handle_autosave_interval_changed(self, interval_minutes: int):
        logger.info(f"Updating autosave interval to: {interval_minutes} minutes")
        if self.autosave_timer.isActive():
            self.autosave_timer.stop()
        
        if interval_minutes > 0:
            self.autosave_timer.setInterval(interval_minutes * 60 * 1000) # milliseconds
            if not self.autosave_timer.receivers(self.autosave_timer.timeout): # Check if already connected
                self.autosave_timer.timeout.connect(self._perform_autosave)
            self.autosave_timer.start()
            logger.info(f"Autosave timer started with interval {interval_minutes} minutes.")
        else:
            logger.info("Autosave disabled.")

    def _perform_autosave(self):
        if self.data_manager and self.editor_widget and \
           self.editor_widget.current_topic_id and self.editor_widget.is_dirty():
            logger.info(f"Autosaving content for topic: {self.editor_widget.current_topic_id}")
            # Use the force_save_if_dirty method which encapsulates the save logic
            self.editor_widget.force_save_if_dirty(wait_for_completion=False) # Non-blocking for autosave
        else:
            logger.info("Autosave triggered, but no dirty content to save or no topic open.")

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
        
        if self.editor_widget and self.editor_widget.current_topic_id == topic_id:
            self._update_window_title() # Update title as current topic's name changed

    def _on_dm_topic_content_saved(self, topic_id: str):
        logger.info(f"DM SIGNAL: Topic Content Saved - ID: {topic_id}")
        if self.editor_widget.current_topic_id == topic_id:
            self.editor_widget.mark_as_clean() # Update dirty status
            # Optionally, reload content if there's a chance it was modified externally
            # or if the save process itself normalizes content that should be re-shown.
            # For now, mark_as_saved is the primary action.

    def _on_dm_topic_deleted(self, deleted_topic_id: str, old_parent_id: str):
        logger.info(f"DM SIGNAL: Topic Deleted - ID: {deleted_topic_id}, Old Parent: {old_parent_id}")
        if self.editor_widget.current_topic_id == deleted_topic_id:
            self.editor_widget.clear_content() # Clear editor if current topic deleted
            self.editor_widget.current_topic_id = None # Reset current topic id

        if self.tree_widget and hasattr(self.tree_widget, 'remove_topic_item'):
            logger.info(f"_on_dm_topic_deleted: Found remove_topic_item. Calling it for {deleted_topic_id}.")
            self.tree_widget.remove_topic_item(deleted_topic_id)
            logger.info(f"_on_dm_topic_deleted: Returned from remove_topic_item for {deleted_topic_id}.")
        else:
            logger.error(f"_on_dm_topic_deleted: remove_topic_item method NOT FOUND in tree_widget. Tree will NOT be updated for deletion of {deleted_topic_id}. Falling back to full reload.")
            # Fallback to full reload if specific removal isn't available
            if self.tree_widget and self.data_manager:
                logger.info(f"_on_dm_topic_deleted: Attempting fallback: self.tree_widget.load_tree_data for {deleted_topic_id}")
                self.tree_widget.load_tree_data(self.data_manager)
                logger.info(f"_on_dm_topic_deleted: Fallback load_tree_data completed for {deleted_topic_id}")
            else:
                logger.error("_on_dm_topic_deleted: Cannot fallback to load_tree_data, tree_widget or data_manager is None.")
        
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
        logger.info("Application close event triggered.")
        
        # Step 1: Handle unsaved changes in the currently active editor
        # This check needs to be robust: ensure editor_widget and current_topic_id exist.
        if self.data_manager and \
           self.editor_widget and \
           self.editor_widget.current_topic_id and \
           self.editor_widget.is_dirty():
            
            logger.info(f"Application close: Current editor for topic {self.editor_widget.current_topic_id} is dirty. Attempting to save.")
            self.editor_widget.force_save_if_dirty(wait_for_completion=True) # Blocking save
            
            if self.editor_widget.is_dirty(): # Check if save failed
                topic_title_for_msg = self.editor_widget.current_topic_id # Fallback title
                # Try to get a more user-friendly title
                if self.data_manager: # Check if data_manager is still valid
                    details = self.data_manager.get_topic_details(self.editor_widget.current_topic_id)
                    if details and details.get('title'):
                        topic_title_for_msg = details['title']
                
                reply = QMessageBox.warning(
                    self, "Unsaved Changes",
                    f"Could not save changes for topic '{topic_title_for_msg}'.\n"
                    "Do you want to close anyway and lose these changes?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No # Default to No
                )
                if reply == QMessageBox.StandardButton.No:
                    event.ignore() # User chose not to close
                    return
        
        # Step 2: Store the path of the collection that was active *before* _handle_close_collection
        collection_path_at_start_of_close = self.active_collection_path

        # Step 3: Perform standard operations for closing a collection, if one is managed.
        # _handle_close_collection itself calls force_save_if_dirty for the current editor,
        # but the above block is a more explicit primary check for the app closing sequence.
        # _handle_close_collection will also set self.active_collection_path to None
        # and call _save_last_collection_path(None).
        if self.data_manager:
            self._handle_close_collection()

        # Step 4: Determine the final "last_opened_collection" path to persist.
        # If a collection was active when the application started to close (before _handle_close_collection),
        # save its path. This overrides the None potentially set by _handle_close_collection.
        if collection_path_at_start_of_close:
            self._save_last_collection_path(collection_path_at_start_of_close)
        else:
            # If no collection was active at the start of closeEvent, or if _handle_close_collection
            # wasn't called (because no data_manager), ensure the setting is cleared.
            self._save_last_collection_path(None)
            
        # Step 5: Proceed with closing the application
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