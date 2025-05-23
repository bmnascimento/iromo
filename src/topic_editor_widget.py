import logging
import os # For __main__ test
import re # For placeholder title detection
import shutil # For __main__ test cleanup
import datetime # For __main__ test

from PyQt6.QtCore import pyqtSignal, QUrl, QThread, QObject # Removed QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QDesktopServices,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QFocusEvent, # Added QFocusEvent
    QPalette,
)
from PyQt6.QtWidgets import QApplication, QTextEdit, QToolBar, QVBoxLayout, QWidget

from .data_manager import DataManager # Import the DataManager class

logger = logging.getLogger(__name__)

# Worker for background saving
class SaveWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    success = pyqtSignal(str) # Emits the saved content

    def __init__(self, data_manager, topic_id, content_to_save):
        super().__init__()
        self.data_manager = data_manager
        self.topic_id = topic_id
        self.content_to_save = content_to_save

    def run(self):
        try:
            if self.data_manager and self.topic_id:
                logger.info(f"SaveWorker: Saving content for topic {self.topic_id} in background thread.")
                self.data_manager.save_topic_content(self.topic_id, self.content_to_save)
                self.success.emit(self.content_to_save)
            else:
                raise ValueError("DataManager or Topic ID not provided to SaveWorker.")
        except Exception as e:
            logger.error(f"SaveWorker: Error saving topic {self.topic_id}: {e}", exc_info=True)
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class TopicEditorWidget(QWidget): # Changed from QTextEdit to QWidget
    content_changed_externally = pyqtSignal() # Emitted if content is changed by an external action (e.g. undo/redo of save)
    dirty_changed = pyqtSignal(bool) # Emitted when the dirty state changes
    # AUTO_SAVE_INTERVAL = 2000 # milliseconds (2 seconds) # REMOVED

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_topic_id = None
        self.data_manager = None # Store DataManager instance
        self.original_content = "" # Stores the content as it was when loaded or last saved
        self._is_dirty = False      # True if content has changed since last load/save
        self.save_thread = None
        self.save_worker = None
        self._extraction_highlight_color = QColor("#A7D8DE") # Default highlight color

        self._setup_ui()
        # self._setup_auto_save_timer() # REMOVED
        self._connect_signals()

    # def _setup_auto_save_timer(self): # REMOVED
    #     self.auto_save_timer = QTimer(self) # REMOVED
    #     self.auto_save_timer.setSingleShot(True) # REMOVED
    #     self.auto_save_timer.setInterval(self.AUTO_SAVE_INTERVAL) # REMOVED
    #     self.auto_save_timer.timeout.connect(self._initiate_auto_save) # REMOVED

    def _setup_ui(self):
        """Sets up the UI elements for the widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Remove margins for toolbar
        layout.setSpacing(0) # Remove spacing between toolbar and editor

        # Toolbar
        self.toolbar = QToolBar(self)
        layout.addWidget(self.toolbar)

        # --- Formatting Actions ---
        # Bold
        self.action_bold = QAction("Bold", self)
        self.action_bold.setCheckable(True)
        self.action_bold.setShortcut(QKeySequence.StandardKey.Bold)
        self.action_bold.triggered.connect(self._toggle_bold)
        self.toolbar.addAction(self.action_bold)

        # Italic
        self.action_italic = QAction("Italic", self)
        self.action_italic.setCheckable(True)
        self.action_italic.setShortcut(QKeySequence.StandardKey.Italic)
        self.action_italic.triggered.connect(self._toggle_italic)
        self.toolbar.addAction(self.action_italic)

        # Underline
        self.action_underline = QAction("Underline", self)
        self.action_underline.setCheckable(True)
        self.action_underline.setShortcut(QKeySequence.StandardKey.Underline)
        self.action_underline.triggered.connect(self._toggle_underline)
        self.toolbar.addAction(self.action_underline)

        self.toolbar.addSeparator()

        # Paragraph
        self.action_paragraph = QAction("P", self)
        self.action_paragraph.triggered.connect(self._set_block_style_paragraph)
        self.toolbar.addAction(self.action_paragraph)

        # Heading 1
        self.action_h1 = QAction("H1", self)
        self.action_h1.triggered.connect(lambda: self._set_block_style_heading(1))
        self.toolbar.addAction(self.action_h1)

        # Heading 2
        self.action_h2 = QAction("H2", self)
        self.action_h2.triggered.connect(lambda: self._set_block_style_heading(2))
        self.toolbar.addAction(self.action_h2)
        
        # Heading 3 (Optional, as per spec)
        self.action_h3 = QAction("H3", self)
        self.action_h3.triggered.connect(lambda: self._set_block_style_heading(3))
        self.toolbar.addAction(self.action_h3)


        self.toolbar.addSeparator()

        # Open File Action
        self.action_open_file = QAction("Open HTML File", self)
        self.action_open_file.triggered.connect(self._open_current_topic_file)
        self.action_open_file.setEnabled(False) # Disabled by default
        self.toolbar.addAction(self.action_open_file)

        # Text Editor
        self.editor = QTextEdit(self)
        self.editor.setFont(QFont("Arial", 12))
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText("No collection open or no topic selected.")
        layout.addWidget(self.editor)

        self.setLayout(layout)

    def _connect_signals(self):
        """Connects signals for the editor."""
        self.editor.textChanged.connect(self._on_text_changed) # Renamed from _on_text_changed_for_auto_save
        self.editor.currentCharFormatChanged.connect(self._update_format_actions)
        self.editor.cursorPositionChanged.connect(self._update_format_actions)

    def _on_text_changed(self): # Renamed from _on_text_changed_for_auto_save
        """Handles text changes to update dirty status."""
        # First, update the dirty status based on content difference
        if not hasattr(self, 'editor') or self.editor is None:
            return

        current_text = self.editor.toHtml()
        if not self._is_dirty and current_text != self.original_content:
            self._is_dirty = True
            self.dirty_changed.emit(True)
            logger.debug(f"TopicEditorWidget for {self.current_topic_id} became dirty.")
        elif self._is_dirty and current_text == self.original_content:
            # This case might happen if user undoes changes to match original
            self._is_dirty = False
            self.dirty_changed.emit(False)
            logger.debug(f"TopicEditorWidget for {self.current_topic_id} became clean by reverting to original.")

        # Auto-save timer logic removed
        # if self.current_topic_id and self.data_manager and self._is_dirty:
        #     logger.debug(f"Text changed for {self.current_topic_id}, restarting auto-save timer.")
        #     self.auto_save_timer.start() # REMOVED
        # elif not self._is_dirty and self.auto_save_timer.isActive():
        #     logger.debug(f"Content for {self.current_topic_id} is no longer dirty, stopping auto-save timer.")
        #     self.auto_save_timer.stop() # REMOVED

    # def _initiate_auto_save(self): # REMOVED
    #     if not self._is_dirty or not self.current_topic_id or not self.data_manager: # REMOVED
    #         logger.debug("Auto-save triggered, but conditions not met (not dirty, no topic_id, or no data_manager). Skipping.") # REMOVED
    #         return # REMOVED
    # # REMOVED
    #     if self.save_thread and self.save_thread.isRunning(): # REMOVED
    #         logger.warning(f"Auto-save for {self.current_topic_id}: Previous save operation still in progress. Skipping new save.") # REMOVED
    #         # Optionally, restart timer to try again later, or queue the save. # REMOVED
    #         # For simplicity, we skip and rely on next textChanged or explicit save. # REMOVED
    #         # self.auto_save_timer.start() # Re-queue # REMOVED
    #         return # REMOVED
    # # REMOVED
    #     content_to_save = self.editor.toHtml() # REMOVED
    #     logger.info(f"Auto-saving content for topic {self.current_topic_id}. Dirty: {self._is_dirty}") # REMOVED
    # # REMOVED
    #     self.save_thread = QThread(self) # REMOVED
    #     self.save_worker = SaveWorker(self.data_manager, self.current_topic_id, content_to_save) # REMOVED
    #     self.save_worker.moveToThread(self.save_thread) # REMOVED
    # # REMOVED
    #     self.save_worker.success.connect(self._handle_save_success) # REMOVED
    #     self.save_worker.error.connect(self._handle_save_failure) # REMOVED
    #     self.save_worker.finished.connect(self.save_thread.quit) # REMOVED
    #     self.save_worker.finished.connect(self.save_worker.deleteLater) # REMOVED
    #     self.save_thread.finished.connect(self.save_thread.deleteLater) # REMOVED
    #     self.save_thread.started.connect(self.save_worker.run) # REMOVED
    # # REMOVED
    #     self.save_thread.start() # REMOVED

    def _handle_save_success(self, saved_content: str):
        logger.info(f"Successfully saved topic {self.current_topic_id}.") # Changed "auto-saved" to "saved"
        self.original_content = saved_content # Update baseline to the successfully saved content
        if self.editor.toHtml() == saved_content: # Check if content changed again during save
            self.mark_as_clean() # Resets _is_dirty to False and emits signal
        else:
            # Content changed again while saving, so it's still dirty relative to the *new* original_content
            # The _on_text_changed will handle restarting the timer if needed.
            logger.debug(f"Content for {self.current_topic_id} was modified during background save. Remains dirty.")
            # No need to explicitly set _is_dirty = True, as _on_text_changed will do it.

        # Clean up references
        self.save_thread = None
        self.save_worker = None


    def _handle_save_failure(self, error_message: str):
        logger.error(f"Save failed for topic {self.current_topic_id}: {error_message}") # Changed "Auto-save" to "Save"
        # Decide on error handling: maybe a status bar message, or keep dirty flag
        # For now, we keep it dirty, so the next change or manual action might retry.
        # Clean up references
        self.save_thread = None
        self.save_worker = None


    # --- Formatting Action Handlers ---
    def _toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if self.action_bold.isChecked() else QFont.Weight.Normal)
        self._merge_char_format(fmt)

    def _toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(self.action_italic.isChecked())
        self._merge_char_format(fmt)

    def _toggle_underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(self.action_underline.isChecked())
        self._merge_char_format(fmt)

    def _merge_char_format(self, fmt: QTextCharFormat):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.editor.mergeCurrentCharFormat(fmt) # Ensures typing new text also gets the format

    def _set_block_style_paragraph(self):
        self._set_block_style_heading(0) # Heading level 0 is a normal paragraph

    def _set_block_style_heading(self, level: int):
        cursor = self.editor.textCursor()
        block_fmt = QTextBlockFormat()
        if level > 0:
            block_fmt.setHeadingLevel(level)
        # For level 0 (paragraph), a default QTextBlockFormat is fine,
        # or ensure any existing heading level is removed.
        # QTextBlockFormat() by default is a paragraph.
        # To be explicit for removing heading:
        # if level == 0:
        #     block_fmt.setProperty(QTextBlockFormat.Property.HeadingLevel, 0) # or some other way to clear it
        
        cursor.mergeBlockFormat(block_fmt)
        self.editor.setFocus() # Return focus to editor

    def _update_format_actions(self):
        """Updates the state of formatting actions based on the current cursor or selection."""
        char_format = self.editor.currentCharFormat()
        block_format = self.editor.textCursor().blockFormat()

        self.action_bold.setChecked(char_format.fontWeight() == QFont.Weight.Bold)
        self.action_italic.setChecked(char_format.fontItalic())
        self.action_underline.setChecked(char_format.fontUnderline())

        # Update heading/paragraph state (more complex, might need a QComboBox or radio buttons for exclusive selection)
    def _open_current_topic_file(self):
        """Opens the HTML file of the current topic in the system's default application."""
        if not self.current_topic_id or not self.data_manager:
            logger.warning("Open file called but no topic/data_manager loaded.")
            return

        topic_details = self.data_manager.get_topic_details(self.current_topic_id)
        if not topic_details or 'text_file_uuid' not in topic_details:
            logger.error(f"Could not retrieve details or text_file_uuid for topic {self.current_topic_id}.")
            return

        # We need to use the _get_topic_text_file_path method from DataManager.
        # Since it's a protected member, it's better if DataManager exposes a public method
        # to get the full path directly, or we reconstruct it here if the pattern is stable.
        # For now, let's assume DataManager needs a public method or we call the protected one.
        # To avoid modifying DataManager further in this step, we'll call the protected one.
        # A better long-term solution would be a public `get_topic_file_path(topic_id)` in DataManager.
        file_path = self.data_manager._get_topic_text_file_path(topic_details['text_file_uuid'])

        if not os.path.exists(file_path):
            logger.error(f"Topic file does not exist at path: {file_path}")
            # Optionally, inform the user via a QMessageBox
            return

        url = QUrl.fromLocalFile(file_path)
        if not QDesktopServices.openUrl(url):
            logger.error(f"Could not open file: {file_path}")
            # Optionally, inform the user
        # For now, we don't have a visual indicator for H1/H2/P on the buttons themselves.
        # If we made them checkable, we'd need to uncheck others.
        # heading_level = block_format.headingLevel()
        # self.action_paragraph.setChecked(heading_level == 0)
        # self.action_h1.setChecked(heading_level == 1)
        # self.action_h2.setChecked(heading_level == 2)
        # self.action_h3.setChecked(heading_level == 3)


    def _get_document_text_for_logging(self):
        doc = self.editor.document()
        text = doc.toPlainText()
        return text.replace('\n', '\\n')[:100]

    def load_topic_content(self, topic_id: str, data_manager_instance: DataManager):
        """Loads and displays the content for the given topic_id using the provided DataManager."""
        logger.info(f"Loading content for topic_id: {topic_id}")
        self.clear_content() # Clear previous content and highlights, sets placeholder

        if not data_manager_instance:
            logger.warning("load_topic_content called with no DataManager instance.")
            self.editor.setPlaceholderText(f"Error: Data manager not available for topic {topic_id}.")
            self.action_open_file.setEnabled(False)
            return

        self.data_manager = data_manager_instance # Store DataManager
        content = self.data_manager.get_topic_content(topic_id)
        if content is not None:
            self.current_topic_id = topic_id
            self.original_content = content # Store original content
            logger.debug(f"TopicEditorWidget: Content for topic {topic_id} before setHtml: '{content[:500]}'") # Log first 500 chars
            self.editor.setHtml(content) # Render content as HTML
            self.mark_as_clean() # Sets _is_dirty to False and emits signal
            # if self.auto_save_timer.isActive(): # Stop any pending save from previous topic # REMOVED
            #     self.auto_save_timer.stop() # REMOVED
            self.action_open_file.setEnabled(True) # Enable button
            logger.debug(f"After setHtml for {topic_id}. Doc text: '{self._get_document_text_for_logging()}'")

            # cursor = self.editor.textCursor()
            # cursor.select(QTextCursor.SelectionType.Document)
            # default_format = QTextCharFormat()
            # # default_format.setFont(self.editor.font()) # Ensure it uses the editor's default font
            # cursor.setCharFormat(default_format)
            # cursor.clearSelection()
            # self.editor.setTextCursor(cursor)
            # logger.debug(f"Applied default char format to entire document for topic {topic_id}.")

            self._apply_existing_highlights(self.data_manager)
        else:
            self.current_topic_id = None # Ensure this is reset
            self.editor.setPlaceholderText(f"Could not load content for topic {topic_id}.")
            logger.warning(f"Content for topic_id {topic_id} was None.")
            self.original_content = ""
            self.mark_as_clean()
            self.action_open_file.setEnabled(False) # Disable button

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
        return self.editor.toHtml() # Return HTML content

    def get_selected_text_and_offsets(self):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            return None, -1, -1
        
        selected_text = cursor.selectedText()
        start_offset = cursor.selectionStart()
        end_offset = cursor.selectionEnd()
        
        return selected_text, start_offset, end_offset - 1 # end_offset is exclusive, so -1 for inclusive

    def apply_extraction_highlight(self, start_char, end_char):
        doc_text_before_highlight = self._get_document_text_for_logging()
        doc_len = len(self.editor.toPlainText()) # Use self.editor
        logger.debug(f"apply_extraction_highlight: START. For topic {self.current_topic_id}. Input start={start_char}, end={end_char}. Doc len: {doc_len}. Doc text: '{doc_text_before_highlight}'")

        if start_char is None or end_char is None or start_char < 0 or end_char < start_char or end_char >= doc_len :
            logger.warning(f"apply_extraction_highlight: Invalid range: start={start_char}, end={end_char}, doc_len={doc_len}. Skipping highlight.")
            return

        cursor = self.editor.textCursor() # Use self.editor
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
            # This check might be too strict if HTML content vs plain text indexing differs slightly.
            # For now, keeping it for debugging.
            logger.warning(f"apply_extraction_highlight: Selection mismatch! Expected sel_start={start_char}, sel_end={selection_end_pos}. Got actual_sel_start={cursor.selectionStart()}, actual_sel_end={cursor.selectionEnd()}. This might be due to HTML vs PlainText offset differences.")

        highlight_color = getattr(self, '_extraction_highlight_color', QColor("#A7D8DE"))
        char_format = QTextCharFormat()
        char_format.setBackground(highlight_color)
        char_format.setForeground(QColor("black")) # Set text color to black
        cursor.mergeCharFormat(char_format)
        logger.debug(f"apply_extraction_highlight: Char format merged with background {highlight_color.name()}.")
        
        final_cursor_pos = cursor.selectionEnd()
        cursor.clearSelection()
        cursor.setPosition(final_cursor_pos)
        self.editor.setTextCursor(cursor) # Use self.editor

    def clear_content(self):
        """Clears the editor, resets current_topic_id, and sets placeholder text."""
        self.current_topic_id = None
        self.editor.clear() # Use self.editor
        self.editor.setPlaceholderText("Select a topic to view or edit its content, or open a collection.") # Use self.editor
        self.original_content = ""
        self.mark_as_clean()
        self.action_open_file.setEnabled(False) # Disable button
        self.data_manager = None # Clear stored DataManager

    # _handle_text_changed is now part of _on_text_changed_for_auto_save
    # def _handle_text_changed(self):
    #     """Sets the dirty flag if the current content differs from original_content."""
    #     # Check if the editor is available, e.g. during __init__ it might not be fully set up
    #     if not hasattr(self, 'editor') or self.editor is None:
    #         return
    #
    #     if not self._is_dirty: # Only change and emit if it wasn't already dirty
    #         current_text = self.editor.toHtml() # Use self.editor
    #         if current_text != self.original_content:
    #             self._is_dirty = True
    #             self.dirty_changed.emit(True)
    #             logger.debug(f"TopicEditorWidget for {self.current_topic_id} became dirty.")

    def is_dirty(self) -> bool:
        """Returns True if the content has been modified since it was last loaded or saved."""
        return self._is_dirty

    def _check_and_update_placeholder_title(self):
        """
        Checks if the current topic has a placeholder title and updates it
        based on the first line/50 chars of content if applicable.
        Returns True if title was updated, False otherwise.
        """
        if not self.current_topic_id or not self.data_manager:
            return False

        topic_details = self.data_manager.get_topic_details(self.current_topic_id)
        if not topic_details:
            logger.warning(f"Could not get details for topic {self.current_topic_id} to check placeholder title.")
            return False

        current_title = topic_details.get('title', '')
        # Regex for "Topic YYYY-MM-DD HH:MM:SS"
        placeholder_pattern = r"^Topic \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"

        if re.match(placeholder_pattern, current_title):
            plain_text_content = self.editor.document().toPlainText()
            
            if not plain_text_content.strip(): # Content is empty or only whitespace
                logger.debug(f"Topic {self.current_topic_id} has placeholder title '{current_title}' but content is empty. Title not changed.")
                return False

            new_title_candidate = plain_text_content[:50]
            newline_index = new_title_candidate.find('\n')
            if newline_index != -1:
                new_title_candidate = new_title_candidate[:newline_index]
            
            new_title_candidate = new_title_candidate.strip()

            if new_title_candidate:
                logger.info(f"Topic {self.current_topic_id} has placeholder title '{current_title}'. Updating to: '{new_title_candidate}'")
                try:
                    # This method will need to be added to DataManager
                    self.data_manager.update_topic_title(self.current_topic_id, new_title_candidate)
                    # The DataManager's update_topic_title method should emit a signal
                    # (e.g., topic_updated or topic_metadata_changed) which the
                    # KnowledgeTreeWidget listens to for updating the display.
                    return True
                except Exception as e:
                    logger.error(f"Failed to update placeholder title for topic {self.current_topic_id}: {e}", exc_info=True)
                    return False
            else:
                logger.debug(f"Topic {self.current_topic_id} has placeholder title '{current_title}' but extracted new title is empty. Title not changed.")
                return False
        return False

    def force_save_if_dirty(self, wait_for_completion=False):
        """
        If the content is dirty, triggers an immediate save.
        Optionally updates placeholder title before saving.
        If wait_for_completion is True, this method will block until the save is done.
        Otherwise, it will attempt to save in the background.
        """
        if not self._is_dirty or not self.current_topic_id or not self.data_manager:
            logger.debug(f"Force save called for {self.current_topic_id}, but not dirty or no topic/DM. Skipping.")
            return

        # If we are proceeding to save because it's dirty, then check and update title.
        self._check_and_update_placeholder_title()
        # If title was updated, DataManager.update_topic_title was called.
        # The main window (KnowledgeTreeWidget) should observe DataManager signals for topic changes.

        logger.info(f"Force saving content for topic {self.current_topic_id} (wait_for_completion={wait_for_completion}). Dirty: {self._is_dirty}")
        content_to_save = self.editor.toHtml()

        if self.save_thread and self.save_thread.isRunning():
            logger.warning(f"Force save for {self.current_topic_id}: A save operation is already in progress.")
            if wait_for_completion:
                logger.info(f"Waiting for existing save thread to complete for topic {self.current_topic_id}.")
                self.save_thread.wait() # Wait for the existing thread to finish
                # After waiting, the content might have been saved by the other thread, making it clean.
                # The title update (if applicable for *this* call's context) has already been attempted.
                if not self._is_dirty: # Check current dirty state after wait
                    logger.info(f"Force save for {self.current_topic_id}: Content became clean while waiting for another save. Skipping further content save in this call.")
                    return # Content is clean, title (if placeholder) was already processed.
                logger.info(f"Force save for {self.current_topic_id}: Content still dirty after waiting. Proceeding with current save.")
            else: # not wait_for_completion
                logger.info(f"Force save for {self.current_topic_id}: Save in progress, and not waiting. Skipping this save trigger.")
                return
        
        # If, after all checks and potential waits, the content is no longer dirty,
        # we might not need to save the content. The title update (if any) has already occurred.
        if not self._is_dirty:
            logger.info(f"Force save for {self.current_topic_id}: Content is no longer dirty (e.g. saved by waited thread, or was never dirty enough for this stage). Skipping content save.")
            return

        if wait_for_completion:
            try:
                logger.info(f"Force save (blocking) for topic {self.current_topic_id}.")
                self.data_manager.save_topic_content(self.current_topic_id, content_to_save)
                self._handle_save_success(content_to_save)
            except Exception as e:
                logger.error(f"Force save (blocking) for topic {self.current_topic_id} failed: {e}", exc_info=True)
                self._handle_save_failure(str(e))
        else:
            # Background save logic
            logger.info(f"Force save (background) for topic {self.current_topic_id} initiated.")
            # Ensure no other save thread from this editor instance is running
            if self.save_thread and self.save_thread.isRunning():
                 logger.warning(f"Background save for {self.current_topic_id}: Previous save worker from this editor instance still active. Skipping new background save.")
                 return

            self.save_thread = QThread(self)
            self.save_worker = SaveWorker(self.data_manager, self.current_topic_id, content_to_save)
            self.save_worker.moveToThread(self.save_thread)

            self.save_worker.success.connect(self._handle_save_success)
            self.save_worker.error.connect(self._handle_save_failure)
            self.save_worker.finished.connect(self.save_thread.quit)
            self.save_worker.finished.connect(self.save_worker.deleteLater)
            self.save_thread.finished.connect(self.save_thread.deleteLater)
            self.save_thread.finished.connect(lambda: setattr(self, 'save_thread', None)) # Clear self.save_thread
            self.save_thread.started.connect(self.save_worker.run)
            self.save_thread.start()

    def mark_as_saved(self, saved_content: str):
        """
        Marks the content as saved by updating original_content and resetting the dirty flag.
        This is typically called after a successful save operation.
        """
        self.original_content = saved_content
        self.mark_as_clean()

    # --- Focus Event Handling ---
    def focusOutEvent(self, event: QFocusEvent):
        """Handle the editor losing focus."""
        logger.debug(f"TopicEditorWidget for topic {self.current_topic_id} lost focus. Reason: {event.reason()}. Checking if dirty to save.")
        # Check if the new focus widget is a child of this TopicEditorWidget.
        # This prevents saving when focus moves, for example, from the QTextEdit to the QToolBar within this widget.
        new_focus_widget = QApplication.focusWidget()
        if new_focus_widget:
            is_child = False
            parent = new_focus_widget
            while parent:
                if parent == self:
                    is_child = True
                    break
                parent = parent.parent()
            
            if is_child:
                logger.debug(f"Focus moved to a child widget ({new_focus_widget.__class__.__name__}) of TopicEditorWidget. Not saving.")
                super().focusOutEvent(event)
                return

        self.force_save_if_dirty(wait_for_completion=False) # Non-blocking save
        super().focusOutEvent(event) # Call base class implementation
    def mark_as_clean(self):
        """Resets the dirty flag and emits the dirty_changed signal if state changes."""
        if self._is_dirty:
            self._is_dirty = False
            self.dirty_changed.emit(False)
            logger.debug(f"TopicEditorWidget for {self.current_topic_id} marked as clean.")
        # If it was already clean, no need to emit the signal again.
        # However, to ensure consistency, we can always set and emit:
        # self._is_dirty = False
        # self.dirty_changed.emit(False)

    def set_font(self, font: QFont):
        """Sets the font for the editor."""
        self.editor.setFont(font)
        # If you want to apply this font to existing content, you might need to iterate or select all and apply.
        # For now, this will affect new text and potentially the default for unformatted existing text.
        # To apply to all existing content:
        # cursor = self.editor.textCursor()
        # cursor.select(QTextCursor.SelectionType.Document)
        # char_format = QTextCharFormat()
        # char_format.setFont(font)
        # cursor.mergeCharFormat(char_format)
        # cursor.clearSelection()
        # self.editor.setTextCursor(cursor)
        # self.editor.setCurrentCharFormat(char_format) # Ensure new typing uses this font

    def set_extraction_highlight_color(self, color_str: str):
        """Sets the color used for extraction highlights."""
        # This method would store the color. The actual application of the color
        # happens in _apply_existing_highlights and apply_extraction_highlight.
        # We need to decide if changing this should re-apply all highlights.
        # For now, let's assume apply_extraction_highlight will use a fixed color
        # or a color fetched from settings/property at the time of highlighting.
        # If we want dynamic re-coloring, _apply_existing_highlights would need to be
        # called after this, and apply_extraction_highlight would need to use the new color.
        
        # For simplicity, let's assume apply_extraction_highlight uses a hardcoded color for now,
        # and this setting would be used if we refactor it to be dynamic.
        # Or, we can update a property here that apply_extraction_highlight reads.
        try:
            self._extraction_highlight_color = QColor(color_str)
            logger.info(f"Extraction highlight color set to: {color_str}")
            # If content is loaded and has highlights, re-apply them with the new color
            if self.current_topic_id and self.data_manager:
                self._apply_existing_highlights(self.data_manager) # This will use the new color if apply_extraction_highlight is adapted
        except Exception as e:
            logger.error(f"Invalid color string for extraction highlight: {color_str}. Error: {e}")
            self._extraction_highlight_color = QColor("#A7D8DE") # Fallback to default


    # In apply_extraction_highlight, change:
    # highlight_color = QColor("#A7D8DE") # Fixed light teal color
    # TO:
    # highlight_color = getattr(self, '_extraction_highlight_color', QColor("#A7D8DE"))

    # Make sure to initialize _extraction_highlight_color in __init__
    # self._extraction_highlight_color = QColor("#A7D8DE") # Default

    def set_font(self, font: QFont):
        """Sets the font for the editor."""
        self.editor.setFont(font)
        # If you want to apply this font to existing content, you might need to iterate or select all and apply.
        # For now, this will affect new text and potentially the default for unformatted existing text.
        # To apply to all existing content:
        # cursor = self.editor.textCursor()
        # cursor.select(QTextCursor.SelectionType.Document)
        # char_format = QTextCharFormat()
        # char_format.setFont(font)
        # cursor.mergeCharFormat(char_format)
        # cursor.clearSelection()
        # self.editor.setTextCursor(cursor)
        # self.editor.setCurrentCharFormat(char_format) # Ensure new typing uses this font

    def set_extraction_highlight_color(self, color_str: str):
        """Sets the color used for extraction highlights."""
        # This method would store the color. The actual application of the color
        # happens in _apply_existing_highlights and apply_extraction_highlight.
        # We need to decide if changing this should re-apply all highlights.
        # For now, let's assume apply_extraction_highlight will use a fixed color
        # or a color fetched from settings/property at the time of highlighting.
        # If we want dynamic re-coloring, _apply_existing_highlights would need to be
        # called after this, and apply_extraction_highlight would need to use the new color.
        
        # For simplicity, let's assume apply_extraction_highlight uses a hardcoded color for now,
        # and this setting would be used if we refactor it to be dynamic.
        # Or, we can update a property here that apply_extraction_highlight reads.
        try:
            self._extraction_highlight_color = QColor(color_str)
            logger.info(f"Extraction highlight color set to: {color_str}")
            # If content is loaded and has highlights, re-apply them with the new color
            if self.current_topic_id and self.data_manager:
                self._apply_existing_highlights(self.data_manager) # This will use the new color if apply_extraction_highlight is adapted
        except Exception as e:
            logger.error(f"Invalid color string for extraction highlight: {color_str}. Error: {e}")
            self._extraction_highlight_color = QColor("#A7D8DE") # Fallback to default


    # In apply_extraction_highlight, change:
    # highlight_color = QColor("#A7D8DE") # Fixed light teal color
    # TO:
    # highlight_color = getattr(self, '_extraction_highlight_color', QColor("#A7D8DE"))

    # Make sure to initialize _extraction_highlight_color in __init__
    # self._extraction_highlight_color = QColor("#A7D8DE") # Default


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
                                   (topic_id, f"Title for {topic_id}", text_uuid, datetime.datetime.now(), datetime.datetime.now()))
                
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