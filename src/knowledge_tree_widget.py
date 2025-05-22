import logging
import os # For __main__ test

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QAbstractItemView, QTreeView

from .data_manager import DataManager # Import the DataManager class

logger = logging.getLogger(__name__)

class KnowledgeTreeWidget(QTreeView):
    topic_selected = pyqtSignal(str) # topic_id
    # Emits topic_id, old_title (fetched by MainWindow), new_title
    topic_title_changed = pyqtSignal(str, str, str) # topic_id, old_title, new_title

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setHeaderHidden(True)

        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.model.setHorizontalHeaderLabels(['Topic Title']) # Set header early
        
        self.model.itemChanged.connect(self._handle_item_changed)
        self.selectionModel().selectionChanged.connect(self._handle_selection_changed)

        self._topic_item_map = {} # Maps topic_id to QStandardItem
        self._editing_item_old_title = None # Store title before editing starts
        
        # load_tree is no longer called here; MainWindow will call load_tree_data

    def clear_tree(self):
        """Clears all items from the tree and resets the internal map."""
        self.model.clear()
        self._topic_item_map = {}
        # Set column count and header data again after clearing
        self.model.setHorizontalHeaderLabels(['Topic Title'])
        # Add placeholder when tree is empty and no collection is loaded
        self._add_placeholder_if_empty("No collection open or collection is empty.")


    def _add_placeholder_if_empty(self, text="No topics yet. Add one!"):
        """Adds a non-selectable, non-editable placeholder item if the tree is empty."""
        if self.model.rowCount() == 0:
            placeholder_item = QStandardItem(text)
            placeholder_item.setEditable(False)
            placeholder_item.setEnabled(False) # Grayed out
            self.model.appendRow(placeholder_item)

    def load_tree_data(self, data_manager_instance: DataManager):
        """Loads the topic hierarchy from the given DataManager instance and populates the tree."""
        if not data_manager_instance:
            logger.warning("load_tree_data called with no DataManager instance.")
            self.clear_tree() # Show "No collection open..."
            return

        self.clear_tree() # Clear previous content and placeholder
        topics_data = data_manager_instance.get_topic_hierarchy()
        
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
            
        if not topics_data:
            self._add_placeholder_if_empty("This collection is empty. Add a topic!")
        
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
        # Remove placeholder if it exists and is the only item
        if self.model.rowCount() == 1:
            first_item_data = self.model.item(0).data(Qt.ItemDataRole.UserRole)
            if first_item_data is None: # Likely a placeholder
                 self.model.removeRow(0)

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


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
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
    try:
        dummy_dm_instance = DummyDataManagerForTreeTest(test_collection_path)
    
        tree_widget = KnowledgeTreeWidget()
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
            # To test placeholder for empty collection after clear:
            # tree_widget.load_tree_data(None) # This would show "No collection open"
            # Or reload with dummy DM
            tree_widget.load_tree_data(dummy_dm_instance)


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

        main_win.setGeometry(200, 200, 400, 500)
        main_win.show()
        
        exit_code = app.exec()
    
    except Exception as e:
        logger.error(f"Error in KnowledgeTreeWidget test setup: {e}")
        exit_code = 1
    finally:
        if dummy_dm_instance:
            dummy_dm_instance.cleanup_test_dirs() # Clean up test directories
        sys.exit(exit_code)