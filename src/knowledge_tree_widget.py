from PyQt6.QtWidgets import QTreeView, QAbstractItemView
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QFont
from PyQt6.QtCore import Qt, pyqtSignal
import data_manager as dm

class KnowledgeTreeWidget(QTreeView):
    # Signal emitted when a topic is selected in the tree
    # Passes the topic_id (str) as an argument
    topic_selected = pyqtSignal(str) 
    # Signal emitted when a topic's title is edited by the user
    # Passes topic_id (str) and new_title (str)
    topic_title_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.SelectedClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setHeaderHidden(True) # We only care about the topic titles

        self.model = QStandardItemModel()
        self.setModel(self.model)
        
        self.model.itemChanged.connect(self._handle_item_changed)
        self.selectionModel().selectionChanged.connect(self._handle_selection_changed)

        self._topic_item_map = {} # Maps topic_id to QStandardItem

        self.load_tree()

    def _clear_tree(self):
        self.model.clear()
        self._topic_item_map = {}
        # Set column count and header data again after clearing
        self.model.setHorizontalHeaderLabels(['Topic Title'])


    def load_tree(self):
        """Loads the topic hierarchy from the data manager and populates the tree."""
        self._clear_tree()
        topics_data = dm.get_topic_hierarchy() # Expects list of dicts
        
        # Build a dictionary of items keyed by their ID, and a dictionary of children for each parent
        items = {}
        children_map = {}

        # First pass: create all items
        for topic_d in topics_data:
            item = QStandardItem(topic_d['title'])
            item.setData(topic_d['id'], Qt.ItemDataRole.UserRole) # Store topic_id in the item
            item.setEditable(True) # Allow title editing
            items[topic_d['id']] = item
            self._topic_item_map[topic_d['id']] = item
            
            parent_id = topic_d.get('parent_id')
            if parent_id:
                if parent_id not in children_map:
                    children_map[parent_id] = []
                children_map[parent_id].append(item)

        # Second pass: attach children to parents, or add to root if no parent
        root_items = []
        for topic_d in topics_data:
            item = items[topic_d['id']]
            parent_id = topic_d.get('parent_id')
            if parent_id is None: # Root item
                root_items.append(item)
            elif parent_id in items: # Parent exists, add as child
                # This check is redundant if children_map is built correctly, but good for safety
                pass # Children are added below based on children_map
            else: # Orphaned item (should ideally not happen with FK constraints)
                print(f"Warning: Topic {topic_d['id']} has parent_id {parent_id} but parent not found. Adding as root.")
                root_items.append(item)
        
        # Add children to their respective parents using children_map
        for parent_id, child_items_list in children_map.items():
            if parent_id in items:
                parent_item = items[parent_id]
                for child_item in child_items_list:
                    parent_item.appendRow(child_item)
            # else: orphaned children, already handled if we add them as roots or log

        # Add all root items to the model
        for root_item in root_items:
            self.model.appendRow(root_item)
            
        if not topics_data:
            placeholder_item = QStandardItem("No topics yet. Add one!")
            placeholder_item.setEditable(False)
            placeholder_item.setEnabled(False)
            self.model.appendRow(placeholder_item)

    def _handle_item_changed(self, item):
        """Called when an item's data (e.g., title from editing) changes."""
        topic_id = item.data(Qt.ItemDataRole.UserRole)
        new_title = item.text()
        if topic_id and new_title:
            # Here we could also check if the title actually changed from its original db value
            # For now, we assume any 'itemChanged' on an editable item with UserRole data is a title change.
            print(f"Tree item changed: ID {topic_id}, New Text: '{new_title}'")
            self.topic_title_changed.emit(topic_id, new_title)
            # dm.update_topic_title(topic_id, new_title) # Direct call or via signal to AppLogic

    def _handle_selection_changed(self, selected, deselected):
        """Called when the selection in the tree changes."""
        indexes = selected.indexes()
        if indexes:
            selected_item = self.model.itemFromIndex(indexes[0])
            if selected_item:
                topic_id = selected_item.data(Qt.ItemDataRole.UserRole)
                if topic_id:
                    print(f"Tree selection changed: Topic ID {topic_id}")
                    self.topic_selected.emit(topic_id)

    def add_topic_item(self, title, topic_id, parent_id=None):
        """Adds a new topic item to the tree. If parent_id is None, adds as a root item."""
        # Remove placeholder if it exists
        if self.model.rowCount() > 0:
            first_item_text = self.model.item(0).text()
            if first_item_text == "No topics yet. Add one!":
                self.model.removeRow(0)

        item = QStandardItem(title)
        item.setData(topic_id, Qt.ItemDataRole.UserRole)
        item.setEditable(True)
        self._topic_item_map[topic_id] = item

        if parent_id and parent_id in self._topic_item_map:
            parent_item = self._topic_item_map[parent_id]
            parent_item.appendRow(item)
            self.expand(parent_item.index()) # Expand parent to show new child
        else:
            self.model.appendRow(item)
        
        self.setCurrentIndex(item.index()) # Select the newly added item
        return item

    def update_topic_item_title(self, topic_id, new_title):
        """Updates the title of an existing topic item in the tree."""
        if topic_id in self._topic_item_map:
            item = self._topic_item_map[topic_id]
            # Temporarily disconnect itemChanged signal to prevent feedback loop if called from AppLogic
            try:
                self.model.itemChanged.disconnect(self._handle_item_changed)
            except TypeError: # Already disconnected
                pass
            item.setText(new_title)
            try:
                self.model.itemChanged.connect(self._handle_item_changed)
            except TypeError: # Already connected (should not happen if disconnect worked)
                pass
        else:
            print(f"Warning: Tried to update title for non-existent item in tree: {topic_id}")

    def get_selected_topic_id(self):
        """Returns the topic_id of the currently selected item, or None."""
        current_index = self.currentIndex()
        if current_index.isValid():
            item = self.model.itemFromIndex(current_index)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton
    import sys

    # Dummy data_manager functions for standalone testing
    class DummyDM:
        def get_topic_hierarchy(self):
            return [
                {'id': 'root1', 'title': 'Root Topic 1', 'parent_id': None},
                {'id': 'child1_1', 'title': 'Child 1.1 (R1)', 'parent_id': 'root1'},
                {'id': 'child1_2', 'title': 'Child 1.2 (R1)', 'parent_id': 'root1'},
                {'id': 'grandchild1_1_1', 'title': 'Grandchild 1.1.1 (C1.1)', 'parent_id': 'child1_1'},
                {'id': 'root2', 'title': 'Root Topic 2 (Empty)', 'parent_id': None},
            ]
        def update_topic_title(self, topic_id, new_title):
            print(f"[DummyDM] Update title for {topic_id} to '{new_title}'")
            return True

    dm_actual = dm # Save actual dm
    dm = DummyDM() # Replace with dummy for test

    app = QApplication(sys.argv)
    main_win = QMainWindow()
    main_win.setWindowTitle("Knowledge Tree Widget Test")
    
    central_widget = QWidget()
    main_win.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)

    tree_widget = KnowledgeTreeWidget()
    layout.addWidget(tree_widget)

    def test_add_topic():
        # Example of adding a new root topic
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
            print("No parent selected to add child to.")
            
    def test_update_selected_title():
        selected_id = tree_widget.get_selected_topic_id()
        if selected_id:
            tree_widget.update_topic_item_title(selected_id, "TITLE UPDATED EXTERNALLY")
        else:
            print("No item selected to update title.")


    btn_add_root = QPushButton("Add Root Topic")
    btn_add_root.clicked.connect(test_add_topic)
    layout.addWidget(btn_add_root)
    
    btn_add_child = QPushButton("Add Child to Selected")
    btn_add_child.clicked.connect(test_add_child_topic)
    layout.addWidget(btn_add_child)

    btn_update_title = QPushButton("Update Selected Title Externally")
    btn_update_title.clicked.connect(test_update_selected_title)
    layout.addWidget(btn_update_title)

    main_win.setGeometry(200, 200, 400, 500)
    main_win.show()
    
    dm = dm_actual # Restore actual dm
    sys.exit(app.exec())