from PyQt6.QtWidgets import QTextEdit, QApplication
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter, QFont
from PyQt6.QtCore import Qt, pyqtSignal
import logging
import os # For __main__ test
import shutil # For __main__ test cleanup

from .data_manager import DataManager # Import the DataManager class

logger = logging.getLogger(__name__)

class TopicEditorWidget(QTextEdit):
    content_changed_externally = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_topic_id = None
        self.setFont(QFont("Arial", 12))
        self.setAcceptRichText(True)
        self.setPlaceholderText("No collection open or no topic selected.")


    def _get_document_text_for_logging(self):
        doc = self.document()
        text = doc.toPlainText()
        return text.replace('\n', '\\n')[:100]

    def load_topic_content(self, topic_id: str, data_manager_instance: DataManager):
        """Loads and displays the content for the given topic_id using the provided DataManager."""
        logger.info(f"Loading content for topic_id: {topic_id}")
        self.clear_content() # Clear previous content and highlights, sets placeholder

        if not data_manager_instance:
            logger.warning("load_topic_content called with no DataManager instance.")
            self.setPlaceholderText(f"Error: Data manager not available for topic {topic_id}.")
            return

        content = data_manager_instance.get_topic_content(topic_id)
        if content is not None:
            self.current_topic_id = topic_id
            self.setPlainText(content)
            logger.debug(f"After setPlainText for {topic_id}. Doc text: '{self._get_document_text_for_logging()}'")

            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            default_format = QTextCharFormat()
            cursor.setCharFormat(default_format)
            cursor.clearSelection()
            self.setTextCursor(cursor)
            logger.debug(f"Applied default char format to entire document for topic {topic_id}.")

            self._apply_existing_highlights(data_manager_instance)
        else:
            self.current_topic_id = None # Ensure this is reset
            self.setPlaceholderText(f"Could not load content for topic {topic_id}.")
            logger.warning(f"Content for topic_id {topic_id} was None.")

    def _apply_existing_highlights(self, data_manager_instance: DataManager):
        """Applies highlights for all extractions using the provided DataManager."""
        logger.debug(f"Applying existing highlights for topic {self.current_topic_id}")
        if not self.current_topic_id or not data_manager_instance:
            logger.debug("No current_topic_id or no DataManager, returning from _apply_existing_highlights.")
            return
        
        extractions = data_manager_instance.get_extractions_for_parent(self.current_topic_id)
        logger.debug(f"Found {len(extractions)} extractions for topic {self.current_topic_id}: {extractions}")
        for i, extr in enumerate(extractions):
            start_char = extr['parent_text_start_char']
            end_char = extr['parent_text_end_char']
            logger.debug(f"Applying highlight {i+1}/{len(extractions)}: start={start_char}, end={end_char}")
            self.apply_extraction_highlight(start_char, end_char)

    def get_current_content(self):
        return self.toPlainText()

    def get_selected_text_and_offsets(self):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return None, -1, -1
        
        selected_text = cursor.selectedText()
        start_offset = cursor.selectionStart()
        end_offset = cursor.selectionEnd()
        
        return selected_text, start_offset, end_offset - 1

    def apply_extraction_highlight(self, start_char, end_char, color=QColor("lightblue")):
        doc_text_before_highlight = self._get_document_text_for_logging()
        doc_len = len(self.toPlainText())
        logger.debug(f"apply_extraction_highlight: START. For topic {self.current_topic_id}. Input start={start_char}, end={end_char}. Doc len: {doc_len}. Doc text: '{doc_text_before_highlight}'")

        if start_char is None or end_char is None or start_char < 0 or end_char < start_char or end_char >= doc_len :
            logger.warning(f"apply_extraction_highlight: Invalid range: start={start_char}, end={end_char}, doc_len={doc_len}. Skipping highlight.")
            return

        cursor = self.textCursor()
        cursor.setPosition(start_char)
        selection_end_pos = end_char + 1
        
        if selection_end_pos > doc_len:
            logger.warning(f"apply_extraction_highlight: selection_end_pos ({selection_end_pos}) exceeds doc_len ({doc_len}). Clamping to {doc_len}.")
            selection_end_pos = doc_len
            if start_char >= selection_end_pos :
                 logger.warning(f"apply_extraction_highlight: start_char ({start_char}) is >= clamped selection_end_pos ({selection_end_pos}). Skipping highlight.")
                 return
        
        cursor.setPosition(selection_end_pos, QTextCursor.MoveMode.KeepAnchor)
        
        selected_text_for_log = cursor.selectedText().replace('\n', '\\n')[:60]
        logger.debug(f"apply_extraction_highlight: Cursor set. Selection: start={cursor.selectionStart()}, end={cursor.selectionEnd()}, text='{selected_text_for_log}...'")

        if not (cursor.selectionStart() == start_char and cursor.selectionEnd() == selection_end_pos):
            logger.critical(f"apply_extraction_highlight: Selection mismatch! Expected sel_start={start_char}, sel_end={selection_end_pos}. Got actual_sel_start={cursor.selectionStart()}, actual_sel_end={cursor.selectionEnd()}. This indicates a serious issue in cursor positioning.")

        char_format = QTextCharFormat()
        char_format.setBackground(color)
        cursor.mergeCharFormat(char_format)
        logger.debug(f"apply_extraction_highlight: Char format merged with background {color.name()}.")
        
        final_cursor_pos = cursor.selectionEnd()
        cursor.clearSelection()
        cursor.setPosition(final_cursor_pos)
        self.setTextCursor(cursor)

    def clear_content(self):
        """Clears the editor, resets current_topic_id, and sets placeholder text."""
        self.current_topic_id = None
        super().clear() 
        self.setPlaceholderText("Select a topic to view or edit its content, or open a collection.")


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton

    # Dummy DataManager for standalone testing
    class DummyDataManagerForEditorTest(DataManager):
        def __init__(self, collection_base_path):
            self.test_collection_dir = collection_base_path
            if not os.path.exists(self.test_collection_dir):
                os.makedirs(self.test_collection_dir)
            
            self.app_migrations_dir = "temp_editor_test_migrations"
            if not os.path.exists(self.app_migrations_dir):
                os.makedirs(self.app_migrations_dir)
            dummy_mig_file = os.path.join(self.app_migrations_dir, "000_dummy.sql")
            if not os.path.exists(dummy_mig_file):
                 with open(dummy_mig_file, "w") as f: f.write("-- test")
            
            super().__init__(collection_base_path)
            self.migrations_dir = self.app_migrations_dir
            try:
                self.initialize_collection_storage()
            except Exception as e:
                logger.error(f"Error initializing DummyDataManagerForEditorTest storage: {e}")

            self.topic_contents = {
                "topic1": "This is the first topic.\nIt has multiple lines.\nSome text to extract here for testing.",
                "topic2": "Another topic with some important information."
            }
            self.extractions_data = {
                "topic1": [{'id': 'extr1', 'child_topic_id': 'child_extr1', 'parent_text_start_char': 38, 'parent_text_end_char': 53}]
            }
            # Simulate creating these topics in the dummy DB
            conn = self._get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DROP TABLE IF EXISTS topics")
                cursor.execute("DROP TABLE IF EXISTS extractions")
                cursor.execute("""CREATE TABLE topics (id TEXT PRIMARY KEY, parent_id TEXT, title TEXT, text_file_uuid TEXT, created_at timestamp, updated_at timestamp, display_order INTEGER)""")
                cursor.execute("""CREATE TABLE extractions (id TEXT PRIMARY KEY, parent_topic_id TEXT, child_topic_id TEXT, parent_text_start_char INTEGER, parent_text_end_char INTEGER)""")

                for topic_id, content in self.topic_contents.items():
                    text_uuid = str(os.urandom(16).hex())
                    text_file_path = self._get_topic_text_file_path(text_uuid)
                    with open(text_file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    cursor.execute("INSERT INTO topics (id, title, text_file_uuid, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                                   (topic_id, f"Title for {topic_id}", text_uuid, dt.datetime.now(), dt.datetime.now()))
                
                for parent_id, extr_list in self.extractions_data.items():
                    for extr in extr_list:
                         cursor.execute("INSERT INTO extractions VALUES (?, ?, ?, ?, ?)",
                                   (extr['id'], parent_id, extr['child_topic_id'], extr['parent_text_start_char'], extr['parent_text_end_char']))
                conn.commit()
            except Exception as e:
                logger.error(f"Error setting up dummy DB for editor test: {e}")
            finally:
                conn.close()


        def get_topic_content(self, topic_id):
            logger.info(f"[DummyDM Editor] get_topic_content for {topic_id}")
            # Simulate reading from file via superclass method after setup
            return super().get_topic_content(topic_id)


        def get_extractions_for_parent(self, parent_topic_id):
            logger.info(f"[DummyDM Editor] get_extractions_for_parent for {parent_topic_id}")
            # Simulate reading from DB via superclass method
            return super().get_extractions_for_parent(parent_topic_id)

        def cleanup_test_dirs(self):
            if os.path.exists(self.test_collection_dir):
                shutil.rmtree(self.test_collection_dir)
                logger.info(f"Cleaned up test collection dir: {self.test_collection_dir}")
            if os.path.exists(self.app_migrations_dir):
                shutil.rmtree(self.app_migrations_dir)
                logger.info(f"Cleaned up test migrations dir: {self.app_migrations_dir}")

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("Topic Editor Widget Test")
    
    central_widget = QWidget()
    main_win.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    editor_widget = TopicEditorWidget()
    layout.addWidget(editor_widget)

    dummy_dm_instance_editor = None
    try:
        test_collection_path_editor = os.path.abspath("temp_editor_widget_test_collection")
        dummy_dm_instance_editor = DummyDataManagerForEditorTest(test_collection_path_editor)

        def load_t1():
            editor_widget.load_topic_content("topic1", dummy_dm_instance_editor)

        def load_t2():
            editor_widget.load_topic_content("topic2", dummy_dm_instance_editor)

        def print_selection():
            text, start, end = editor_widget.get_selected_text_and_offsets()
            if text:
                logger.info(f"Selected: '{text}', Start: {start}, End: {end}")
                editor_widget.apply_extraction_highlight(start, end, QColor("lightgreen"))
            else:
                logger.info("No text selected.")
                
        def clear_editor():
            editor_widget.clear_content()

        btn_load1 = QPushButton("Load Topic 1 (with existing highlight)")
        btn_load1.clicked.connect(load_t1)
        layout.addWidget(btn_load1)

        btn_load2 = QPushButton("Load Topic 2")
        btn_load2.clicked.connect(load_t2)
        layout.addWidget(btn_load2)
        
        btn_selection = QPushButton("Print Selection & Highlight Green")
        btn_selection.clicked.connect(print_selection)
        layout.addWidget(btn_selection)

        btn_clear = QPushButton("Clear Editor")
        btn_clear.clicked.connect(clear_editor)
        layout.addWidget(btn_clear)

        main_win.setGeometry(300, 300, 600, 400)
        main_win.show()
        exit_code = app.exec()
    except Exception as e:
        logger.error(f"Error in TopicEditorWidget test setup: {e}")
        exit_code = 1
    finally:
        if dummy_dm_instance_editor:
            dummy_dm_instance_editor.cleanup_test_dirs()
        sys.exit(exit_code)