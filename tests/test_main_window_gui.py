import pytest
from pytestqt.qt_compat import qt_api # For accessing QtWidgets, QtCore, etc.
from pytestqt.qtbot import QtBot

# Add project root to sys.path for src imports
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.main_window import MainWindow
# from src.knowledge_tree_widget import KnowledgeTreeWidget # For type hinting if needed
# from src.topic_editor_widget import TopicEditorWidget # For type hinting if needed
from src import data_manager as dm

@pytest.fixture
def test_app_env(tmp_path, monkeypatch):
    """
    Pytest fixture to set up a temporary environment for GUI tests
    that require data_manager.
    - Creates a temporary directory for the database and topic files.
    - Patches data_manager's DB_NAME and TEXT_FILES_DIR to use temp paths.
    - Ensures MIGRATIONS_DIR points to the project's migrations directory.
    - Initializes the database.
    """
    test_db_name = "test_gui_iromo.sqlite"
    test_topics_dir_name = "test_gui_topics_data"
    
    temp_db_path = tmp_path / test_db_name
    temp_topics_path = tmp_path / test_topics_dir_name
    os.makedirs(temp_topics_path, exist_ok=True)

    actual_migrations_dir = os.path.join(project_root, "migrations")

    monkeypatch.setattr(dm, 'DB_NAME', str(temp_db_path))
    monkeypatch.setattr(dm, 'TEXT_FILES_DIR', str(temp_topics_path))
    monkeypatch.setattr(dm, 'MIGRATIONS_DIR', actual_migrations_dir)
    
    dm.initialize_database() # Initialize the database for this test environment

    yield {
        "db_path": str(temp_db_path),
        "topics_dir": str(temp_topics_path),
        "migrations_dir": actual_migrations_dir
    }
    # Cleanup of tmp_path is handled by pytest automatically

def test_main_window_loads(qtbot: QtBot, test_app_env):
    """Test that the MainWindow loads and is visible."""
    main_window = MainWindow()
    qtbot.addWidget(main_window) # Register widget with qtbot
    
    assert main_window is not None
    main_window.show() # Ensure it can be shown
    assert main_window.isVisible()
    # qtbot.waitExposed(main_window) # Alternative way to wait for visibility

def test_main_widgets_visibility(qtbot: QtBot, test_app_env):
    """Test that main child widgets (KnowledgeTreeWidget, TopicEditorWidget) are present and visible."""
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()

    # Access widgets using attribute names from MainWindow._setup_central_widget
    knowledge_tree = main_window.tree_widget
    topic_editor = main_window.editor_widget

    assert knowledge_tree is not None, "KnowledgeTreeWidget should exist"
    assert topic_editor is not None, "TopicEditorWidget should exist"

    # Widgets within a QSplitter are visible if the splitter and main window are.
    assert knowledge_tree.isVisible(), "KnowledgeTreeWidget should be visible"
    assert topic_editor.isVisible(), "TopicEditorWidget should be visible"
    
    # Check if they are indeed children of the splitter and have some geometry
    assert knowledge_tree.parent() == main_window.splitter
    assert topic_editor.parent() == main_window.splitter
    assert knowledge_tree.width() > 0
    assert topic_editor.width() > 0


def test_basic_topic_selection_updates_editor(qtbot: QtBot, test_app_env):
    """
    Test that selecting a topic in KnowledgeTreeWidget updates the TopicEditorWidget.
    """
    # test_app_env fixture has already initialized the database (dm.initialize_database())
    
    # 1. Create a test topic directly using data_manager
    topic_title = "Test Root Topic"
    topic_content = "Content of the test root topic."
    root_topic_id = dm.create_topic(text_content=topic_content, custom_title=topic_title, parent_id=None)
    assert root_topic_id is not None

    # 2. Instantiate MainWindow. It should load topics on init.
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    
    # 3. Wait for the tree to populate and find the QTreeWidgetItem for the created topic
    # KnowledgeTreeWidget._topic_item_map maps topic_id to QTreeWidgetItem
    def tree_has_item_check():
        return main_window.tree_widget._topic_item_map.get(root_topic_id) is not None
    qtbot.waitUntil(tree_has_item_check, timeout=1000) # Wait for tree to populate

    tree_item = main_window.tree_widget._topic_item_map.get(root_topic_id)
    assert tree_item is not None, f"Topic ID {root_topic_id} not found in tree widget's item map."

    # 4. Simulate selecting the item in the tree
    # This should trigger the topic_selected signal and update the editor
    main_window.tree_widget.setCurrentIndex(tree_item.index())
    
    # The signal connection should call main_window.handle_topic_selected,
    # which then calls editor_widget.load_topic_content.

    # 5. Assert that TopicEditorWidget is updated
    # Wait for signals to process and editor to update
    def editor_updated_check():
        editor_text = main_window.editor_widget.toPlainText()
        current_editor_topic_id = main_window.editor_widget.current_topic_id
        return editor_text == topic_content and current_editor_topic_id == root_topic_id

    qtbot.waitUntil(editor_updated_check, timeout=2000) 

    assert main_window.editor_widget.toPlainText() == topic_content, \
        "TopicEditorWidget content did not update to selected topic's content."
    assert main_window.editor_widget.current_topic_id == root_topic_id, \
        "TopicEditorWidget current_topic_id did not update."