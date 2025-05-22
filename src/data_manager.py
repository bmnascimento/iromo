import sqlite3
import uuid
import os
import datetime as dt
import glob
import logging

# Get a logger for this module
logger = logging.getLogger(__name__)

# Module-level constants
MIGRATIONS_DIR = "migrations"  # Directory to store SQL migration files relative to app root
INITIAL_TITLE_LENGTH = 70
DB_FILENAME = "iromo.sqlite"
TEXT_FILES_SUBDIR = "text_files"

# --- SQLite datetime handling (remains at module level) ---
def adapt_datetime_iso(datetime_obj):
    """Adapt dt.datetime to timezone-naive ISO 8601 format."""
    return datetime_obj.isoformat()

def convert_timestamp_iso(val_bytes):
    """Convert ISO 8601 string (bytes) to dt.datetime object."""
    val_str = val_bytes.decode() if isinstance(val_bytes, bytes) else val_bytes
    return dt.datetime.fromisoformat(val_str)

sqlite3.register_adapter(dt.datetime, adapt_datetime_iso)
sqlite3.register_converter("timestamp", convert_timestamp_iso)
# --- End SQLite datetime handling ---

class DataManager:
    def __init__(self, collection_base_path: str):
        """
        Initializes the DataManager for a specific collection.

        Args:
            collection_base_path: The absolute path to the root of the collection folder.
        """
        if not os.path.isdir(collection_base_path):
            # This case should ideally be handled before instantiating DataManager,
            # e.g., when creating a new collection or trying to open one.
            # For now, we'll log and proceed, but db/file ops will likely fail.
            logger.warning(f"Collection base path does not exist: {collection_base_path}. Creating it.")
            try:
                os.makedirs(collection_base_path, exist_ok=True)
            except OSError as e:
                logger.error(f"Failed to create collection base path {collection_base_path}: {e}")
                raise  # Re-raise if directory creation fails critically

        self.collection_base_path = collection_base_path
        self.db_path = os.path.join(self.collection_base_path, DB_FILENAME)
        self.text_files_dir = os.path.join(self.collection_base_path, TEXT_FILES_SUBDIR)
        # MIGRATIONS_DIR is module-level, referring to the application's migrations folder
        self.migrations_dir = MIGRATIONS_DIR

        logger.info(f"DataManager initialized for collection: {self.collection_base_path}")
        logger.info(f"Database path: {self.db_path}")
        logger.info(f"Text files directory: {self.text_files_dir}")

    def _get_db_connection(self):
        """Establishes and returns a connection to the SQLite database for the collection."""
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        return conn

    def _apply_migrations(self, conn):
        """Applies pending database migrations to the collection's database."""
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

        # Migrations are read from the application's migration directory
        migration_files = sorted(glob.glob(os.path.join(self.migrations_dir, "*.sql")))
        if not migration_files and not os.path.exists(self.migrations_dir):
             logger.warning(f"Migrations directory '{self.migrations_dir}' not found. Cannot apply migrations.")
             return # Cannot proceed if migrations dir is missing
        if not migration_files:
            logger.info(f"No migration scripts found in {self.migrations_dir}. Assuming schema is up-to-date or managed externally for this collection.")
            return


        for migration_file_path in migration_files:
            migration_filename = os.path.basename(migration_file_path)
            if migration_filename not in applied_versions:
                logger.info(f"Applying migration: {migration_filename} to {self.db_path}...")
                try:
                    with open(migration_file_path, 'r') as f:
                        sql_script = f.read()
                        cursor.executescript(sql_script)
                    
                    cursor.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                                   (migration_filename, dt.datetime.now()))
                    conn.commit()
                    logger.info(f"Successfully applied migration: {migration_filename} to {self.db_path}")
                except sqlite3.Error as e:
                    conn.rollback()
                    logger.error(f"Error applying migration {migration_filename} to {self.db_path}: {e}")
                    raise

    def initialize_collection_storage(self):
        """
        Initializes the storage for the collection:
        Creates the text_files directory if it doesn't exist.
        Creates the database file and applies migrations if it's a new DB.
        """
        if not os.path.exists(self.text_files_dir):
            os.makedirs(self.text_files_dir)
            logger.info(f"Created text_files directory for collection: {self.text_files_dir}")
        
        # Ensure the application's migrations directory exists (for reading migrations)
        if not os.path.exists(self.migrations_dir):
            # This is an application setup issue, not collection specific.
            # For robustness, we could try to create it, but it's better if it's part of app deployment.
            logger.warning(f"Application's migrations directory '{self.migrations_dir}' not found. Migrations may not be applied.")
            # os.makedirs(self.migrations_dir) # Or decide to raise an error

        conn = self._get_db_connection()
        try:
            self._apply_migrations(conn)
            logger.info(f"Collection database '{self.db_path}' initialization and migration check complete.")
        except Exception as e:
            logger.error(f"Collection database initialization failed for {self.db_path}: {e}")
            raise # Re-raise to signal failure
        finally:
            conn.close()

    def _generate_initial_title(self, text_content):
        """Generates an initial title from the first part of the text content."""
        if not text_content:
            return "Untitled Topic"
        lines = [line for line in text_content.splitlines() if line.strip()]
        first_meaningful_line = lines[0] if lines else text_content
        
        return (first_meaningful_line[:INITIAL_TITLE_LENGTH] + '...') if len(first_meaningful_line) > INITIAL_TITLE_LENGTH else first_meaningful_line

    def create_topic(self, text_content="", parent_id=None, custom_title=None):
        """
        Creates a new topic in the collection's database and its corresponding text file.
        Returns the ID of the newly created topic.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        topic_id = str(uuid.uuid4())
        text_file_uuid_str = str(uuid.uuid4())
        text_file_path = os.path.join(self.text_files_dir, f"{text_file_uuid_str}.txt")
        
        now = dt.datetime.now()
        title = custom_title if custom_title else self._generate_initial_title(text_content)

        try:
            # Ensure text_files_dir exists before writing
            if not os.path.exists(self.text_files_dir):
                os.makedirs(self.text_files_dir)
                logger.info(f"Created missing text_files directory: {self.text_files_dir}")

            with open(text_file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)

            cursor.execute("""
            INSERT INTO topics (id, parent_id, title, text_file_uuid, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (topic_id, parent_id, title, text_file_uuid_str, now, now))
            
            conn.commit()
            logger.info(f"Topic '{title}' (ID: {topic_id}) created successfully in collection {self.collection_base_path}.")
            return topic_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating topic in {self.collection_base_path}: {e}")
            if os.path.exists(text_file_path):
                try:
                    os.remove(text_file_path)
                    logger.info(f"Cleaned up orphaned text file: {text_file_path}")
                except OSError as ose:
                    logger.error(f"Error removing orphaned text file {text_file_path}: {ose}")
            return None
        finally:
            conn.close()

    def _get_topic_text_file_path(self, text_file_uuid):
        """Constructs the full path to a topic's text file within the collection."""
        return os.path.join(self.text_files_dir, f"{text_file_uuid}.txt")

    def get_topic_content(self, topic_id):
        """
        Retrieves the text content of a given topic from the collection.
        Returns the content as a string, or None if the topic or file doesn't exist.
        """
        conn = self._get_db_connection()
        row = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT text_file_uuid FROM topics WHERE id = ?", (topic_id,))
            row = cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Database error fetching text_file_uuid for topic {topic_id} in {self.db_path}: {e}")
        finally:
            if conn:
                conn.close()

        if row:
            text_file_path = self._get_topic_text_file_path(row['text_file_uuid'])
            try:
                with open(text_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                logger.error(f"Text file not found for topic {topic_id} at {text_file_path}")
                return None
            except Exception as e:
                logger.error(f"Error reading text file for topic {topic_id} from {text_file_path}: {e}")
                return None
        else:
            logger.warning(f"Topic with ID {topic_id} not found in database {self.db_path} when trying to get content.")
            return None

    def save_topic_content(self, topic_id, content):
        """
        Saves the given content to the topic's text file in the collection and updates the 'updated_at' timestamp.
        Returns True on success, False on failure.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT text_file_uuid FROM topics WHERE id = ?", (topic_id,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"Topic with ID {topic_id} not found in {self.db_path} for saving content.")
            conn.close()
            return False

        text_file_path = self._get_topic_text_file_path(row['text_file_uuid'])
        now = dt.datetime.now()

        try:
            with open(text_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            cursor.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, topic_id))
            conn.commit()
            logger.info(f"Content for topic '{topic_id}' in collection {self.collection_base_path} saved successfully.")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving content for topic {topic_id} in {self.collection_base_path}: {e}")
            return False
        finally:
            conn.close()

    def update_topic_title(self, topic_id, new_title):
        """
        Updates the title of a given topic in the collection's database.
        Returns True on success, False on failure.
        """
        if not new_title or not new_title.strip():
            logger.error("New title cannot be empty.")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()
        now = dt.datetime.now()

        try:
            cursor.execute("UPDATE topics SET title = ?, updated_at = ? WHERE id = ?", (new_title, now, topic_id))
            if cursor.rowcount == 0:
                logger.error(f"Topic with ID {topic_id} not found in {self.db_path} for title update.")
                conn.close()
                return False
            conn.commit()
            logger.info(f"Title for topic '{topic_id}' in {self.collection_base_path} updated to '{new_title}'.")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating title for topic {topic_id} in {self.collection_base_path}: {e}")
            return False
        finally:
            conn.close()

    def get_topic_hierarchy(self):
        """
        Fetches all topics from the collection's database to allow reconstruction of the hierarchy.
        Returns a list of dictionaries, each containing id, title, and parent_id.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, title, parent_id, created_at FROM topics ORDER BY parent_id, display_order, created_at")
            topics = [dict(row) for row in cursor.fetchall()]
            return topics
        except Exception as e:
            logger.error(f"Error fetching topic hierarchy from {self.db_path}: {e}")
            return []
        finally:
            conn.close()

    def create_extraction(self, parent_topic_id, child_topic_id, start_char, end_char):
        """
        Records an extraction event in the collection's database.
        Returns the ID of the newly created extraction record, or None on failure.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        extraction_id = str(uuid.uuid4())
        
        try:
            cursor.execute("SELECT id FROM topics WHERE id = ?", (parent_topic_id,))
            if not cursor.fetchone():
                logger.error(f"Error creating extraction in {self.db_path}: Parent topic {parent_topic_id} not found.")
                return None
            
            cursor.execute("SELECT id FROM topics WHERE id = ?", (child_topic_id,))
            if not cursor.fetchone():
                logger.error(f"Error creating extraction in {self.db_path}: Child topic {child_topic_id} not found.")
                return None

            cursor.execute("""
            INSERT INTO extractions (id, parent_topic_id, child_topic_id, parent_text_start_char, parent_text_end_char)
            VALUES (?, ?, ?, ?, ?)
            """, (extraction_id, parent_topic_id, child_topic_id, start_char, end_char))
            
            cursor.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (dt.datetime.now(), parent_topic_id))

            conn.commit()
            logger.info(f"Extraction from '{parent_topic_id}' to '{child_topic_id}' (ID: {extraction_id}) created successfully in {self.collection_base_path}.")
            return extraction_id
        except sqlite3.IntegrityError as e:
            conn.rollback()
            logger.error(f"Error creating extraction in {self.collection_base_path} (IntegrityError): {e}.")
            return None
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating extraction in {self.collection_base_path}: {e}")
            return None
        finally:
            conn.close()

    def get_extractions_for_parent(self, parent_topic_id):
        """
        Retrieves all extraction records for a given parent topic from the collection's database.
        Returns a list of dictionaries, each representing an extraction.
        """
        conn = self._get_db_connection()
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
            logger.error(f"Error fetching extractions for parent {parent_topic_id} from {self.db_path}: {e}")
            return []
        finally:
            conn.close()

if __name__ == '__main__':
    # This block is for illustrative purposes or direct testing of DataManager.
    # In the actual application, DataManager will be instantiated by other modules.
    
    # Create a dummy collection path for testing
    test_collection_dir = "temp_test_iromo_collection"
    if not os.path.exists(test_collection_dir):
        os.makedirs(test_collection_dir)
    
    # Create a dummy migrations directory and a dummy migration file if they don't exist
    # This is just to allow the test code to run without erroring on missing migrations.
    # In a real scenario, migrations are part of the application.
    if not os.path.exists(MIGRATIONS_DIR):
        os.makedirs(MIGRATIONS_DIR)
        logger.info(f"Created dummy migrations directory: {MIGRATIONS_DIR}")
    
    dummy_migration_file = os.path.join(MIGRATIONS_DIR, "000_dummy_test_migration.sql")
    if not os.path.exists(dummy_migration_file):
        with open(dummy_migration_file, "w") as f:
            f.write("-- Dummy migration for testing DataManager directly")
        logger.info(f"Created dummy migration file: {dummy_migration_file}")


    logger.info(f"Attempting to initialize DataManager for test collection: {test_collection_dir}")
    try:
        dm = DataManager(collection_base_path=os.path.abspath(test_collection_dir))
        logger.info(f"DataManager initialized. DB path: {dm.db_path}")
        
        logger.info("Attempting to initialize collection storage (DB and text files dir)...")
        dm.initialize_collection_storage() # This will create DB and apply migrations
        logger.info("Collection storage initialization complete.")

        # Example usage (optional, for testing):
        # logger.info("\n--- Running manual tests for DataManager methods ---")
        # test_topic_id = dm.create_topic(text_content="Initial content for testing.", custom_title="Test Topic")
        # if test_topic_id:
        #     logger.info(f"Created test topic with ID: {test_topic_id}")
        #     content = dm.get_topic_content(test_topic_id)
        #     logger.info(f"Content of test topic: {content}")
        #     dm.save_topic_content(test_topic_id, "Updated content for test topic.")
        #     updated_content = dm.get_topic_content(test_topic_id)
        #     logger.info(f"Updated content: {updated_content}")
        #     dm.update_topic_title(test_topic_id, "Test Topic - Updated Title")
        #     hierarchy = dm.get_topic_hierarchy()
        #     logger.info(f"Topic hierarchy: {hierarchy}")
        # else:
        #     logger.error("Failed to create test topic.")

    except Exception as e:
        logger.error(f"Error during DataManager direct test: {e}")
    finally:
        # Clean up the dummy collection directory after test
        # import shutil
        # if os.path.exists(test_collection_dir):
        #     logger.info(f"Removing test collection directory: {test_collection_dir}")
        #     shutil.rmtree(test_collection_dir)
        # if os.path.exists(dummy_migration_file): # Clean up dummy migration
        #     os.remove(dummy_migration_file)
        # if os.path.exists(MIGRATIONS_DIR) and not os.listdir(MIGRATIONS_DIR): # Clean up dummy migrations dir if empty
        #     os.rmdir(MIGRATIONS_DIR)
        logger.info("--- DataManager direct test finished ---")
        pass