import sys
import os
import json
import logging
from PyQt6.QtWidgets import (QMainWindow, QApplication, QToolBar, QLabel,
                             QSplitter, QVBoxLayout, QWidget, QFileDialog, QMessageBox)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QSettings

from .knowledge_tree_widget import KnowledgeTreeWidget
from .topic_editor_widget import TopicEditorWidget
from .data_manager import DataManager, DB_FILENAME, TEXT_FILES_SUBDIR # Import DataManager class

logger = logging.getLogger(__name__)
APP_ORGANIZATION_NAME = "IromoOrg" # For QSettings
APP_NAME = "Iromo" # For QSettings
COLLECTION_MANIFEST_FILE = "iromo_collection.json"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.data_manager = None
        self.active_collection_path = None

        self.setWindowTitle(f"{APP_NAME} - No Collection Open")
        self.setGeometry(100, 100, 1024, 768)

        self._create_menu_bar()
        self._create_tool_bar()
        self._setup_central_widget()
        self._connect_signals()
        
        self._update_ui_for_collection_state() # Initial UI state
        self._try_load_last_collection()

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
        # self.new_topic_action.triggered.connect(self.new_topic_handler) # Placeholder
        file_menu.addAction(self.new_topic_action)

        self.save_content_action = QAction("&Save Content", self)
        self.save_content_action.triggered.connect(self.save_current_topic_content)
        file_menu.addAction(self.save_content_action)
        
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close) # QMainWindow.close
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
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

    def _update_ui_for_collection_state(self):
        collection_open = self.data_manager is not None
        
        self.close_collection_action.setEnabled(collection_open)
        self.new_topic_action.setEnabled(collection_open)
        self.save_content_action.setEnabled(collection_open)
        self.save_content_action_toolbar.setEnabled(collection_open)
        self.extract_action_toolbar.setEnabled(collection_open)

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
        self._update_ui_for_collection_state()


    # --- Signal Handlers ---
    def handle_topic_selected(self, topic_id):
        if not self.data_manager:
            logger.warning("handle_topic_selected called but no collection is open.")
            return

        logger.info(f"Topic selected - ID: {topic_id}")
        if self.editor_widget.current_topic_id and self.editor_widget.current_topic_id != topic_id:
            logger.info(f"Saving content for {self.editor_widget.current_topic_id} before switching to {topic_id}.")
            self.save_current_topic_content(prompt_if_no_topic=False)
        
        # Pass data_manager to load_topic_content
        self.editor_widget.load_topic_content(topic_id, self.data_manager) # Assumes method signature updated

    def handle_topic_title_changed(self, topic_id, new_title):
        if not self.data_manager:
            logger.warning("handle_topic_title_changed called but no collection is open.")
            return

        logger.info(f"Topic title changed - ID: {topic_id}, New Title: '{new_title}'")
        success = self.data_manager.update_topic_title(topic_id, new_title)
        if not success:
            logger.error(f"Error persisting title change for {topic_id} to '{new_title}'")
            # Optionally, show an error to the user or revert in tree
            
    def save_current_topic_content(self, prompt_if_no_topic=True):
        if not self.data_manager:
            if prompt_if_no_topic:
                logger.info("No collection open. Cannot save content.")
                QMessageBox.information(self, "Save Content", "No collection is open to save content to.")
            return

        current_editor_topic_id = self.editor_widget.current_topic_id
        if current_editor_topic_id:
            content = self.editor_widget.get_current_content()
            success = self.data_manager.save_topic_content(current_editor_topic_id, content)
            if success:
                logger.info(f"Content for topic {current_editor_topic_id} saved successfully.")
            else:
                logger.error(f"Failed to save content for topic {current_editor_topic_id}.")
                QMessageBox.warning(self, "Save Error", f"Could not save content for topic {current_editor_topic_id}.")
        elif prompt_if_no_topic:
            logger.info("No topic loaded in the editor to save.")
            QMessageBox.information(self, "Save Content", "No topic is currently loaded in the editor.")
            
    def extract_text(self):
        if not self.data_manager:
            logger.warning("Extract text called but no collection is open.")
            QMessageBox.information(self, "Extract Text", "No collection is open to extract text into.")
            return

        current_parent_topic_id = self.editor_widget.current_topic_id
        if not current_parent_topic_id:
            logger.warning("No parent topic selected/loaded in editor to extract from.")
            QMessageBox.information(self, "Extract Text", "Please select a topic to extract from.")
            return

        selected_text, start_char, end_char = self.editor_widget.get_selected_text_and_offsets()
        if not selected_text:
            logger.info("No text selected to extract.")
            QMessageBox.information(self, "Extract Text", "Please select text to extract.")
            return

        logger.info(f"Attempting to extract: '{selected_text}' from parent {current_parent_topic_id} (chars {start_char}-{end_char})")
        self.save_current_topic_content(prompt_if_no_topic=False)

        child_topic_id = self.data_manager.create_topic(text_content=selected_text, parent_id=current_parent_topic_id)
        if not child_topic_id:
            logger.error("Failed to create child topic for extraction.")
            QMessageBox.critical(self, "Extraction Error", "Could not create the new topic for extraction.")
            return
        
        # Use _generate_initial_title from the data_manager instance
        child_topic_title = self.data_manager._generate_initial_title(selected_text) 

        extraction_id = self.data_manager.create_extraction(
            parent_topic_id=current_parent_topic_id,
            child_topic_id=child_topic_id,
            start_char=start_char,
            end_char=end_char
        )
        if not extraction_id:
            logger.error("Failed to record extraction in database.")
            QMessageBox.critical(self, "Extraction Error", "Could not record the extraction link in the database.")
            # Consider deleting the orphaned child_topic_id here
            return

        self.tree_widget.add_topic_item(title=child_topic_title, topic_id=child_topic_id, parent_id=current_parent_topic_id) # Assumes method exists
        self.editor_widget._apply_existing_highlights(self.data_manager) # Assumes method signature updated

        logger.info(f"Extraction successful: New topic '{child_topic_id}' created and linked.")

    def closeEvent(self, event):
        # Override QMainWindow's closeEvent to handle unsaved changes or other cleanup
        if self.data_manager:
            # Example: Prompt to save changes if any widget is "dirty"
            # reply = QMessageBox.question(self, 'Message',
            #                              "Are you sure you want to quit? Any unsaved changes will be lost.",
            #                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            #                              QMessageBox.StandardButton.No)
            # if reply == QMessageBox.StandardButton.Yes:
            #     self._handle_close_collection() # Ensure collection state is saved if needed
            #     event.accept()
            # else:
            #     event.ignore()
            # For now, just close the collection cleanly
            self._handle_close_collection() 
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