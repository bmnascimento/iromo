from PyQt6.QtWidgets import QTextEdit, QApplication
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter, QFont
from PyQt6.QtCore import Qt, pyqtSignal
import logging

from . import data_manager as dm # Assuming data_manager.py is in the same src directory

logger = logging.getLogger(__name__)

class TopicEditorWidget(QTextEdit):
    # Signal emitted when content might have changed and needs saving
    # (e.g., on focus out, or before an extraction)
    content_changed_externally = pyqtSignal() # Could pass topic_id if needed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_topic_id = None
        self.setFont(QFont("Arial", 12)) # Default font
        self.setAcceptRichText(True) # Important for highlighting

        # Could connect textChanged signal if auto-save or dirty flag is needed
        # self.textChanged.connect(self._handle_text_changed)

    def _get_document_text_for_logging(self):
        # Helper for concise logging of document content
        doc = self.document()
        text = doc.toPlainText()
        return text.replace('\n', '\\n')[:100] # First 100 chars, newlines escaped

    def load_topic_content(self, topic_id):
        """Loads and displays the content for the given topic_id."""
        logger.info(f"Loading content for topic_id: {topic_id}")
        self.clear_content() # Clear previous content and highlights
        # logger.debug(f"After clear_content. Current text: '{self._get_document_text_for_logging()}'")
        content = dm.get_topic_content(topic_id)
        if content is not None:
            self.current_topic_id = topic_id
            # logger.debug(f"Setting plain text for {topic_id}: '{content.replace('\n', '\\n')[:100]}'")
            self.setPlainText(content) # Use setPlainText to avoid issues if content has accidental HTML
            logger.debug(f"After setPlainText for {topic_id}. Doc text: '{self._get_document_text_for_logging()}'")

            # Explicitly reset all character formatting to default before applying new highlights
            # This is to prevent persistent formatting issues.
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            default_format = QTextCharFormat() # Create a default format
            # You might want to explicitly set font/color if it differs from a fresh QTextEdit
            # For now, an empty QTextCharFormat should revert to defaults for background.
            cursor.setCharFormat(default_format)
            cursor.clearSelection()
            self.setTextCursor(cursor) # Ensure the cursor is updated
            logger.debug(f"Applied default char format to entire document for topic {topic_id}.")

            self._apply_existing_highlights()
        else:
            self.current_topic_id = None
            self.setPlaceholderText(f"Could not load content for topic {topic_id}.")
            logger.warning(f"Content for topic_id {topic_id} was None.")
        # logger.debug(f"Finished load_topic_content for topic_id: {topic_id}")

    def _apply_existing_highlights(self):
        """Applies highlights for all extractions already made from the current topic."""
        logger.debug(f"Applying existing highlights for topic {self.current_topic_id}")
        if not self.current_topic_id:
            logger.debug("No current_topic_id, returning from _apply_existing_highlights.")
            return
        
        extractions = dm.get_extractions_for_parent(self.current_topic_id)
        logger.debug(f"Found {len(extractions)} extractions for topic {self.current_topic_id}: {extractions}")
        for i, extr in enumerate(extractions):
            start_char = extr['parent_text_start_char']
            end_char = extr['parent_text_end_char']
            logger.debug(f"Applying highlight {i+1}/{len(extractions)}: start={start_char}, end={end_char}")
            self.apply_extraction_highlight(start_char, end_char)
        # logger.debug(f"Finished _apply_existing_highlights for topic {self.current_topic_id}")

    def get_current_content(self):
        """Returns the plain text content currently in the editor."""
        return self.toPlainText()

    def get_selected_text_and_offsets(self):
        """
        Returns the currently selected plain text and its start/end character offsets.
        Returns (None, -1, -1) if no text is selected.
        Offsets are for plain text.
        """
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return None, -1, -1
        
        selected_text = cursor.selectedText()
        start_offset = cursor.selectionStart()
        end_offset = cursor.selectionEnd() # This is exclusive for selection
        
        return selected_text, start_offset, end_offset -1 # Make end_offset inclusive for our storage

    def apply_extraction_highlight(self, start_char, end_char, color=QColor("lightblue")):
        """
        Applies a background color highlight to the text range specified by
        start_char and end_char (inclusive).
        """
        doc_text_before_highlight = self._get_document_text_for_logging()
        doc_len = len(self.toPlainText())
        logger.debug(f"apply_extraction_highlight: START. For topic {self.current_topic_id}. Input start={start_char}, end={end_char}. Doc len: {doc_len}. Doc text: '{doc_text_before_highlight}'")

        if start_char is None or end_char is None or start_char < 0 or end_char < start_char or end_char >= doc_len :
            logger.warning(f"apply_extraction_highlight: Invalid range: start={start_char}, end={end_char}, doc_len={doc_len}. Skipping highlight.")
            return

        cursor = self.textCursor()
        # It's good practice to ensure the cursor is in a known state or doesn't have an unexpected selection.
        # However, setPosition should override previous selection state when not using KeepAnchor for the first setPosition.
        
        cursor.setPosition(start_char)
        # The selection end for QTextCursor is exclusive. If end_char is inclusive, we need to select up to end_char + 1.
        selection_end_pos = end_char + 1
        
        # Safety check: ensure selection_end_pos does not exceed document length
        if selection_end_pos > doc_len:
            logger.warning(f"apply_extraction_highlight: selection_end_pos ({selection_end_pos}) exceeds doc_len ({doc_len}). Clamping to {doc_len}.")
            selection_end_pos = doc_len
            if start_char >= selection_end_pos and doc_len > 0 : # If start is now also out of bounds due to clamping
                 logger.warning(f"apply_extraction_highlight: start_char ({start_char}) is >= clamped selection_end_pos ({selection_end_pos}). Skipping highlight.")
                 return
            elif doc_len == 0 and start_char == 0 and selection_end_pos == 0: # Highlighting empty doc, technically valid but unusual
                 pass # allow to proceed if it's a zero-length selection on empty doc
            elif start_char >= selection_end_pos : # General case for start >= end after clamping
                 logger.warning(f"apply_extraction_highlight: start_char ({start_char}) is >= clamped selection_end_pos ({selection_end_pos}). Skipping highlight.")
                 return


        cursor.setPosition(selection_end_pos, QTextCursor.MoveMode.KeepAnchor)
        
        selected_text_for_log = cursor.selectedText().replace('\n', '\\n')[:60]
        logger.debug(f"apply_extraction_highlight: Cursor set. Selection: start={cursor.selectionStart()}, end={cursor.selectionEnd()}, text='{selected_text_for_log}...'")

        if not (cursor.selectionStart() == start_char and cursor.selectionEnd() == selection_end_pos):
            logger.critical(f"apply_extraction_highlight: Selection mismatch! Expected sel_start={start_char}, sel_end={selection_end_pos}. Got actual_sel_start={cursor.selectionStart()}, actual_sel_end={cursor.selectionEnd()}. This indicates a serious issue in cursor positioning.")
            # Potentially skip merging format if selection is not as expected
            # return

        char_format = QTextCharFormat()
        char_format.setBackground(color)
        cursor.mergeCharFormat(char_format)
        logger.debug(f"apply_extraction_highlight: Char format merged with background {color.name()}.")
        
        # Clear selection after applying format and set cursor position
        final_cursor_pos = cursor.selectionEnd() # Keep track of where selection ended
        cursor.clearSelection()
        cursor.setPosition(final_cursor_pos) # Place cursor at the end of what was the selection
        self.setTextCursor(cursor)
        # logger.debug(f"apply_extraction_highlight: FINISHED. Cursor at {cursor.position()}.")


    def clear_content(self):
        """Clears the editor and resets current_topic_id."""
        self.current_topic_id = None
        super().clear() # Call QTextEdit's clear
        self.setPlaceholderText("Select a topic to view or edit its content.")

    # def _handle_text_changed(self):
    #     # Placeholder for auto-save logic or setting a 'dirty' flag
    #     if self.current_topic_id:
    #         # print(f"Text changed for topic: {self.current_topic_id}")
    #         # self.content_changed_externally.emit() # Or a more specific signal
    #         pass


