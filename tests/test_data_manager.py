import sys
import os

# Calculate the project root directory (one level up from the 'tests' directory)
# This ensures that 'src' can be imported correctly when running tests from 'tests/' or the project root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add project root to sys.path if it's not already there
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
import sqlite3
import uuid
import shutil
from datetime import datetime

from src import data_manager

# Store original values to restore them later if needed, though monkeypatch handles this for tests
ORIGINAL_DB_NAME = data_manager.DB_NAME
ORIGINAL_TEXT_FILES_DIR = data_manager.TEXT_FILES_DIR
ORIGINAL_MIGRATIONS_DIR = data_manager.MIGRATIONS_DIR

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """
    Pytest fixture to set up a temporary environment for data_manager tests.
    - Creates a temporary directory for the database and topic files.
    - Patches data_manager's DB_NAME and TEXT_FILES_DIR to use temp paths.
    - Ensures MIGRATIONS_DIR points to the project's migrations directory.
    - Cleans up the temporary directory after tests.
    """
    test_db_name = "test_iromo.sqlite"
    test_topics_dir_name = "test_topics_data"
    
    # Create temporary directories within tmp_path provided by pytest
    temp_db_path = tmp_path / test_db_name
    temp_topics_path = tmp_path / test_topics_dir_name
    os.makedirs(temp_topics_path, exist_ok=True)

    # Path to the project's actual migrations directory
    # project_root is defined globally at the top of this file.
    actual_migrations_dir = os.path.join(project_root, "migrations")

    monkeypatch.setattr(data_manager, 'DB_NAME', str(temp_db_path))
    monkeypatch.setattr(data_manager, 'TEXT_FILES_DIR', str(temp_topics_path))
    # Ensure MIGRATIONS_DIR is correct relative to where data_manager expects it.
    # If data_manager.py uses it as a relative path from its own location,
    # and tests run from root, this should be fine.
    # For robustness, one might copy migrations to tmp_path or ensure absolute path.
    # For now, we assume "migrations" relative to CWD (project root) works.
    monkeypatch.setattr(data_manager, 'MIGRATIONS_DIR', actual_migrations_dir)

    yield {
        "db_path": str(temp_db_path),
        "topics_dir": str(temp_topics_path),
        "migrations_dir": actual_migrations_dir
    }

    # Cleanup is handled by tmp_path fixture automatically.
    # If not using tmp_path, manual cleanup would be:
    # shutil.rmtree(tmp_path)


