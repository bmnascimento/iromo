import logging
import os # For __main__ test

from PyQt6.QtCore import Qt, pyqtSignal, QItemSelectionModel
from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel, QKeyEvent, QAction
from PyQt6.QtWidgets import QAbstractItemView, QTreeView, QMessageBox, QMenu, QInputDialog
 
from .data_manager import DataManager # Import the DataManager class
from .commands.topic_commands import DeleteMultipleTopicsCommand, CreateTopicCommand # Import the command

logger = logging.getLogger(__name__)

class KnowledgeTreeWidget(QTreeView):
    topic_selected = pyqtSignal(str) # topic_id
    # Emits topic_id, old_title (fetched by MainWindow), new_title
    topic_title_changed = pyqtSignal(str, str, str) # topic_id, old_title, new_title

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Allows multiple items to be selected

        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.model.setHorizontalHeaderLabels(['Topic Title']) # Set header early
        
        self.model.itemChanged.connect(self._handle_item_changed)
        self.selectionModel().selectionChanged.connect(self._handle_selection_changed)

        self._topic_item_map = {} # Maps topic_id to QStandardItem
        self._editing_item_old_title = None # Store title before editing starts
        self.data_manager: DataManager = None # Will be set by load_tree_data
        
        # load_tree is no longer called here; MainWindow will call load_tree_data

    def clear_tree(self):
        """Clears all items from the tree and resets the internal map."""
        self.model.clear()
        self._topic_item_map = {}
        # Set column count and header data again after clearing
        self.model.setHorizontalHeaderLabels(['Topic Title'])
        # Add placeholder when tree is empty and no collection is loaded
        logger.info("clear_tree: Called")
        placeholder_text = "No collection open or collection is empty."
        logger.info(f"clear_tree: Requesting placeholder: '{placeholder_text}'") # Adjusted log
        self._add_placeholder_if_empty(placeholder_text)


    def _add_placeholder_if_empty(self, text="No topics yet. Add one!"):
        """Adds or updates a placeholder item if the tree would otherwise be empty."""
        logger.info(f"_add_placeholder_if_empty: Called with text: '{text}'. Current rowCount: {self.model.rowCount()}")
        if self.model.rowCount() == 0:
            logger.info(f"_add_placeholder_if_empty: rowCount is 0. Adding new placeholder: '{text}'")
            placeholder_item = QStandardItem(text)
            placeholder_item.setEditable(False)
            placeholder_item.setEnabled(False) # Grayed out
            self.model.appendRow(placeholder_item)
        elif self.model.rowCount() == 1:
            item = self.model.item(0)
            if item and item.data(Qt.ItemDataRole.UserRole) is None: # It's a placeholder
                old_text = item.text()
                logger.info(f"_add_placeholder_if_empty: rowCount is 1 and item is placeholder. Updating text from '{old_text}' to '{text}'")
                item.setText(text)
                item.setEditable(False) # Ensure it remains non-editable
                item.setEnabled(False) # Ensure it remains disabled
            else:
                logger.info(f"_add_placeholder_if_empty: rowCount is 1, but not a recognized placeholder (item text: '{item.text() if item else 'None'}'). Doing nothing.")
        else:
            logger.info(f"_add_placeholder_if_empty: rowCount is {self.model.rowCount()}. Not a candidate for placeholder. Doing nothing.")

    def load_tree_data(self, data_manager_instance: DataManager):
        """Loads the topic hierarchy from the given DataManager instance and populates the tree."""
        logger.info(f"load_tree_data: Called. DataManager instance present: {data_manager_instance is not None}")
        if not data_manager_instance:
            logger.warning("load_tree_data: No DataManager instance provided.")
            self.data_manager = None # Clear if invalid instance is passed
            self.clear_tree() # Show "No collection open..."
            return
        
        self.data_manager = data_manager_instance # Store the data manager instance

        self.clear_tree() # Clear previous content and placeholder
        topics_data = self.data_manager.get_topic_hierarchy()
        logger.info(f"load_tree_data: Fetched topics_data. Length: {len(topics_data) if topics_data else 'None'}")

        # If actual topics are being loaded, remove the default placeholder set by clear_tree()
        if topics_data:
            if self.model.rowCount() == 1:
                first_item = self.model.item(0)
                # Check if it's a placeholder (no UserRole data)
                if first_item and first_item.data(Qt.ItemDataRole.UserRole) is None:
                    logger.info("load_tree_data: Actual topics found, removing placeholder set by clear_tree.")
                    self.model.removeRow(0)
        
        items = {}
        children_map = {}

        for topic_d in topics_data:
            item = QStandardItem(topic_d['title'])
            item.setData(topic_d['id'], Qt.ItemDataRole.UserRole)
            item.setEditable(True)
            items[topic_d['id']] = item
            self._topic_item_map[topic_d['id']] = item
            
            parent_id = topic_d.get('parent_id')
            if parent_id:
                if parent_id not in children_map:
                    children_map[parent_id] = []
                children_map[parent_id].append(item)

        root_items = []
        for topic_d in topics_data:
            item = items[topic_d['id']]
            parent_id = topic_d.get('parent_id')
            if parent_id is None:
                root_items.append(item)
            # Children are attached below based on children_map

        for parent_id, child_items_list in children_map.items():
            if parent_id in items:
                parent_item = items[parent_id]
                for child_item in child_items_list:
                    parent_item.appendRow(child_item)
            else: # Orphaned children (parent_id exists but parent item not found in current batch)
                logger.warning(f"Orphaned children found for parent_id {parent_id}. Adding them as roots.")
                for child_item in child_items_list: # Add them as roots
                    root_items.append(child_item)


        for root_item in root_items:
            self.model.appendRow(root_item)
            
        
        self.expandAll() # Optionally expand all items after loading

    def _handle_item_changed(self, item: QStandardItem):
        # This signal is emitted *after* the item's data (text) has changed.
        topic_id = item.data(Qt.ItemDataRole.UserRole)
        new_title = item.text()

        if topic_id and self._editing_item_old_title is not None:
            if new_title != self._editing_item_old_title:
                logger.info(f"Tree item changed: ID {topic_id}, Old: '{self._editing_item_old_title}', New: '{new_title}'")
                self.topic_title_changed.emit(topic_id, self._editing_item_old_title, new_title)
            else:
                logger.info(f"Tree item data changed but title remained the same for {topic_id}: '{new_title}'")
        elif topic_id:
            # This case might happen if itemChanged is triggered for reasons other than text edit completion,
            # or if _editing_item_old_title was not set.
            # For robustness, we could fetch the "current" title from data_manager as old_title if needed,
            # but that's best handled by the command creator (MainWindow).
            # For now, we rely on _editing_item_old_title being set.
            logger.warning(f"Item {topic_id} changed, but old title was not captured. New title: '{new_title}'")

        self._editing_item_old_title = None # Reset after processing

    def edit(self, index, trigger, event):
        # Override edit to capture the old title before editing begins
        if index.isValid() and trigger != QAbstractItemView.EditTrigger.NoEditTriggers:
            item = self.model.itemFromIndex(index)
            if item and item.isEditable():
                self._editing_item_old_title = item.text()
                logger.debug(f"Starting edit for item '{self._editing_item_old_title}', topic_id: {item.data(Qt.ItemDataRole.UserRole)}")
        return super().edit(index, trigger, event)

    def _handle_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            selected_item = self.model.itemFromIndex(indexes[0])
            if selected_item:
                topic_id = selected_item.data(Qt.ItemDataRole.UserRole)
                if topic_id: # Ensure it's a topic item, not a placeholder
                    logger.debug(f"Tree selection changed: Topic ID {topic_id}")
                    self.topic_selected.emit(topic_id)
                # else:
                    # logger.debug("Placeholder item selected.")
        # else:
            # logger.debug("Tree selection cleared or invalid.")


    def add_topic_item(self, title: str, topic_id: str, parent_id: str = None):
        logger.info(f"add_topic_item: Called with title='{title}', topic_id='{topic_id}', parent_id='{parent_id}'")
        logger.info(f"add_topic_item: Current model rowCount before placeholder check: {self.model.rowCount()}")
        # Remove placeholder if it exists and is the only item
        if self.model.rowCount() == 1:
            first_item = self.model.item(0)
            if first_item: # Ensure item exists
                first_item_data = first_item.data(Qt.ItemDataRole.UserRole)
                first_item_text = first_item.text()
                logger.info(f"add_topic_item: Checking placeholder. rowCount is 1. First item text: '{first_item_text}', data: {first_item_data}")
                if first_item_data is None: # Likely a placeholder
                    logger.info("add_topic_item: Placeholder detected (rowCount=1, item data is None). Removing row 0.")
                    self.model.removeRow(0)
                else:
                    logger.info("add_topic_item: rowCount is 1, but first item has data. Not a placeholder by this check.")
            else:
                logger.warning("add_topic_item: rowCount is 1, but model.item(0) is None. Cannot check for placeholder.")
        elif self.model.rowCount() == 0:
            logger.info("add_topic_item: model rowCount is 0. No placeholder to remove.")
        else:
            logger.info(f"add_topic_item: model rowCount is {self.model.rowCount()}. Not attempting placeholder removal.")

        item = QStandardItem(title)
        item.setData(topic_id, Qt.ItemDataRole.UserRole)
        item.setEditable(True)
        self._topic_item_map[topic_id] = item

        if parent_id and parent_id in self._topic_item_map:
            parent_item = self._topic_item_map[parent_id]
            parent_item.appendRow(item)
            self.expand(parent_item.index())
        else:
            self.model.appendRow(item)
        
        self.setCurrentIndex(item.index())
        return item

    def update_topic_item_title(self, topic_id: str, new_title: str):
        if topic_id in self._topic_item_map:
            item = self._topic_item_map[topic_id]
            # Temporarily disconnect itemChanged signal
            try:
                self.model.itemChanged.disconnect(self._handle_item_changed)
            except TypeError: 
                pass 
            item.setText(new_title)
            try:
                self.model.itemChanged.connect(self._handle_item_changed)
            except TypeError:
                pass 
        else:
            logger.warning(f"Tried to update title for non-existent item in tree: {topic_id}")

    def get_selected_topic_id(self):
        current_index = self.currentIndex()
        if current_index.isValid():
            item = self.model.itemFromIndex(current_index)
            if item:
                return item.data(Qt.ItemDataRole.UserRole) # Returns None if not a topic item
        return None
    
    def get_current_selected_topic_id(self):
        """Returns the topic_id of the currently selected item, or None."""
        return self.get_selected_topic_id() # Alias for clarity/consistency

    def select_topic_item(self, topic_id: str):
        """Selects the tree item corresponding to the given topic_id."""
        if topic_id in self._topic_item_map:
            item = self._topic_item_map[topic_id]
            self.setCurrentIndex(item.index())
            self.scrollTo(item.index(), QAbstractItemView.ScrollHint.PositionAtCenter)
        else:
            logger.warning(f"Cannot select topic item: ID {topic_id} not found in tree map.")

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events, specifically the Delete key."""
        if event.key() == Qt.Key.Key_Delete:
            selected_indexes = self.selectionModel().selectedIndexes()
            
            # We only care about column 0 for items
            # and QTreeView can return indexes for all columns for a selected row.
            # Filter to get unique items based on column 0.
            unique_items_to_delete = []
            seen_items = set()

            if selected_indexes:
                topic_ids_to_delete = []
                for index in selected_indexes:
                    if index.column() == 0: # Process only one index per row (e.g., from column 0)
                        item = self.model.itemFromIndex(index)
                        if item: # Ensure item is valid
                            topic_id = item.data(Qt.ItemDataRole.UserRole)
                            if topic_id and topic_id not in seen_items: # Ensure it's a real topic and not already processed
                                topic_ids_to_delete.append(topic_id)
                                unique_items_to_delete.append(item) # For logging or further checks if needed
                                seen_items.add(topic_id)
                
                if topic_ids_to_delete:
                    logger.info(f"Delete key pressed. Topics to delete: {topic_ids_to_delete}")

                    # Confirmation Dialog
                    reply = QMessageBox.question(self, 'Confirm Deletion',
                                                 f"Are you sure you want to delete {len(topic_ids_to_delete)} topic(s)?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                 QMessageBox.StandardButton.No)

                    if reply == QMessageBox.StandardButton.Yes:
                        logger.info(f"User confirmed deletion for topics: {topic_ids_to_delete}")
                        if not self.data_manager:
                            logger.error("Cannot delete topics: DataManager not available.")
                            return

                        # Access UndoManager, assuming it's on the main window
                        undo_manager = None
                        if hasattr(self.window(), 'undo_manager'):
                            undo_manager = self.window().undo_manager
                        
                        if not undo_manager:
                            logger.error("Cannot delete topics: UndoManager not available.")
                            return

                        command = DeleteMultipleTopicsCommand(self.data_manager, topic_ids_to_delete)
                        undo_manager.execute_command(command)
                        # If push_command doesn't execute, then:
                        # undo_manager.execute_command(command) or command.execute(); undo_manager.add_command(command)
                        # Based on typical UndoManager patterns, push_command often implies execute + add to stack.
                        # Let's assume `push_command` handles execution. If not, this needs adjustment.
                        logger.info(f"Executed DeleteMultipleTopicsCommand for IDs: {topic_ids_to_delete}")
                    else:
                        logger.info(f"User cancelled deletion for topics: {topic_ids_to_delete}")
                else:
                    logger.debug("Delete key pressed, but no valid topic items selected.")
            else:
                logger.debug("Delete key pressed, but no items selected.")
            event.accept() # Indicate event was handled
        else:
            super().keyPressEvent(event) # Pass to parent for other keys

    def contextMenuEvent(self, event):
        """Handles context menu requests for the tree view."""
        logger.debug("contextMenuEvent triggered.")
        selected_index = self.indexAt(event.pos())
        menu = QMenu(self)

        # Placeholder actions
        add_child_action = QAction("Add Child", self)
        add_child_action.triggered.connect(self._handle_add_child)
        menu.addAction(add_child_action)

        add_sibling_action = QAction("Add Sibling", self)
        add_sibling_action.triggered.connect(self._handle_add_sibling)
        menu.addAction(add_sibling_action)

        # Only show menu if there's an item, or always show for broader actions?
        # For now, let's assume we always want to show it if the tree itself is right-clicked.
        # If we only want it on items:
        # if selected_index.isValid():
        #     item = self.model.itemFromIndex(selected_index)
        #     if item and item.data(Qt.ItemDataRole.UserRole) is not None: # Is a real topic
        #         menu.exec(event.globalPos())
        # else:
        #     # Context menu on empty area - perhaps only "Add Root Topic"?
        #     # For now, let's keep it simple and show for any right click.
        #     pass
        
        # Show the menu if there are actions.
        # We might want to disable actions if no item is selected, or if a placeholder is selected.
        is_item_selected = selected_index.isValid()
        is_placeholder_selected = False
        if is_item_selected:
            item = self.model.itemFromIndex(selected_index)
            if item and item.data(Qt.ItemDataRole.UserRole) is None: # It's a placeholder
                is_placeholder_selected = True
        
        # Disable actions if no item is selected or if a placeholder is selected
        if not is_item_selected or is_placeholder_selected:
            add_child_action.setEnabled(False)
            add_sibling_action.setEnabled(False)
            # Potentially add a "Add Root Topic" action here if desired for empty space clicks

        if menu.actions(): # Only show if there are actions to show
            menu.exec(event.globalPos())
        else:
            logger.debug("No actions in context menu, not showing.")

    def _handle_add_child(self):
        """Handles adding a child topic to the selected topic."""
        parent_topic_id = self.get_selected_topic_id()
        if not parent_topic_id:
            logger.warning("Add Child: No parent topic selected.")
            QMessageBox.warning(self, "Add Child", "Please select a parent topic first.")
            return

        # Prompt for the new topic name
        child_topic_name, ok = QInputDialog.getText(self, "Add Child Topic", "Enter name for the new child topic:")

        if ok and child_topic_name:
            logger.info(f"Attempting to add child topic '{child_topic_name}' to parent '{parent_topic_id}'.")
            
            if not self.data_manager:
                logger.error("Cannot add child topic: DataManager not available.")
                QMessageBox.critical(self, "Error", "DataManager is not available. Cannot add topic.")
                return

            undo_manager = None
            if hasattr(self.window(), 'undo_manager'):
                undo_manager = self.window().undo_manager
            
            if not undo_manager:
                logger.error("Cannot add child topic: UndoManager not available.")
                QMessageBox.critical(self, "Error", "UndoManager is not available. Cannot add topic.")
                return

            command = CreateTopicCommand(
                data_manager=self.data_manager,
                parent_id=parent_topic_id,
                custom_title=child_topic_name,
                text_content="" # Child topics start with empty content by default
            )
            
            try:
                undo_manager.execute_command(command) # Assumes execute_command also adds to stack
                logger.info(f"Executed CreateTopicCommand for new child '{child_topic_name}' under parent '{parent_topic_id}'.")
                # The KnowledgeTreeWidget should update automatically if it's listening to
                # DataManager.topic_created signal (typically via MainWindow).
                # If direct refresh is needed and not handled by signals:
                # self.load_tree_data(self.data_manager) # Or a more targeted update
            except Exception as e:
                logger.error(f"Error executing CreateTopicCommand: {e}")
                QMessageBox.critical(self, "Error", f"Failed to add child topic: {e}")
        elif ok and not child_topic_name:
            logger.info("Add Child: User provided an empty name.")
            QMessageBox.information(self, "Add Child", "Topic name cannot be empty.")
        else:
            logger.info("Add Child: User cancelled the dialog.")

    def _handle_add_sibling(self):
        """Handles adding a sibling topic to the selected topic."""
        current_index = self.currentIndex()
        if not current_index.isValid():
            logger.warning("Add Sibling: No item selected.")
            QMessageBox.warning(self, "Add Sibling", "Please select an item in the tree first.")
            return

        selected_item = self.model.itemFromIndex(current_index)
        if not selected_item or selected_item.data(Qt.ItemDataRole.UserRole) is None:
            logger.warning("Add Sibling: Selected item is not a valid topic (e.g., placeholder).")
            QMessageBox.warning(self, "Add Sibling", "Please select a valid topic to add a sibling to.")
            return

        # Determine the parent for the new sibling
        parent_item = selected_item.parent()
        sibling_parent_id = None
        if parent_item: # Selected item has a parent, so sibling shares this parent
            sibling_parent_id = parent_item.data(Qt.ItemDataRole.UserRole)
            if sibling_parent_id is None: # Parent item is somehow not a valid topic (should not happen with valid tree)
                logger.error(f"Add Sibling: Parent item of selected topic '{selected_item.text()}' has no topic ID.")
                QMessageBox.critical(self, "Error", "Could not determine parent for the new sibling topic.")
                return
        else: # Selected item is a root topic, so sibling will also be a root topic
            sibling_parent_id = None
            logger.info(f"Add Sibling: Selected item '{selected_item.text()}' is a root topic. New sibling will also be a root topic.")


        # Prompt for the new topic name
        sibling_topic_name, ok = QInputDialog.getText(self, "Add Sibling Topic", "Enter name for the new sibling topic:")

        if ok and sibling_topic_name:
            logger.info(f"Attempting to add sibling topic '{sibling_topic_name}' with parent_id '{sibling_parent_id}'.")

            if not self.data_manager:
                logger.error("Cannot add sibling topic: DataManager not available.")
                QMessageBox.critical(self, "Error", "DataManager is not available. Cannot add topic.")
                return

            undo_manager = None
            if hasattr(self.window(), 'undo_manager'):
                undo_manager = self.window().undo_manager
            
            if not undo_manager:
                logger.error("Cannot add sibling topic: UndoManager not available.")
                QMessageBox.critical(self, "Error", "UndoManager is not available. Cannot add topic.")
                return

            command = CreateTopicCommand(
                data_manager=self.data_manager,
                parent_id=sibling_parent_id, # This will be None for root topics
                custom_title=sibling_topic_name,
                text_content="" # New topics start with empty content
            )
            
            try:
                undo_manager.execute_command(command)
                logger.info(f"Executed CreateTopicCommand for new sibling '{sibling_topic_name}' (parent ID: {sibling_parent_id}).")
                # Tree updates are expected via signals from DataManager
            except Exception as e:
                logger.error(f"Error executing CreateTopicCommand for sibling: {e}")
                QMessageBox.critical(self, "Error", f"Failed to add sibling topic: {e}")
        elif ok and not sibling_topic_name:
            logger.info("Add Sibling: User provided an empty name.")
            QMessageBox.information(self, "Add Sibling", "Topic name cannot be empty.")
        else:
            logger.info("Add Sibling: User cancelled the dialog.")


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
    # Need UndoManager for the test if we want to test delete
    from src.undo_manager import UndoManager # Assuming path
    import sys
    import shutil # For cleaning up test directory

    # Dummy DataManager for standalone testing
    # Needs to be instantiated with a path
    class DummyDataManagerForTreeTest(DataManager):
        def __init__(self, collection_base_path):
            # Create the dummy collection path for the test
            self.test_collection_dir = collection_base_path
            if not os.path.exists(self.test_collection_dir):
                os.makedirs(self.test_collection_dir)
            
            # Create dummy migrations dir and file for DataManager init
            # This setup is more involved now that DataManager handles its own migrations dir
            self.app_migrations_dir = "temp_test_migrations_for_tree"
            if not os.path.exists(self.app_migrations_dir):
                os.makedirs(self.app_migrations_dir)
            
            dummy_mig_file = os.path.join(self.app_migrations_dir, "000_dummy.sql")
            if not os.path.exists(dummy_mig_file):
                 with open(dummy_mig_file, "w") as f: f.write("-- test")
            
            # Call parent DataManager's init, but override migrations_dir for the test
            super().__init__(collection_base_path)
            self.migrations_dir = self.app_migrations_dir # Point to our temp app migrations
            
            # Initialize the dummy collection (creates DB, text_files dir)
            try:
                self.initialize_collection_storage()
            except Exception as e:
                logger.error(f"Error initializing DummyDataManagerForTreeTest storage: {e}")
                # Depending on test needs, might raise e or log and continue

            self.topics = [
                {'id': 'root1', 'title': 'Root Topic 1', 'parent_id': None, 'created_at': '2023-01-01T10:00:00'},
                {'id': 'child1_1', 'title': 'Child 1.1 (R1)', 'parent_id': 'root1', 'created_at': '2023-01-01T10:01:00'},
                {'id': 'child1_2', 'title': 'Child 1.2 (R1)', 'parent_id': 'root1', 'created_at': '2023-01-01T10:02:00'},
                {'id': 'grandchild1_1_1', 'title': 'Grandchild 1.1.1 (C1.1)', 'parent_id': 'child1_1', 'created_at': '2023-01-01T10:03:00'},
                {'id': 'root2', 'title': 'Root Topic 2 (Empty)', 'parent_id': None, 'created_at': '2023-01-01T10:04:00'},
            ]
            # Simulate writing these to the dummy DB (simplified for test)
            conn = self._get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DROP TABLE IF EXISTS topics") # Ensure clean table
                # Recreate table based on a minimal schema (adapt from your actual migrations)
                cursor.execute("""
                CREATE TABLE topics (
                    id TEXT PRIMARY KEY, 
                    parent_id TEXT, 
                    title TEXT, 
                    text_file_uuid TEXT, 
                    created_at timestamp, 
                    updated_at timestamp,
                    display_order INTEGER
                )""")
                for t in self.topics:
                    cursor.execute("INSERT INTO topics (id, title, parent_id, text_file_uuid, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                                   (t['id'], t['title'], t.get('parent_id'), str(os.urandom(16).hex()), t['created_at'], t['created_at']))
                conn.commit()
            except Exception as e:
                logger.error(f"Error setting up dummy DB for tree test: {e}")
            finally:
                conn.close()


        def get_topic_hierarchy(self):
            # In a real scenario, this would query self.db_path
            # For this dummy, we return the predefined list
            logger.info(f"[DummyDM] get_topic_hierarchy called for {self.collection_base_path}")
            return self.topics

        def update_topic_title(self, topic_id, new_title):
            logger.info(f"[DummyDM] Update title for {topic_id} to '{new_title}' in {self.collection_base_path}")
            # Simulate update in self.topics for consistency if needed for further tests
            for topic in self.topics:
                if topic['id'] == topic_id:
                    topic['title'] = new_title
                    break
            return True
        
        def cleanup_test_dirs(self):
            if os.path.exists(self.test_collection_dir):
                shutil.rmtree(self.test_collection_dir)
                logger.info(f"Cleaned up test collection dir: {self.test_collection_dir}")
            if os.path.exists(self.app_migrations_dir):
                shutil.rmtree(self.app_migrations_dir)
                logger.info(f"Cleaned up test migrations dir: {self.app_migrations_dir}")


    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("Knowledge Tree Widget Test")
    
    central_widget = QWidget()
    main_win.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    # Create a dummy DataManager instance for the test
    test_collection_path = os.path.abspath("temp_tree_widget_test_collection")
    dummy_dm_instance = None
    
    # Dummy UndoManager for the test
    class DummyUndoManager:
        def __init__(self):
            self.stack = []
            logger.info("DummyUndoManager initialized for test.")
        def push_command(self, command):
            logger.info(f"DummyUndoManager: Pushing command: {command.description}")
            try:
                command.execute() # Simulate execution
                self.stack.append(command)
                logger.info(f"DummyUndoManager: Executed and added to stack: {command.description}")
            except Exception as e:
                logger.error(f"DummyUndoManager: Error executing command {command.description}: {e}")

        def undo(self):
            if self.stack:
                command = self.stack.pop()
                logger.info(f"DummyUndoManager: Undoing command: {command.description}")
                try:
                    command.undo()
                except Exception as e:
                    logger.error(f"DummyUndoManager: Error undoing command {command.description}: {e}")
            else:
                logger.info("DummyUndoManager: Undo stack empty.")

    main_win.undo_manager = DummyUndoManager() # Attach to main_win for keyPressEvent to find

    try:
        dummy_dm_instance = DummyDataManagerForTreeTest(test_collection_path)
    
        tree_widget = KnowledgeTreeWidget(parent=main_win) # Pass parent for self.window()
        tree_widget.load_tree_data(dummy_dm_instance) # Load data using the DM instance
        layout.addWidget(tree_widget)

        def test_add_topic():
            new_id_root = f"new_root_{tree_widget.model.rowCount()}"
            tree_widget.add_topic_item(f"New Root Topic {tree_widget.model.rowCount()}", new_id_root, parent_id=None)

        def test_add_child_topic():
            selected_id = tree_widget.get_selected_topic_id()
            if selected_id:
                parent_item = tree_widget._topic_item_map.get(selected_id)
                if parent_item:
                    new_id_child = f"new_child_{parent_item.rowCount()}_of_{selected_id}"
                    tree_widget.add_topic_item(f"New Child {parent_item.rowCount()}", new_id_child, parent_id=selected_id)
            else:
                logger.warning("No parent selected to add child to.")
                
        def test_update_selected_title():
            selected_id = tree_widget.get_selected_topic_id()
            if selected_id:
                tree_widget.update_topic_item_title(selected_id, "TITLE UPDATED EXTERNALLY")
            else:
                logger.warning("No item selected to update title.")
        
        def test_clear_and_reload():
            tree_widget.clear_tree()
            logger.info("Tree cleared. Reloading with placeholder.")
            tree_widget.load_tree_data(dummy_dm_instance)
        
        def test_select_all_and_press_delete():
            logger.info("Simulating select all and pressing Delete...")
            # Select all items. This is a bit manual for QTreeView with QStandardItemModel
            # We'll select the first few items for testing.
            if tree_widget.model.rowCount() > 0:
                # tree_widget.selectAll() # This might work depending on selection behavior
                
                # More explicit selection for testing:
                selection = QItemSelection()
                if tree_widget.model.rowCount() > 0:
                    # Select first root item
                    index0 = tree_widget.model.index(0, 0)
                    selection.select(index0, index0)
                    if tree_widget.model.rowCount() > 1:
                         # Select second root item if exists
                        index1 = tree_widget.model.index(1, 0)
                        selection.select(index1, index1)

                tree_widget.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                
                # Simulate Delete key press
                delete_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
                tree_widget.keyPressEvent(delete_event)
                logger.info("Simulated Delete key press event sent.")
            else:
                logger.info("No items to select for delete test.")


        btn_add_root = QPushButton("Add Root Topic")
        btn_add_root.clicked.connect(test_add_topic)
        layout.addWidget(btn_add_root)
        
        btn_add_child = QPushButton("Add Child to Selected")
        btn_add_child.clicked.connect(test_add_child_topic)
        layout.addWidget(btn_add_child)

        btn_update_title = QPushButton("Update Selected Title Externally")
        btn_update_title.clicked.connect(test_update_selected_title)
        layout.addWidget(btn_update_title)

        btn_clear_reload = QPushButton("Clear and Reload Tree")
        btn_clear_reload.clicked.connect(test_clear_and_reload)
        layout.addWidget(btn_clear_reload)

        btn_test_delete = QPushButton("Test Delete Selected (Simulated)")
        btn_test_delete.clicked.connect(test_select_all_and_press_delete)
        layout.addWidget(btn_test_delete)


        main_win.setGeometry(200, 200, 400, 600) # Increased height for new button
        main_win.show()
        
        exit_code = app.exec()
    
    except Exception as e:
        logger.error(f"Error in KnowledgeTreeWidget test setup: {e}")
        exit_code = 1
    finally:
        if dummy_dm_instance:
            dummy_dm_instance.cleanup_test_dirs() # Clean up test directories
        sys.exit(exit_code)