if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton

    # Dummy data_manager for standalone testing
    class DummyDM:
        def get_topic_content(self, topic_id):
            if topic_id == "topic1":
                return "This is the first topic.\nIt has multiple lines.\nSome text to extract here for testing."
            if topic_id == "topic2":
                return "Another topic with some important information."
            return None

        def get_extractions_for_parent(self, parent_topic_id):
            if parent_topic_id == "topic1":
                # Simulate an existing extraction: "text to extract" (chars 38-53 inclusive)
                return [{'id': 'extr1', 'child_topic_id': 'child_extr1', 'parent_text_start_char': 38, 'parent_text_end_char': 53}]
            return []

    dm_actual = dm
    dm = DummyDM()

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("Topic Editor Widget Test")
    
    central_widget = QWidget()
    main_win.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    editor_widget = TopicEditorWidget()
    layout.addWidget(editor_widget)

    def load_t1():
        editor_widget.load_topic_content("topic1")

    def load_t2():
        editor_widget.load_topic_content("topic2")

    def print_selection():
        text, start, end = editor_widget.get_selected_text_and_offsets()
        if text:
            logger.info(f"Selected: '{text}', Start: {start}, End: {end}")
            # Test highlighting the selection
            editor_widget.apply_extraction_highlight(start, end, QColor("lightgreen"))
        else:
            logger.info("No text selected.")
            
    def clear_editor():
        editor_widget.clear_content()

    btn_load1 = QPushButton("Load Topic 1")
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
    
    dm = dm_actual # Restore
    sys.exit(app.exec())