def get_table_names(db_path):
    """Helper to get table names from a sqlite DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()
    return tables

def test_initialize_database(test_env):
    """
    Test that initialize_database creates the DB file, topics dir, and necessary tables.
    """
    db_path = test_env["db_path"]
    topics_dir = test_env["topics_dir"]

    # Ensure DB and topics dir don't exist before call (tmp_path handles fresh state)
    assert not os.path.exists(db_path)
    # The topics_dir is created by the fixture, initialize_database should also ensure it.
    
    data_manager.initialize_database()

    assert os.path.exists(db_path), "Database file should be created"
    assert os.path.exists(topics_dir), "Topics data directory should be created"

    # Verify tables are created
    tables = get_table_names(db_path)
    expected_tables = {"topics", "extractions", "schema_migrations"}
    assert expected_tables.issubset(tables), \
        f"Expected tables {expected_tables} not found in {tables}"

    # Verify migration was applied
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations WHERE version = '001_initial_schema.sql'")
    migration_applied = cursor.fetchone()
    conn.close()
    assert migration_applied is not None, "001_initial_schema.sql should be marked as applied"


def test_create_topic_root(test_env):
    """
    Test creating a new root topic.
    """
    db_path = test_env["db_path"]
    topics_dir = test_env["topics_dir"]
    
    data_manager.initialize_database() # Setup DB schema

    test_content = "This is the content for a root topic."
    custom_title = "My Root Topic"
    
    topic_id = data_manager.create_topic(text_content=test_content, custom_title=custom_title, parent_id=None)

    assert topic_id is not None, "create_topic should return a topic ID"
    try:
        uuid.UUID(topic_id) # Check if it's a valid UUID
    except ValueError:
        pytest.fail(f"Returned topic_id '{topic_id}' is not a valid UUID.")

    # Verify database record
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, parent_id, title, text_file_uuid, created_at, updated_at FROM topics WHERE id = ?", (topic_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "Topic should be in the database"
    db_topic_id, db_parent_id, db_title, db_text_file_uuid, db_created_at, db_updated_at = row
    
    assert db_topic_id == topic_id
    assert db_parent_id is None, "Root topic parent_id should be NULL"
    assert db_title == custom_title
    assert uuid.UUID(db_text_file_uuid), "text_file_uuid should be a valid UUID"
    
    # Check timestamps (basic check: they should exist and be recent)
    assert db_created_at is not None
    assert db_updated_at is not None
    # A more precise check might involve datetime parsing and comparison, but this is often sufficient
    created_dt = datetime.fromisoformat(db_created_at.split('.')[0]) # Handle potential microseconds
    updated_dt = datetime.fromisoformat(db_updated_at.split('.')[0])
    assert (datetime.now() - created_dt).total_seconds() < 5 # Created within last 5 seconds
    assert (datetime.now() - updated_dt).total_seconds() < 5 # Updated within last 5 seconds


    # Verify text file creation
    expected_text_file_path = os.path.join(topics_dir, f"{db_text_file_uuid}.txt")
    assert os.path.exists(expected_text_file_path), "Topic content file should be created"
    
    with open(expected_text_file_path, 'r', encoding='utf-8') as f:
        content_in_file = f.read()
    assert content_in_file == test_content, "Content in file should match provided content"


def test_create_topic_child(test_env):
    """
    Test creating a child topic.
    """
    db_path = test_env["db_path"]
    topics_dir = test_env["topics_dir"]

    data_manager.initialize_database()

    # Create a parent topic first
    parent_content = "Parent topic content."
    parent_title = "Parent Topic"
    parent_id = data_manager.create_topic(text_content=parent_content, custom_title=parent_title)
    assert parent_id is not None

    # Create child topic
    child_content = "This is content for a child topic."
    child_title = "Child Topic"
    child_id = data_manager.create_topic(text_content=child_content, custom_title=child_title, parent_id=parent_id)

    assert child_id is not None, "create_topic for child should return an ID"
    try:
        uuid.UUID(child_id)
    except ValueError:
        pytest.fail(f"Returned child_id '{child_id}' is not a valid UUID.")

    # Verify database record for child
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, parent_id, title, text_file_uuid, created_at, updated_at FROM topics WHERE id = ?", (child_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "Child topic should be in the database"
    db_child_id, db_parent_id, db_title, db_text_file_uuid, db_created_at, db_updated_at = row

    assert db_child_id == child_id
    assert db_parent_id == parent_id, "Child's parent_id should match the parent's ID"
    assert db_title == child_title
    assert uuid.UUID(db_text_file_uuid)

    created_dt = datetime.fromisoformat(db_created_at.split('.')[0])
    updated_dt = datetime.fromisoformat(db_updated_at.split('.')[0])
    assert (datetime.now() - created_dt).total_seconds() < 5
    assert (datetime.now() - updated_dt).total_seconds() < 5

    # Verify text file creation for child
    expected_child_text_file_path = os.path.join(topics_dir, f"{db_text_file_uuid}.txt")
    assert os.path.exists(expected_child_text_file_path), "Child topic content file should be created"
    
    with open(expected_child_text_file_path, 'r', encoding='utf-8') as f:
        child_content_in_file = f.read()
    assert child_content_in_file == child_content

def test_create_topic_auto_title(test_env):
    """
    Test creating a topic where title is auto-generated from content.
    """
    db_path = test_env["db_path"]
    data_manager.initialize_database()

    # Test with content shorter than INITIAL_TITLE_LENGTH
    short_content = "Short content for title."
    topic_id_short = data_manager.create_topic(text_content=short_content)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM topics WHERE id = ?", (topic_id_short,))
    row_short = cursor.fetchone()
    conn.close()
    assert row_short[0] == short_content, "Auto-title for short content failed"

    # Test with content longer than INITIAL_TITLE_LENGTH
    long_content_prefix = "This is a very long piece of content that will definitely exceed the initial title length"
    long_content_suffix = " and this part should be truncated."
    long_content = long_content_prefix + long_content_suffix
    
    topic_id_long = data_manager.create_topic(text_content=long_content)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM topics WHERE id = ?", (topic_id_long,))
    row_long = cursor.fetchone()
    conn.close()
    
    expected_long_title = (long_content_prefix[:data_manager.INITIAL_TITLE_LENGTH] + '...') \
        if len(long_content_prefix) > data_manager.INITIAL_TITLE_LENGTH \
        else long_content_prefix + ('...' if long_content_suffix else '')

    # Adjusting expectation based on _generate_initial_title logic (uses first meaningful line)
    first_line_of_long_content = long_content.splitlines()[0]
    expected_auto_title_long = (first_line_of_long_content[:data_manager.INITIAL_TITLE_LENGTH] + '...') \
                               if len(first_line_of_long_content) > data_manager.INITIAL_TITLE_LENGTH \
                               else first_line_of_long_content

    assert row_long[0] == expected_auto_title_long, \
        f"Auto-title for long content failed. Expected '{expected_auto_title_long}', got '{row_long[0]}'"

    # Test with empty content
    empty_content = ""
    topic_id_empty = data_manager.create_topic(text_content=empty_content)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT title FROM topics WHERE id = ?", (topic_id_empty,))
    row_empty = cursor.fetchone()
    conn.close()
    assert row_empty[0] == "Untitled Topic", "Auto-title for empty content failed"