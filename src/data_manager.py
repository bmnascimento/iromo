import sqlite3
import uuid
import os
from datetime import datetime
import glob
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

DB_NAME = "iromo.sqlite"
TEXT_FILES_DIR = "iromo_data/text_files"
MIGRATIONS_DIR = "migrations" # Directory to store SQL migration files
INITIAL_TITLE_LENGTH = 70

# --- Database Connection & Initialization ---

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def _apply_migrations(conn):
    """Applies pending database migrations."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL
    )
    """)
    conn.commit()

    cursor.execute("SELECT version FROM schema_migrations ORDER BY version DESC")
    applied_versions = {row['version'] for row in cursor.fetchall()}

    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))

    for migration_file_path in migration_files:
        migration_filename = os.path.basename(migration_file_path)
        if migration_filename not in applied_versions:
            logger.info(f"Applying migration: {migration_filename}...")
            try:
                with open(migration_file_path, 'r') as f:
                    sql_script = f.read()
                    cursor.executescript(sql_script) # Use executescript for multi-statement SQL files
                
                cursor.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                               (migration_filename, datetime.now()))
                conn.commit()
                logger.info(f"Successfully applied migration: {migration_filename}")
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"Error applying migration {migration_filename}: {e}")
                raise # Re-raise the exception to halt further operations if a migration fails

def initialize_database():
    """
    Initializes the database by creating necessary directories and applying migrations.
    """
    if not os.path.exists(TEXT_FILES_DIR):
        os.makedirs(TEXT_FILES_DIR)
        logger.info(f"Created directory: {TEXT_FILES_DIR}")
    
    if not os.path.exists(MIGRATIONS_DIR):
        os.makedirs(MIGRATIONS_DIR)
        logger.info(f"Created directory: {MIGRATIONS_DIR}")
        # Create a placeholder for the first migration if it doesn't exist
        # This helps guide the user to create the actual 001_initial_schema.sql
        if not glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")):
             logger.warning(f"No migration scripts found in {MIGRATIONS_DIR}. Please create '001_initial_schema.sql'.")


    conn = get_db_connection()
    try:
        _apply_migrations(conn)
        logger.info(f"Database '{DB_NAME}' initialization and migration check complete.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    finally:
        conn.close()

# --- Topic Management Functions ---

def _generate_initial_title(text_content):
    """Generates an initial title from the first part of the text content."""
    if not text_content:
        return "Untitled Topic"
    # Prefer the first non-empty line for the title
    lines = [line for line in text_content.splitlines() if line.strip()]
    first_meaningful_line = lines[0] if lines else text_content
    
    return (first_meaningful_line[:INITIAL_TITLE_LENGTH] + '...') if len(first_meaningful_line) > INITIAL_TITLE_LENGTH else first_meaningful_line

def create_topic(text_content="", parent_id=None, custom_title=None):
    """
    Creates a new topic in the database and its corresponding text file.
    Returns the ID of the newly created topic.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    topic_id = str(uuid.uuid4())
    text_file_uuid_str = str(uuid.uuid4())
    text_file_path = os.path.join(TEXT_FILES_DIR, f"{text_file_uuid_str}.txt")
    
    now = datetime.now()
    title = custom_title if custom_title else _generate_initial_title(text_content)

    try:
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        cursor.execute("""
        INSERT INTO topics (id, parent_id, title, text_file_uuid, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (topic_id, parent_id, title, text_file_uuid_str, now, now))
        
        conn.commit()
        logger.info(f"Topic '{title}' (ID: {topic_id}) created successfully.")
        return topic_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating topic: {e}")
        if os.path.exists(text_file_path):
            try:
                os.remove(text_file_path) # Clean up orphaned text file
                logger.info(f"Cleaned up orphaned text file: {text_file_path}")
            except OSError as ose:
                logger.error(f"Error removing orphaned text file {text_file_path}: {ose}")
        return None
    finally:
        conn.close()

# --- Helper function for text file paths ---
def _get_topic_text_file_path(text_file_uuid):
    """Constructs the full path to a topic's text file."""
    return os.path.join(TEXT_FILES_DIR, f"{text_file_uuid}.txt")

# --- Topic Content and Title Management ---

def get_topic_content(topic_id):
    """
    Retrieves the text content of a given topic.
    Returns the content as a string, or None if the topic or file doesn't exist.
    """
    conn = get_db_connection()
    row = None # Initialize row to ensure it's defined in case of early exit/error
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT text_file_uuid FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Database error fetching text_file_uuid for topic {topic_id}: {e}")
        # row remains None, the existing 'if row:' logic will handle this
    finally:
        if conn: # conn is guaranteed to be defined by this point from get_db_connection()
            conn.close()

    if row:
        text_file_path = _get_topic_text_file_path(row['text_file_uuid'])
        try:
            with open(text_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Text file not found for topic {topic_id} at {text_file_path}")
            return None
        except Exception as e:
            logger.error(f"Error reading text file for topic {topic_id}: {e}")
            return None
    else:
        logger.warning(f"Topic with ID {topic_id} not found in database when trying to get content.")
        return None

def save_topic_content(topic_id, content):
    """
    Saves the given content to the topic's text file and updates the 'updated_at' timestamp.
    Returns True on success, False on failure.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT text_file_uuid FROM topics WHERE id = ?", (topic_id,))
    row = cursor.fetchone()

    if not row:
        logger.error(f"Topic with ID {topic_id} not found for saving content.")
        conn.close()
        return False

    text_file_path = _get_topic_text_file_path(row['text_file_uuid'])
    now = datetime.now()

    try:
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        cursor.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, topic_id))
        conn.commit()
        logger.info(f"Content for topic '{topic_id}' saved successfully.")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error saving content for topic {topic_id}: {e}")
        return False
    finally:
        conn.close()

def update_topic_title(topic_id, new_title):
    """
    Updates the title of a given topic in the database.
    Returns True on success, False on failure.
    """
    if not new_title or not new_title.strip():
        logger.error("New title cannot be empty.")
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()

    try:
        cursor.execute("UPDATE topics SET title = ?, updated_at = ? WHERE id = ?", (new_title, now, topic_id))
        if cursor.rowcount == 0:
            logger.error(f"Topic with ID {topic_id} not found for title update.")
            conn.close()
            return False
        conn.commit()
        logger.info(f"Title for topic '{topic_id}' updated to '{new_title}'.")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating title for topic {topic_id}: {e}")
        return False
    finally:
        conn.close()

# --- Hierarchy and Extraction Management ---

def get_topic_hierarchy():
    """
    Fetches all topics to allow reconstruction of the hierarchy.
    Returns a list of dictionaries, each containing id, title, and parent_id.
    Order by created_at to give a default sensible ordering for siblings.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, parent_id, created_at FROM topics ORDER BY parent_id, display_order, created_at")
        # Using sqlite3.Row factory, so items are dictionary-like
        topics = [dict(row) for row in cursor.fetchall()]
        return topics
    except Exception as e:
        logger.error(f"Error fetching topic hierarchy: {e}")
        return []
    finally:
        conn.close()

def create_extraction(parent_topic_id, child_topic_id, start_char, end_char):
    """
    Records an extraction event in the database.
    'child_topic_id' is the ID of the new topic created from the extracted text.
    Returns the ID of the newly created extraction record, or None on failure.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    extraction_id = str(uuid.uuid4())
    
    try:
        # First, ensure both parent and child topics exist
        cursor.execute("SELECT id FROM topics WHERE id = ?", (parent_topic_id,))
        if not cursor.fetchone():
            logger.error(f"Error creating extraction: Parent topic {parent_topic_id} not found.")
            return None
        
        cursor.execute("SELECT id FROM topics WHERE id = ?", (child_topic_id,))
        if not cursor.fetchone():
            logger.error(f"Error creating extraction: Child topic {child_topic_id} not found.")
            return None

        cursor.execute("""
        INSERT INTO extractions (id, parent_topic_id, child_topic_id, parent_text_start_char, parent_text_end_char)
        VALUES (?, ?, ?, ?, ?)
        """, (extraction_id, parent_topic_id, child_topic_id, start_char, end_char))
        
        # Also update the parent topic's updated_at timestamp
        cursor.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (datetime.now(), parent_topic_id))

        conn.commit()
        logger.info(f"Extraction from '{parent_topic_id}' to '{child_topic_id}' (ID: {extraction_id}) created successfully.")
        return extraction_id
    except sqlite3.IntegrityError as e:
        # This could happen if child_topic_id is not unique in extractions, or foreign key constraints fail
        conn.rollback()
        logger.error(f"Error creating extraction (IntegrityError): {e}. Ensure child_topic_id is unique for extractions and both topics exist.")
        return None
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating extraction: {e}")
        return None
    finally:
        conn.close()

def get_extractions_for_parent(parent_topic_id):
    """
    Retrieves all extraction records for a given parent topic.
    Returns a list of dictionaries, each representing an extraction.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT id, child_topic_id, parent_text_start_char, parent_text_end_char
        FROM extractions
        WHERE parent_topic_id = ?
        ORDER BY parent_text_start_char
        """, (parent_topic_id,))
        extractions = [dict(row) for row in cursor.fetchall()]
        return extractions
    except Exception as e:
        logger.error(f"Error fetching extractions for parent {parent_topic_id}: {e}")
        return []
    finally:
        conn.close()

# --- Placeholder for other functions ---
# def delete_topic(topic_id): pass # Consider implications for children and extractions


if __name__ == '__main__':
    # This block is now only for manually initializing the database if needed.
    # For testing, use a dedicated test runner and temporary databases.
    logger.info("Initializing Iromo database (if needed) when data_manager.py is run directly...")
    initialize_database()
    logger.info("Initialization process finished when data_manager.py is run directly.")
    # Example: You could add a test topic creation here for manual dev checks,
    # but it's better to do this in a separate test script or via the UI.
    #
    # # --- Manual test calls for new functions ---
    # # Ensure DB is initialized before running these
    # logger.info("\n--- Running manual tests for data_manager functions ---")
    # test_topic_id = create_topic(text_content="Initial content for testing get/save.", custom_title="Test Topic for Content")
    #
    # if test_topic_id:
    #     logger.info(f"\n[Test] Original content for {test_topic_id}:")
    #     original_content = get_topic_content(test_topic_id)
    #     logger.info(original_content)
    #
    #     logger.info(f"\n[Test] Saving new content for {test_topic_id}...")
    #     save_topic_content(test_topic_id, "This is the updated content. It's much better now!")
    #
    #     logger.info(f"\n[Test] Retrieving updated content for {test_topic_id}:")
    #     updated_content = get_topic_content(test_topic_id)
    #     logger.info(updated_content)
    #
    #     logger.info(f"\n[Test] Updating title for {test_topic_id}...")
    #     update_topic_title(test_topic_id, "Test Topic - Title Updated")
    #
    #     # Verify title update by trying to fetch it (though we don't have a get_topic_details yet)
    #     # For now, we'd check the DB directly or assume it worked based on logger.info output.
    #
    #     logger.info(f"\n[Test] Attempting to get content for a non-existent topic:")
    #     get_topic_content("non-existent-uuid")
    #
    #     logger.info(f"\n[Test] Attempting to save content for a non-existent topic:")
    #     save_topic_content("non-existent-uuid", "some content")
    #
    #     logger.info(f"\n[Test] Attempting to update title for a non-existent topic:")
    #     update_topic_title("non-existent-uuid", "some title")
    #
    #     logger.info(f"\n[Test] Attempting to update title with empty string:")
    #     update_topic_title(test_topic_id, "  ")
    #
    # # --- Tests for hierarchy and extractions ---
    # logger.info("\n--- Testing Hierarchy and Extractions ---")
    # # Create a small hierarchy for testing
    # root_id = create_topic("Root for hierarchy test", custom_title="Hierarchy Root")
    # child1_id = None
    # child2_id = None
    # grandchild1_id = None
    #
    # if root_id:
    #     child1_id = create_topic("Child 1 text. Some extractable content here.", parent_id=root_id, custom_title="Child 1")
    #     child2_id = create_topic("Child 2 text.", parent_id=root_id, custom_title="Child 2")
    #
    # if child1_id:
    #     # Simulating content that would be in the file for "Child 1"
    #     # For the purpose of this test, the actual file content of child1_id is "Child 1 text. Some extractable content here."
    #     # "extractable content" is at index 25 to 45 (exclusive of end for slicing, inclusive for highlighting)
    #     grandchild1_id = create_topic("extractable content", parent_id=child1_id, custom_title="Grandchild 1 (Extracted)")
    #     if grandchild1_id:
    #         extraction_id = create_extraction(parent_topic_id=child1_id, child_topic_id=grandchild1_id, start_char=25, end_char=44) # "extractable content" (end_char is inclusive for storage)
    #         if extraction_id:
    #             logger.info(f"Created extraction record: {extraction_id}")
    #
    # logger.info("\n[Test] Full Topic Hierarchy:")
    # hierarchy = get_topic_hierarchy()
    # if hierarchy:
    #     for topic in hierarchy:
    #         logger.info(f"  ID: {topic['id']}, Title: {topic['title']}, Parent: {topic['parent_id']}")
    # else:
    #     logger.info("  No hierarchy data returned.")
    #
    # if child1_id:
    #     logger.info(f"\n[Test] Extractions for Parent ID {child1_id} (Child 1):")
    #     extractions = get_extractions_for_parent(child1_id)
    #     if extractions:
    #         for extr in extractions:
    #             logger.info(f"  Extraction ID: {extr['id']}, Child Topic: {extr['child_topic_id']}, Start: {extr['parent_text_start_char']}, End: {extr['parent_text_end_char']}")
    #     else:
    #         logger.info(f"  No extractions found for {child1_id}.")
    #
    # logger.info("\n[Test] Attempting to create extraction with non-existent parent:")
    # create_extraction("non-existent-parent", child1_id if child1_id else "dummy_child", 0, 10)
    #
    # logger.info("\n[Test] Attempting to create extraction with non-existent child:")
    # create_extraction(root_id if root_id else "dummy_parent", "non-existent-child", 0, 10)
    #
    # logger.info("\n--- Manual tests finished ---")
    pass # Keep the if __name__ block, but no active test code by default.