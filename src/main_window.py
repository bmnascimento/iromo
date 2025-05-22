import sys
from PyQt6.QtWidgets import (QMainWindow, QApplication, QToolBar, QLabel,
                             QSplitter, QVBoxLayout, QWidget)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from knowledge_tree_widget import KnowledgeTreeWidget
from topic_editor_widget import TopicEditorWidget
import data_manager as dm # For initializing the database
import logging

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Iromo - Incremental Reading")
        self.setGeometry(100, 100, 1024, 768)  # x, y, width, height

        # Initialize database if it's the first run
        dm.initialize_database() # Ensures DB and tables exist
        self._create_test_data_if_needed() # For debugging highlights

        self._create_menu_bar()
        self._create_tool_bar() # Placeholder for the ribbon
        self._setup_central_widget()
        self._connect_signals()

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Topic", self)
        # new_action.triggered.connect(self.new_topic) # Placeholder
        file_menu.addAction(new_action)

        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        save_action = QAction("&Save Content", self)
        save_action.triggered.connect(self.save_current_topic_content)
        # save_action.setShortcut("Ctrl+S") # Add shortcut later if desired
        file_menu.addAction(save_action)

        # Edit Menu (Placeholder)
        edit_menu = menu_bar.addMenu("&Edit")
        # Add edit actions here later

        # View Menu (Placeholder)
        view_menu = menu_bar.addMenu("&View")
        # Add view actions here later

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        # about_action.triggered.connect(self.show_about_dialog) # Placeholder
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        # This will eventually be replaced by a more complex ribbon UI
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Example action
        extract_action = QAction("Extract (Alt+X)", self)
        extract_action.triggered.connect(self.extract_text)
        extract_action.setShortcut("Alt+X")
        self.addAction(extract_action) # Add shortcut to window context
        toolbar.addAction(extract_action)

        save_content_action_toolbar = QAction("Save Content", self)
        save_content_action_toolbar.triggered.connect(self.save_current_topic_content)
        toolbar.addAction(save_content_action_toolbar)


    def _setup_central_widget(self):
        # Main content area will be a splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Knowledge Tree Widget
        self.tree_widget = KnowledgeTreeWidget()
        
        # Topic Editor Widget
        self.editor_widget = TopicEditorWidget()
        
        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.editor_widget)
        
        # Set initial sizes for the splitter panes (e.g., 1/3 for tree, 2/3 for editor)
        self.splitter.setSizes([self.width() // 3, 2 * self.width() // 3])

        self.setCentralWidget(self.splitter)

    def _connect_signals(self):
        self.tree_widget.topic_selected.connect(self.handle_topic_selected)
        self.tree_widget.topic_title_changed.connect(self.handle_topic_title_changed)

    # --- Signal Handlers ---
    def handle_topic_selected(self, topic_id):
        logger.info(f"Topic selected - ID: {topic_id}")
        # Before loading new content, check if current editor content needs saving
        # For now, we'll just load. A "dirty" flag mechanism would be better.
        if self.editor_widget.current_topic_id and self.editor_widget.current_topic_id != topic_id:
            # Potentially prompt to save changes for self.editor_widget.current_topic_id
            # For MVP, we can save automatically or just switch. Let's save current before switching.
            logger.info(f"Saving content for {self.editor_widget.current_topic_id} before switching to {topic_id}.")
            self.save_current_topic_content(prompt_if_no_topic=False)


        self.editor_widget.load_topic_content(topic_id)

    def handle_topic_title_changed(self, topic_id, new_title):
        logger.info(f"Topic title changed - ID: {topic_id}, New Title: '{new_title}'")
        # Persist the change to the database
        success = dm.update_topic_title(topic_id, new_title)
        if not success:
            logger.error(f"Error persisting title change for {topic_id} to '{new_title}'")
            # Optionally, revert the title in the tree or show an error to the user
            # For now, we'll assume the tree widget's display is the source of truth until AppLogic handles this
            # self.tree_widget.update_topic_item_title(topic_id, dm.get_topic_title(topic_id)) # Needs get_topic_title
    
    def save_current_topic_content(self, prompt_if_no_topic=True):
        """Saves the content of the currently active topic in the editor."""
        current_editor_topic_id = self.editor_widget.current_topic_id
        if current_editor_topic_id:
            content = self.editor_widget.get_current_content()
            success = dm.save_topic_content(current_editor_topic_id, content)
            if success:
                logger.info(f"Content for topic {current_editor_topic_id} saved successfully.")
                # Refresh highlights in case new extractions were made and saved with content
                # self.editor_widget._apply_existing_highlights() # Or do this on next load
            else:
                logger.error(f"Failed to save content for topic {current_editor_topic_id}.")
                # Optionally, show an error message to the user
        elif prompt_if_no_topic:
            logger.info("No topic loaded in the editor to save.")
            # Optionally, show a message to the user (e.g., in status bar)


    # --- Placeholder Action Handlers from Menu/Toolbar ---
    # def new_topic(self): pass
    # def show_about_dialog(self): pass
    
    def extract_text(self):
        """Handles the text extraction action."""
        current_parent_topic_id = self.editor_widget.current_topic_id
        if not current_parent_topic_id:
            logger.warning("No parent topic selected/loaded in editor to extract from.")
            # Optionally: show a status message to the user
            return

        selected_text, start_char, end_char = self.editor_widget.get_selected_text_and_offsets()

        if not selected_text:
            logger.info("No text selected to extract.")
            # Optionally: show a status message to the user
            return

        logger.info(f"Attempting to extract: '{selected_text}' from parent {current_parent_topic_id} (chars {start_char}-{end_char})")

        # 1. Save current parent topic content FIRST, as offsets depend on current state
        #    If content hasn't changed, this is quick. If it has, it ensures consistency.
        self.save_current_topic_content(prompt_if_no_topic=False) # Don't prompt if no topic, already checked

        # 2. Create the new child topic with the extracted text
        #    The title will be auto-generated by create_topic from selected_text
        child_topic_id = dm.create_topic(text_content=selected_text, parent_id=current_parent_topic_id)

        if not child_topic_id:
            logger.error("Failed to create child topic for extraction.")
            # Optionally: show an error message
            return
        
        child_topic_title = dm._generate_initial_title(selected_text) # Get the title it would have generated

        # 3. Record the extraction
        extraction_id = dm.create_extraction(
            parent_topic_id=current_parent_topic_id,
            child_topic_id=child_topic_id,
            start_char=start_char,
            end_char=end_char
        )

        if not extraction_id:
            logger.error("Failed to record extraction in database.")
            # Potentially: delete the orphaned child_topic_id if critical
            # dm.delete_topic(child_topic_id) # Would need delete_topic
            # Optionally: show an error message
            return

        # 4. Refresh the KnowledgeTreeWidget to show the new child topic
        self.tree_widget.add_topic_item(title=child_topic_title, topic_id=child_topic_id, parent_id=current_parent_topic_id)
        
        # 5. Re-apply highlighting in the TopicEditorWidget for the parent topic
        #    This will pick up the new extraction along with any old ones.
        #    Alternatively, just highlight the new one:
        #    self.editor_widget.apply_extraction_highlight(start_char, end_char)
        #    But reloading all ensures consistency if other changes occurred.
        self.editor_widget._apply_existing_highlights() # Reloads all for current topic

        logger.info(f"Extraction successful: New topic '{child_topic_id}' created and linked.")
        # Optionally: select the new child topic in the tree and editor
        # self.tree_widget.setCurrentIndex(self.tree_widget._topic_item_map[child_topic_id].index())
        # self.handle_topic_selected(child_topic_id)


    def _create_test_data_if_needed(self):
        """Creates a specific topic and extraction for testing if it doesn't exist."""
        # Check if our specific test parent topic exists by title
        # This is a simplification; a more robust check might use a known ID or a flag.
        hierarchy = dm.get_topic_hierarchy()
        test_parent_title = "Test Parent For Highlight"
        test_parent_id = None
        test_child_id = None # To store the ID of the extracted child

        # First, find if the parent topic exists
        for topic in hierarchy:
            if topic['title'] == test_parent_title:
                test_parent_id = topic['id']
                break # Found parent

        # If parent exists, check if the specific extraction (child) also exists
        if test_parent_id:
            for topic in hierarchy: # Iterate again to find child by parent_id and title
                if topic['parent_id'] == test_parent_id and topic['title'] == "Extracted Part":
                    test_child_id = topic['id']
                    # Now also check if an extraction record links them
                    extractions = dm.get_extractions_for_parent(test_parent_id)
                    for extr in extractions:
                        if extr['child_topic_id'] == test_child_id:
                            logger.info(f"Test data '{test_parent_title}' and its extraction record already exist.")
                            # Optionally, print FileUUID for debugging
                            # topic_details = dm.get_topic_details(test_parent_id) # Would need this function
                            # if topic_details: logger.debug(f"FileUUID for {test_parent_id} is {topic_details['text_file_uuid']}")
                            return # Test data fully exists
                    break # Found child by title, but maybe not extraction record

        if test_parent_id and test_child_id:
            # Parent and child topics exist by title, but maybe not the extraction record.
            # This case could be refined, but for now, if titles match, assume it's mostly there.
            # Or, we could decide to recreate the extraction if missing.
            # For simplicity, if both topics are found by title, we'll assume it's okay.
            # A more robust check would verify the extraction record specifically.
            logger.info(f"Test parent '{test_parent_title}' and child 'Extracted Part' topics exist. Assuming extraction record is also present or will be tested by UI.")
            return


        logger.info(f"Creating test data: '{test_parent_title}' with an extraction...")
        parent_content = "This is some initial text. The part to extract is HERE. And some trailing text."
        # String: "This is some initial text. The part to extract is HERE. And some trailing text."
        # Indices:  0123456789012345678901234567890123456789012345678901234567890123456789
        # "HERE" is at index 28, 29, 30, 31. Length is 4.
        # Start char: 28, End char: 31 (inclusive)
        
        new_parent_id = dm.create_topic(text_content=parent_content, custom_title=test_parent_title)
        if not new_parent_id:
            logger.error("Failed to create test parent topic.")
            return

        # The FileUUID is printed by create_topic's modified log
        logger.info(f"PARENT_TOPIC_CREATED: Title='{test_parent_title}', ID='{new_parent_id}'. Note its FileUUID from previous log.")

        extracted_text_content = "HERE"
        new_child_id = dm.create_topic(text_content=extracted_text_content, parent_id=new_parent_id, custom_title="Extracted Part")
        if not new_child_id:
            logger.error("Failed to create test child topic.")
            return
            
        start_char = parent_content.find(extracted_text_content)
        end_char = start_char + len(extracted_text_content) - 1 # Inclusive end

        if start_char != -1:
            extraction_record_id = dm.create_extraction(new_parent_id, new_child_id, start_char, end_char)
            if extraction_record_id:
                logger.info(f"Test extraction record created: ID={extraction_record_id}, Parent={new_parent_id}, Child={new_child_id}, Start={start_char}, End={end_char}")
            else:
                logger.error("Failed to create test extraction record.")
        else: # Should not happen with the hardcoded string
            logger.error(f"Could not find '{extracted_text_content}' in parent content to create test extraction.")


if __name__ == '__main__':
    # This part is for testing the MainWindow independently if needed
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec())