import sys
import os
from PyQt6.QtCore import QSettings, pyqtSignal, Qt, QObject
from PyQt6.QtWidgets import (
    QApplication, QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QPushButton,
    QDialogButtonBox, QFontComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QKeySequenceEdit, QMessageBox
)
from PyQt6.QtGui import QFont, QFontDatabase, QKeySequence
from .data_manager import DataManager


class SettingsDialog(QDialog):
    # Signals for settings changes
    theme_changed = pyqtSignal(str)
    editor_font_changed = pyqtSignal(str, int)
    tree_font_changed = pyqtSignal(str, int)
    extraction_highlight_color_changed = pyqtSignal(str)
    default_collection_path_changed = pyqtSignal(str)
    autosave_interval_changed = pyqtSignal(int)
    recent_collections_count_changed = pyqtSignal(int)
    default_topic_title_length_changed = pyqtSignal(int)
    confirm_topic_deletion_changed = pyqtSignal(bool)
    open_last_collection_on_startup_changed = pyqtSignal(bool)
    show_welcome_on_startup_changed = pyqtSignal(bool)
    log_level_changed = pyqtSignal(str)

    def __init__(self, data_manager: DataManager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.settings = QSettings("IromoProject", "Iromo")
        self.autosave_values = [0, 1, 2, 5, 10, 15, 30] # Corresponds to autosave_interval_combo items

        self.setWindowTitle("Settings")
        self.setMinimumWidth(550)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self._create_appearance_tab()
        self._create_data_tab()
        self._create_behavior_tab()
        self._create_logging_tab()
        if self.data_manager: # Only create shortcuts tab if data_manager is available
            self._create_shortcuts_tab()
            if hasattr(self.data_manager, 'shortcuts_changed'): # Check if signal exists
                 self.data_manager.shortcuts_changed.connect(self._populate_shortcuts_table)


        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        self.button_box.rejected.connect(self.reject) # Cancel button
        # Connections for OK and Apply buttons
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.accept_settings)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_settings)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        self.load_settings() # Load settings after UI is created

    def _create_appearance_tab(self):
        appearance_widget = QWidget()
        layout = QFormLayout(appearance_widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # UI Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System Default", "Light", "Dark"])
        layout.addRow("Theme:", self.theme_combo)

        # Editor Font Family
        self.editor_font_family_combo = QFontComboBox()
        layout.addRow("Editor Font:", self.editor_font_family_combo)

        # Editor Font Size
        self.editor_font_size_spinbox = QSpinBox()
        self.editor_font_size_spinbox.setRange(8, 72)
        layout.addRow("Editor Font Size:", self.editor_font_size_spinbox)

        # Tree Font Family
        self.tree_font_family_combo = QFontComboBox()
        layout.addRow("Tree View Font:", self.tree_font_family_combo)

        # Tree Font Size
        self.tree_font_size_spinbox = QSpinBox()
        self.tree_font_size_spinbox.setRange(8, 24)
        layout.addRow("Tree View Font Size:", self.tree_font_size_spinbox)

        # Extraction Highlight Color
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0,0,0,0)
        self.extraction_highlight_color_edit = QLineEdit()
        self.extraction_highlight_color_edit.setPlaceholderText("#ADD8E6") # Default
        self.extraction_highlight_color_button = QPushButton("Choose...")
        # Connection for QColorDialog to be added in logic implementation phase
        color_layout.addWidget(self.extraction_highlight_color_edit)
        color_layout.addWidget(self.extraction_highlight_color_button)
        layout.addRow("Extraction Highlight Color:", color_widget)

        appearance_widget.setLayout(layout)
        self.tab_widget.addTab(appearance_widget, "Appearance")

    def _create_data_tab(self):
        data_widget = QWidget()
        layout = QFormLayout(data_widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Default Collection Path
        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0,0,0,0)
        self.default_collection_path_edit = QLineEdit()
        self.default_collection_path_edit.setPlaceholderText("~/Documents/IromoCollections") # Default
        self.default_collection_path_button = QPushButton("Browse...")
        # Connection for QFileDialog to be added in logic implementation phase
        path_layout.addWidget(self.default_collection_path_edit)
        path_layout.addWidget(self.default_collection_path_button)
        layout.addRow("Default Collection Path:", path_widget)

        # Autosave Interval
        self.autosave_interval_combo = QComboBox()
        # Values: 0, 1, 2, 5, 10, 15, 30
        self.autosave_interval_combo.addItems([
            "0 (Disabled)", "1 minute", "2 minutes", "5 minutes",
            "10 minutes", "15 minutes", "30 minutes"
        ])
        layout.addRow("Autosave Interval:", self.autosave_interval_combo)

        # Recent Collections Count
        self.recent_collections_count_spinbox = QSpinBox()
        self.recent_collections_count_spinbox.setRange(0, 20)
        layout.addRow("Max Recent Collections:", self.recent_collections_count_spinbox)

        data_widget.setLayout(layout)
        self.tab_widget.addTab(data_widget, "Data")

    def _create_behavior_tab(self):
        behavior_widget = QWidget()
        layout = QFormLayout(behavior_widget)

        # Default Topic Title Length
        self.default_topic_title_length_spinbox = QSpinBox()
        self.default_topic_title_length_spinbox.setRange(10, 100)
        layout.addRow("Default Topic Title Length:", self.default_topic_title_length_spinbox)

        # Confirm Topic Deletion
        self.confirm_topic_deletion_checkbox = QCheckBox("Confirm before deleting topics")
        layout.addRow(self.confirm_topic_deletion_checkbox)

        # Open Last Collection on Startup
        self.open_last_collection_checkbox = QCheckBox("Open last used collection on startup")
        layout.addRow(self.open_last_collection_checkbox)

        # Show Welcome on Startup
        self.show_welcome_checkbox = QCheckBox("Show welcome screen on startup")
        layout.addRow(self.show_welcome_checkbox)

        behavior_widget.setLayout(layout)
        self.tab_widget.addTab(behavior_widget, "Behavior")

    def _create_logging_tab(self):
        logging_widget = QWidget()
        layout = QFormLayout(logging_widget)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Log Level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        layout.addRow("Log Level:", self.log_level_combo)

        # Log File Path (Display only)
        self.log_file_path_edit = QLineEdit()
        self.log_file_path_edit.setReadOnly(True)
        self.log_file_path_edit.setPlaceholderText("(Application managed)")
        layout.addRow("Log File Path:", self.log_file_path_edit)

        logging_widget.setLayout(layout)
        self.tab_widget.addTab(logging_widget, "Logging")

    def load_settings(self):
        # Appearance Tab
        self.theme_combo.setCurrentText(self.settings.value("ui/theme", "System Default"))

        default_editor_font_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        editor_font_family = self.settings.value("ui/editor_font_family", default_editor_font_family)
        self.editor_font_family_combo.setCurrentFont(QFont(editor_font_family))
        self.editor_font_size_spinbox.setValue(self.settings.value("ui/editor_font_size", 12, type=int))

        default_tree_font_family = QApplication.font().family() # System UI font
        tree_font_family = self.settings.value("ui/tree_font_family", default_tree_font_family)
        self.tree_font_family_combo.setCurrentFont(QFont(tree_font_family))
        self.tree_font_size_spinbox.setValue(self.settings.value("ui/tree_font_size", 10, type=int))

        self.extraction_highlight_color_edit.setText(self.settings.value("ui/extraction_highlight_color", "#ADD8E6"))

        # Data Tab
        default_collection_path = os.path.expanduser("~/Documents/IromoCollections")
        self.default_collection_path_edit.setText(self.settings.value("data/default_collection_path", default_collection_path))

        saved_autosave_interval = self.settings.value("data/autosave_interval_minutes", 5, type=int)
        try:
            idx = self.autosave_values.index(saved_autosave_interval)
            self.autosave_interval_combo.setCurrentIndex(idx)
        except ValueError: # Fallback to default if saved value is not in our list
            default_idx = self.autosave_values.index(5) # Default to 5 minutes
            self.autosave_interval_combo.setCurrentIndex(default_idx)

        self.recent_collections_count_spinbox.setValue(self.settings.value("data/recent_collections_count", 10, type=int))

        # Behavior Tab
        self.default_topic_title_length_spinbox.setValue(self.settings.value("behavior/default_topic_title_length", 50, type=int))
        self.confirm_topic_deletion_checkbox.setChecked(self.settings.value("behavior/confirm_topic_deletion", True, type=bool))
        self.open_last_collection_checkbox.setChecked(self.settings.value("behavior/open_last_collection_on_startup", True, type=bool))
        self.show_welcome_checkbox.setChecked(self.settings.value("behavior/show_welcome_on_startup", True, type=bool))

        # Logging Tab
        self.log_level_combo.setCurrentText(self.settings.value("logging/log_level", "INFO"))
        # log_file_path is managed elsewhere, typically just displayed

    def save_settings(self):
        # Appearance Tab
        self.settings.setValue("ui/theme", self.theme_combo.currentText())
        self.settings.setValue("ui/editor_font_family", self.editor_font_family_combo.currentFont().family())
        self.settings.setValue("ui/editor_font_size", self.editor_font_size_spinbox.value())
        self.settings.setValue("ui/tree_font_family", self.tree_font_family_combo.currentFont().family())
        self.settings.setValue("ui/tree_font_size", self.tree_font_size_spinbox.value())
        self.settings.setValue("ui/extraction_highlight_color", self.extraction_highlight_color_edit.text())

        # Data Tab
        self.settings.setValue("data/default_collection_path", self.default_collection_path_edit.text())
        current_autosave_idx = self.autosave_interval_combo.currentIndex()
        if 0 <= current_autosave_idx < len(self.autosave_values):
            self.settings.setValue("data/autosave_interval_minutes", self.autosave_values[current_autosave_idx])
        self.settings.setValue("data/recent_collections_count", self.recent_collections_count_spinbox.value())

        # Behavior Tab
        self.settings.setValue("behavior/default_topic_title_length", self.default_topic_title_length_spinbox.value())
        self.settings.setValue("behavior/confirm_topic_deletion", self.confirm_topic_deletion_checkbox.isChecked())
        self.settings.setValue("behavior/open_last_collection_on_startup", self.open_last_collection_checkbox.isChecked())
        self.settings.setValue("behavior/show_welcome_on_startup", self.show_welcome_checkbox.isChecked())

        # Logging Tab
        self.settings.setValue("logging/log_level", self.log_level_combo.currentText())

    def apply_settings(self):
        # Store old values to check for changes, or simply emit if simpler for now
        # For simplicity, we'll emit signals for all relevant settings.
        # A more optimized approach would check if the value actually changed.

        old_theme = self.settings.value("ui/theme")
        old_editor_font_family = self.settings.value("ui/editor_font_family")
        old_editor_font_size = self.settings.value("ui/editor_font_size", type=int)
        old_tree_font_family = self.settings.value("ui/tree_font_family")
        old_tree_font_size = self.settings.value("ui/tree_font_size", type=int)
        old_extraction_highlight_color = self.settings.value("ui/extraction_highlight_color")
        old_default_collection_path = self.settings.value("data/default_collection_path")
        old_autosave_interval = self.settings.value("data/autosave_interval_minutes", type=int)
        old_recent_collections_count = self.settings.value("data/recent_collections_count", type=int)
        old_default_topic_title_length = self.settings.value("behavior/default_topic_title_length", type=int)
        old_confirm_topic_deletion = self.settings.value("behavior/confirm_topic_deletion", type=bool)
        old_open_last_collection = self.settings.value("behavior/open_last_collection_on_startup", type=bool)
        old_show_welcome = self.settings.value("behavior/show_welcome_on_startup", type=bool)
        old_log_level = self.settings.value("logging/log_level")

        self.save_settings()

        new_theme = self.theme_combo.currentText()
        if old_theme != new_theme:
            self.theme_changed.emit(new_theme)

        new_editor_font_family = self.editor_font_family_combo.currentFont().family()
        new_editor_font_size = self.editor_font_size_spinbox.value()
        if old_editor_font_family != new_editor_font_family or old_editor_font_size != new_editor_font_size:
            self.editor_font_changed.emit(new_editor_font_family, new_editor_font_size)

        new_tree_font_family = self.tree_font_family_combo.currentFont().family()
        new_tree_font_size = self.tree_font_size_spinbox.value()
        if old_tree_font_family != new_tree_font_family or old_tree_font_size != new_tree_font_size:
            self.tree_font_changed.emit(new_tree_font_family, new_tree_font_size)

        new_extraction_highlight_color = self.extraction_highlight_color_edit.text()
        if old_extraction_highlight_color != new_extraction_highlight_color:
            self.extraction_highlight_color_changed.emit(new_extraction_highlight_color)

        new_default_collection_path = self.default_collection_path_edit.text()
        if old_default_collection_path != new_default_collection_path:
            self.default_collection_path_changed.emit(new_default_collection_path)

        current_autosave_idx = self.autosave_interval_combo.currentIndex()
        new_autosave_interval = self.autosave_values[current_autosave_idx] if 0 <= current_autosave_idx < len(self.autosave_values) else old_autosave_interval
        if old_autosave_interval != new_autosave_interval:
            self.autosave_interval_changed.emit(new_autosave_interval)

        new_recent_collections_count = self.recent_collections_count_spinbox.value()
        if old_recent_collections_count != new_recent_collections_count:
            self.recent_collections_count_changed.emit(new_recent_collections_count)
        
        new_default_topic_title_length = self.default_topic_title_length_spinbox.value()
        if old_default_topic_title_length != new_default_topic_title_length:
            self.default_topic_title_length_changed.emit(new_default_topic_title_length)

        new_confirm_topic_deletion = self.confirm_topic_deletion_checkbox.isChecked()
        if old_confirm_topic_deletion != new_confirm_topic_deletion:
            self.confirm_topic_deletion_changed.emit(new_confirm_topic_deletion)

        new_open_last_collection = self.open_last_collection_checkbox.isChecked()
        if old_open_last_collection != new_open_last_collection:
            self.open_last_collection_on_startup_changed.emit(new_open_last_collection)

        new_show_welcome = self.show_welcome_checkbox.isChecked()
        if old_show_welcome != new_show_welcome:
            self.show_welcome_on_startup_changed.emit(new_show_welcome)

        new_log_level = self.log_level_combo.currentText()
        if old_log_level != new_log_level:
            self.log_level_changed.emit(new_log_level)

        print("Settings applied, saved, and signals emitted.")

    def accept_settings(self):
        self.apply_settings()
        self.accept() # Closes the dialog with QDialog.Accepted

    def _create_shortcuts_tab(self):
        shortcuts_widget = QWidget()
        layout = QVBoxLayout(shortcuts_widget)

        self.shortcuts_table = QTableWidget()
        self.shortcuts_table.setColumnCount(4)
        self.shortcuts_table.setHorizontalHeaderLabels(["Action", "Current Shortcut", "Default", ""])
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.shortcuts_table.verticalHeader().setVisible(False)
        # self.shortcuts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # Handled by cell widgets

        layout.addWidget(self.shortcuts_table)

        restore_all_button = QPushButton("Restore All Default Shortcuts")
        restore_all_button.clicked.connect(self._restore_all_shortcuts)
        layout.addWidget(restore_all_button)

        shortcuts_widget.setLayout(layout)
        self.tab_widget.addTab(shortcuts_widget, "Shortcuts")
        self._populate_shortcuts_table()

    def _populate_shortcuts_table(self):
        if not self.data_manager:
            # Handle case where data_manager might not be available (e.g. no collection open)
            # For now, clear the table if it exists
            if hasattr(self, 'shortcuts_table'):
                self.shortcuts_table.setRowCount(0)
            return

        self.shortcuts_table.setRowCount(0) # Clear existing rows
        
        # Get actions from default_shortcuts to ensure all defined actions are listed
        action_ids = sorted(self.data_manager.default_shortcuts.keys())

        for action_id in action_ids:
            action_name = self._get_action_descriptive_name(action_id)
            current_shortcut_str = self.data_manager.get_shortcut(action_id) # This handles fallback to default
            default_shortcut_str = self.data_manager.default_shortcuts.get(action_id, "")

            row_position = self.shortcuts_table.rowCount()
            self.shortcuts_table.insertRow(row_position)

            # Action Name (read-only)
            action_item = QTableWidgetItem(action_name)
            action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.shortcuts_table.setItem(row_position, 0, action_item)

            # Current Shortcut (editable via QKeySequenceEdit)
            key_sequence_edit = QKeySequenceEdit(QKeySequence.fromString(current_shortcut_str, QKeySequence.SequenceFormat.NativeText))
            key_sequence_edit.editingFinished.connect(
                # Use a lambda with default argument binding to capture current action_id and widget
                lambda bound_action_id=action_id, edit_widget=key_sequence_edit: \
                self._handle_shortcut_edited(bound_action_id, edit_widget)
            )
            self.shortcuts_table.setCellWidget(row_position, 1, key_sequence_edit)

            # Default Shortcut (read-only)
            default_item = QTableWidgetItem(default_shortcut_str)
            default_item.setFlags(default_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.shortcuts_table.setItem(row_position, 2, default_item)

            # Restore Button
            restore_button = QPushButton("Restore")
            restore_button.clicked.connect(
                lambda checked=False, bound_action_id=action_id: self._restore_shortcut(bound_action_id)
            )
            self.shortcuts_table.setCellWidget(row_position, 3, restore_button)
        
        self.shortcuts_table.resizeColumnsToContents()
        if self.shortcuts_table.columnCount() > 0: # Ensure column 0 exists
            self.shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)


    def _get_action_descriptive_name(self, action_id: str) -> str:
        """Converts an action_id like 'file.open_collection' to 'Open Collection'."""
        try:
            # Take the part after the first dot, or the whole string if no dot
            name_part = action_id.split('.', 1)[-1]
            return ' '.join(word.capitalize() for word in name_part.split('_'))
        except Exception:
            return action_id # Fallback

    def _handle_shortcut_edited(self, action_id: str, key_sequence_edit_widget: QKeySequenceEdit):
        if not self.data_manager: return
        new_key_sequence = key_sequence_edit_widget.keySequence()
        new_shortcut_str = new_key_sequence.toString(QKeySequence.SequenceFormat.NativeText)
        
        # Optional: Check for conflicts before setting
        # For now, directly set it. DataManager might handle conflicts or log issues.
        success = self.data_manager.set_shortcut(action_id, new_shortcut_str)
        if not success:
            # If set_shortcut indicates failure (e.g. conflict, DB error)
            QMessageBox.warning(self, "Shortcut Conflict",
                                f"Could not set shortcut '{new_shortcut_str}' for '{self._get_action_descriptive_name(action_id)}'. "
                                "It might conflict with another shortcut or an error occurred.")
            # Re-populate to show the actual current state, which might be the old shortcut
            self._populate_shortcuts_table()
        # If successful, the shortcuts_changed signal from DataManager should trigger a refresh.
        # However, set_shortcut itself might not emit if only one shortcut changed and it wants to batch.
        # For immediate feedback on this specific edit, we can repopulate, or rely on DataManager's signal.
        # Let's assume DataManager.shortcuts_changed will be emitted.

    def _restore_shortcut(self, action_id: str):
        if not self.data_manager: return
        self.data_manager.reset_shortcut(action_id)
        # The shortcuts_changed signal from DataManager will trigger _populate_shortcuts_table

    def _restore_all_shortcuts(self):
        if not self.data_manager: return
        confirm = QMessageBox.question(self, "Restore All Shortcuts",
                                       "Are you sure you want to restore all shortcuts to their default values?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.data_manager.reset_all_shortcuts()
            # The shortcuts_changed signal from DataManager will trigger _populate_shortcuts_table

if __name__ == '__main__':
    # This example will not work directly without a DataManager instance.
    # For testing, you'd need to mock or create a dummy DataManager.
    app = QApplication(sys.argv)
    
    # --- Dummy DataManager for standalone testing ---
    class DummyDataManager(QObject):
        shortcuts_changed = pyqtSignal()
        def __init__(self):
            super().__init__()
            self.default_shortcuts = {
                "app.quit": "Ctrl+Q",
                "file.new_topic": "Ctrl+N",
                "file.save_topic": "Ctrl+S",
            }
            self._custom_shortcuts = {}
        def get_shortcut(self, action_id):
            return self._custom_shortcuts.get(action_id, self.default_shortcuts.get(action_id))
        def get_all_shortcuts(self): # Not directly used by populate, but good for DM interface
            all_sc = {}
            for action_id, default_sc in self.default_shortcuts.items():
                all_sc[action_id] = self._custom_shortcuts.get(action_id, default_sc)
            return all_sc
        def set_shortcut(self, action_id, shortcut_str):
            print(f"DummyDM: Setting {action_id} to {shortcut_str}")
            # Check for simple conflict for testing warning
            for k, v in self._custom_shortcuts.items():
                if k != action_id and v == shortcut_str:
                    print(f"DummyDM: Conflict detected for {shortcut_str}")
                    return False # Simulate conflict
            for k, v in self.default_shortcuts.items():
                 if k != action_id and v == shortcut_str and k not in self._custom_shortcuts : # if default is this and not overridden
                    # This conflict logic is a bit simplistic for a dummy
                    pass


            self._custom_shortcuts[action_id] = shortcut_str
            self.shortcuts_changed.emit()
            return True
        def reset_shortcut(self, action_id):
            print(f"DummyDM: Resetting {action_id}")
            if action_id in self._custom_shortcuts:
                del self._custom_shortcuts[action_id]
            self.shortcuts_changed.emit()
            return True
        def reset_all_shortcuts(self):
            print("DummyDM: Resetting all shortcuts")
            self._custom_shortcuts.clear()
            self.shortcuts_changed.emit()
            return True
    # --- End Dummy DataManager ---

    # Create the application and the dialog with the dummy manager
    dummy_dm = DummyDataManager()
    dialog = SettingsDialog(data_manager=dummy_dm) # Pass the dummy_dm
    dialog.show()
    sys.exit(app.exec())