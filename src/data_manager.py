import sqlite3
import uuid
import os
import datetime as dt
import glob
import logging
from PyQt6.QtCore import QObject, pyqtSignal

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

class DataManager(QObject):
    # Signals for data changes
    topic_created = pyqtSignal(str, str, str, str) # topic_id, parent_id, title, text_content
    topic_title_changed = pyqtSignal(str, str) # topic_id, new_title
    topic_content_saved = pyqtSignal(str) # topic_id
    topic_deleted = pyqtSignal(str, str) # deleted_topic_id, old_parent_id
    extraction_created = pyqtSignal(str, str, str, int, int) # extraction_id, parent_topic_id, child_topic_id, start_char, end_char
    extraction_deleted = pyqtSignal(str, str) # extraction_id, parent_topic_id
    topic_moved = pyqtSignal(str, str, str, int) # topic_id, new_parent_id, old_parent_id, new_display_order
    # Signal to indicate a full refresh might be needed, e.g., after migrations or complex ops
    data_changed_bulk = pyqtSignal()
    shortcuts_changed = pyqtSignal() # Signal for shortcut changes


    def __init__(self, collection_base_path: str):
        """
        Initializes the DataManager for a specific collection.

        Args:
            collection_base_path: The absolute path to the root of the collection folder.
        """
        super().__init__() # Initialize QObject
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

        self.default_shortcuts = {
            "app.quit": "Ctrl+Q",
            "app.preferences": "Ctrl+,",
            "file.new_topic": "Ctrl+N",
            "file.save_topic": "Ctrl+S", # Retained as per existing defaults
            "file.open_collection": "Ctrl+O",
            "file.new_collection": "Ctrl+Shift+N",
            "file.close_collection": "Ctrl+Shift+W",
            "edit.undo": "Ctrl+Z",
            "edit.redo": "Ctrl+Shift+Z",
            "edit.cut": "Ctrl+X",
            "edit.copy": "Ctrl+C",
            "edit.paste": "Ctrl+V",
            "edit.delete": "Del",
            "edit.select_all": "Ctrl+A",
            "edit.extract_text": "Alt+X",
            "view.toggle_knowledge_tree": "Ctrl+T",
            "view.zoom_in": "Ctrl+=",
            "view.zoom_out": "Ctrl+-",
            "view.reset_zoom": "Ctrl+0",
            "navigation.next_topic": "Alt+Right",
            "navigation.previous_topic": "Alt+Left",
            "topic.create_child_topic": "Ctrl+Enter",
            "topic.edit_title": "F2",
            "topic.delete_topic": "Shift+Del",
            "help.about": "F1",
            # Add more default shortcuts here as actions are defined
        }

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
            self.data_changed_bulk.emit() # Emit after migrations
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

    def create_topic(self, text_content="", parent_id=None, custom_title=None,
                     topic_id=None, text_file_uuid=None,
                     created_at=None, updated_at=None, display_order=None):
        """
        Creates a new topic in the collection's database and its corresponding text file.
        Allows specifying existing IDs and timestamps for restoration purposes.
        Returns the ID of the newly created topic.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        final_topic_id = topic_id if topic_id else str(uuid.uuid4())
        final_text_file_uuid = text_file_uuid if text_file_uuid else str(uuid.uuid4())
        text_file_path = os.path.join(self.text_files_dir, f"{final_text_file_uuid}.html")
        
        now = dt.datetime.now()
        final_created_at = created_at if created_at else now
        final_updated_at = updated_at if updated_at else now
        
        if custom_title:
            title = custom_title
        else:
            title = dt.datetime.now().strftime("Topic %Y-%m-%d %H:%M:%S")
        # Ensure display_order is an int or None. Default to 0 if None and not specified.
        # However, display_order might be better handled by a separate update or move logic
        # if it involves reordering siblings. For simple creation, it can be set.
        # If None is passed, the DB schema might have a default or it could be NULL.
        # For now, let's assume it can be directly inserted.
        final_display_order = display_order

        try:
            # Ensure text_files_dir exists before writing
            if not os.path.exists(self.text_files_dir):
                os.makedirs(self.text_files_dir)
                logger.info(f"Created missing text_files directory: {self.text_files_dir}")

            with open(text_file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)

            cursor.execute("""
            INSERT INTO topics (id, parent_id, title, text_file_uuid, created_at, updated_at, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (final_topic_id, parent_id, title, final_text_file_uuid, final_created_at, final_updated_at, final_display_order))
            
            conn.commit()
            logger.info(f"Topic '{title}' (ID: {final_topic_id}) created/restored successfully in collection {self.collection_base_path}.")
            self.topic_created.emit(final_topic_id, parent_id, title, text_content) # Consider if this signal is appropriate for restore
            return final_topic_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating topic '{title}' (ID: {final_topic_id}) in {self.collection_base_path}: {e}")
            if os.path.exists(text_file_path) and not text_file_uuid: # Only remove if we created it
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
        return os.path.join(self.text_files_dir, f"{text_file_uuid}.html")

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
            self.topic_content_saved.emit(topic_id)
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
            self.topic_title_changed.emit(topic_id, new_title)
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

    def get_topic_details(self, topic_id):
        """
        Retrieves all details for a specific topic.
        Returns a dictionary of the topic's data, or None if not found.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, parent_id, title, text_file_uuid, created_at, updated_at, display_order
                FROM topics
                WHERE id = ?
            """, (topic_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching details for topic {topic_id} from {self.db_path}: {e}")
            return None
        finally:
            if conn:
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
            self.extraction_created.emit(extraction_id, parent_topic_id, child_topic_id, start_char, end_char)
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

    def _delete_topic_recursive(self, topic_id, conn) -> list | None:
        """
        Internal helper to recursively delete a topic and its descendants.
        Assumes conn is an active database connection with a cursor.
        Returns a list of (deleted_topic_id, original_parent_id) tuples on success,
        or None on failure (triggering a rollback).
        This method performs the actual deletion but DOES NOT emit signals.
        """
        deleted_topics_info = []
        cursor = conn.cursor()
        logger.debug(f"_delete_topic_recursive: Attempting to delete topic {topic_id}")

        # Get details of the current topic
        cursor.execute("SELECT text_file_uuid, parent_id FROM topics WHERE id = ?", (topic_id,))
        topic_data = cursor.fetchone()
        if not topic_data:
            logger.warning(f"_delete_topic_recursive: Topic {topic_id} not found. Already deleted?")
            return [] # Success, no topics deleted by this specific call path

        text_file_uuid = topic_data['text_file_uuid']
        original_parent_id = topic_data['parent_id']

        # Find and delete children first
        cursor.execute("SELECT id FROM topics WHERE parent_id = ?", (topic_id,))
        children_ids = [row['id'] for row in cursor.fetchall()]
        for child_id in children_ids:
            child_deleted_list = self._delete_topic_recursive(child_id, conn)
            if child_deleted_list is None: # If child deletion failed
                logger.error(f"_delete_topic_recursive: Failed to delete child {child_id} of {topic_id}. Aborting delete for {topic_id}.")
                return None # Propagate failure
            deleted_topics_info.extend(child_deleted_list)

        # All children (if any) are processed, now delete this topic
        try:
            # Delete associated extractions
            cursor.execute("DELETE FROM extractions WHERE parent_topic_id = ? OR child_topic_id = ?", (topic_id, topic_id))
            logger.debug(f"Deleted extractions associated with topic {topic_id}.")

            # Delete the topic itself
            cursor.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
            if cursor.rowcount == 0:
                logger.warning(f"_delete_topic_recursive: Topic {topic_id} disappeared before final delete. Assuming already handled.")
                # Not an error for this topic's deletion itself, but it wasn't found.
                # Children might have been deleted. Return current list.
                return deleted_topics_info

            # Text file deletion
            text_file_path = self._get_topic_text_file_path(text_file_uuid)
            if os.path.exists(text_file_path):
                try:
                    os.remove(text_file_path)
                    logger.debug(f"Deleted text file: {text_file_path}")
                except OSError as e:
                    logger.error(f"Error deleting text file {text_file_path} for topic {topic_id}: {e}")
                    # Log error, but consider DB part successful for this topic.

            logger.info(f"Topic {topic_id} (original parent: {original_parent_id}) processed for deletion.")
            deleted_topics_info.append((topic_id, original_parent_id))
            return deleted_topics_info
        except sqlite3.Error as e:
            logger.error(f"_delete_topic_recursive: DB error deleting topic {topic_id}: {e}")
            return None # Signal failure


    def delete_topic(self, topic_id):
        """
        Deletes a topic and all its descendants (cascading delete).
        Emits topic_deleted signals AFTER successful commit.
        Returns True on success, False on failure.
        The command calling this should fetch all necessary data for undo *before* calling this.
        """
        conn = self._get_db_connection()
        all_deleted_topic_infos = []
        try:
            conn.execute("BEGIN") # Start transaction
            
            deleted_infos_list = self._delete_topic_recursive(topic_id, conn)
            
            if deleted_infos_list is None: # Deletion failed and was rolled back internally
                conn.rollback() # Ensure rollback at this level too
                logger.error(f"Recursive deletion failed for topic {topic_id}. Transaction rolled back.")
                return False

            all_deleted_topic_infos.extend(deleted_infos_list)
            conn.commit()
            logger.info(f"Successfully deleted topic {topic_id} and its descendants. Transaction committed.")

            # Emit signals after successful commit
            for deleted_id, old_parent_id in all_deleted_topic_infos:
                self.topic_deleted.emit(deleted_id, old_parent_id)
            if all_deleted_topic_infos: # If anything was actually deleted
                 self.data_changed_bulk.emit() # A more general signal indicating significant change

            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting topic {topic_id} in {self.collection_base_path}: {e}")
            return False
        finally:
            conn.close()

    def delete_extraction(self, extraction_id):
        """
        Deletes a specific extraction record from the collection's database.
        Returns True on success, False on failure.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        parent_topic_id = None
        try:
            # First, get the parent_topic_id for the signal
            cursor.execute("SELECT parent_topic_id FROM extractions WHERE id = ?", (extraction_id,))
            row = cursor.fetchone()
            if row:
                parent_topic_id = row['parent_topic_id']
            else:
                logger.warning(f"Extraction {extraction_id} not found for deletion.")
                return False # Or True, if "not found" means "already deleted"

            cursor.execute("DELETE FROM extractions WHERE id = ?", (extraction_id,))
            if cursor.rowcount == 0:
                # This case might be redundant if the above fetch already confirmed existence
                logger.warning(f"Extraction {extraction_id} not found during delete operation.")
                conn.close()
                return False # Or True, depending on desired semantics for "not found"
            
            conn.commit()
            logger.info(f"Extraction '{extraction_id}' deleted successfully from {self.collection_base_path}.")
            if parent_topic_id: # Only emit if we found the parent
                self.extraction_deleted.emit(extraction_id, parent_topic_id)
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error deleting extraction {extraction_id} from {self.collection_base_path}: {e}")
            return False
        finally:
            conn.close()

    def move_topic(self, topic_id, new_parent_id, new_display_order):
        """
        Moves a topic to a new parent and/or updates its display order among siblings.
        Handles reordering of other siblings if necessary.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            conn.execute("BEGIN") # Start transaction

            # Get current parent and display order
            cursor.execute("SELECT parent_id, display_order FROM topics WHERE id = ?", (topic_id,))
            current_topic_info = cursor.fetchone()
            if not current_topic_info:
                logger.error(f"Topic {topic_id} not found for move operation.")
                conn.rollback()
                return False
            
            old_parent_id = current_topic_info['parent_id']
            # old_display_order = current_topic_info['display_order'] # Not directly used here but good for logging/undo

            # Update the target topic's parent and display order
            cursor.execute("UPDATE topics SET parent_id = ?, display_order = ?, updated_at = ? WHERE id = ?",
                           (new_parent_id, new_display_order, dt.datetime.now(), topic_id))

            # Re-normalize display_order for siblings under the new parent
            # All items at or after new_display_order (excluding the one just moved) need to be shifted
            cursor.execute("""
                UPDATE topics
                SET display_order = display_order + 1
                WHERE parent_id = ? AND id != ? AND display_order >= ?
            """, (new_parent_id, topic_id, new_display_order))
            
            # If the topic moved from a different parent, re-normalize display_order for old siblings
            if old_parent_id != new_parent_id:
                 cursor.execute("""
                    UPDATE topics
                    SET display_order = display_order - 1
                    WHERE parent_id = ? AND display_order > ? 
                 """, (old_parent_id, current_topic_info['display_order']))


            conn.commit()
            logger.info(f"Topic {topic_id} moved to parent {new_parent_id} at order {new_display_order}.")
            self.topic_moved.emit(topic_id, new_parent_id, old_parent_id, new_display_order)
            self.data_changed_bulk.emit() # Moving can affect tree structure significantly
            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"Error moving topic {topic_id}: {e}")
            return False
        finally:
            conn.close()

    def _get_topic_and_descendants_recursive(self, topic_id, conn, collected_topics_details):
        """
        Recursively fetches a topic and all its descendants' details.
        `collected_topics_details` is a list that this function appends to.
        """
        cursor = conn.cursor()
        
        # Fetch the current topic's details
        cursor.execute("""
            SELECT id, parent_id, title, text_file_uuid, created_at, updated_at, display_order
            FROM topics WHERE id = ?
        """, (topic_id,))
        topic_details = cursor.fetchone()
        
        if topic_details:
            collected_topics_details.append(dict(topic_details))
            
            # Fetch children of the current topic
            cursor.execute("SELECT id FROM topics WHERE parent_id = ? ORDER BY display_order", (topic_id,))
            children = cursor.fetchall()
            for child_row in children:
                self._get_topic_and_descendants_recursive(child_row['id'], conn, collected_topics_details)

    def get_topic_and_all_descendants_details(self, topic_id):
        """
        Retrieves details for a given topic and all its descendants.
        This is useful for operations like exporting or duplicating a branch of the tree.
        Returns a list of dictionaries, each representing a topic's data.
        The list is ordered such that parents appear before their children (depth-first).
        """
        conn = self._get_db_connection()
        all_details = []
        try:
            self._get_topic_and_descendants_recursive(topic_id, conn, all_details)
            return all_details
        except Exception as e:
            logger.error(f"Error fetching topic and descendants details for {topic_id}: {e}")
            return [] # Return empty list on error
        finally:
            if conn:
                conn.close()

    # --- Shortcut Management Methods ---

    def get_default_shortcuts(self) -> dict:
        """Returns the predefined default shortcuts."""
        return self.default_shortcuts.copy()

    def get_custom_shortcut(self, action_id: str) -> str | None:
        """
        Retrieves a custom shortcut for a given action_id from the database.
        Returns the shortcut string or None if not found.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT shortcut FROM shortcuts WHERE action_id = ?", (action_id,))
            row = cursor.fetchone()
            return row['shortcut'] if row else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching custom shortcut for {action_id} from {self.db_path}: {e}")
            return None
        finally:
            conn.close()

    def get_all_custom_shortcuts(self) -> dict:
        """
        Retrieves all custom shortcuts from the database.
        Returns a dictionary of {action_id: shortcut}.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        custom_shortcuts = {}
        try:
            cursor.execute("SELECT action_id, shortcut FROM shortcuts")
            for row in cursor.fetchall():
                custom_shortcuts[row['action_id']] = row['shortcut']
            return custom_shortcuts
        except sqlite3.Error as e:
            logger.error(f"Error fetching all custom shortcuts from {self.db_path}: {e}")
            return {}
        finally:
            conn.close()

    def get_shortcut(self, action_id: str) -> str | None:
        """
        Gets the current shortcut for an action.
        Returns the custom shortcut if it exists, otherwise the default shortcut.
        Returns None if the action_id is not recognized (has no default).
        """
        custom_shortcut = self.get_custom_shortcut(action_id)
        if custom_shortcut:
            return custom_shortcut
        return self.default_shortcuts.get(action_id)

    def get_all_shortcuts(self) -> dict:
        """
        Gets all currently active shortcuts, merging defaults with user customizations.
        User customizations override defaults.
        """
        active_shortcuts = self.default_shortcuts.copy()
        custom_shortcuts = self.get_all_custom_shortcuts()
        active_shortcuts.update(custom_shortcuts)
        return active_shortcuts

    def set_shortcut(self, action_id: str, shortcut: str) -> bool:
        """
        Sets or updates a user-customized shortcut for an action.
        Returns True on success, False on failure.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            # Using INSERT OR REPLACE to simplify logic for new vs existing shortcuts
            cursor.execute("""
                INSERT INTO shortcuts (action_id, shortcut) VALUES (?, ?)
                ON CONFLICT(action_id) DO UPDATE SET shortcut = excluded.shortcut
            """, (action_id, shortcut))
            conn.commit()
            logger.info(f"Shortcut for action '{action_id}' set to '{shortcut}' in {self.db_path}.")
            self.shortcuts_changed.emit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error setting shortcut for {action_id} to {shortcut} in {self.db_path}: {e}")
            return False
        finally:
            conn.close()

    def reset_shortcut(self, action_id: str) -> bool:
        """
        Resets a specific action's shortcut to its default by removing the custom setting.
        Returns True if a custom shortcut was removed or if no custom shortcut existed,
        False on database error.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM shortcuts WHERE action_id = ?", (action_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Custom shortcut for action '{action_id}' reset in {self.db_path}.")
            else:
                logger.info(f"No custom shortcut to reset for action '{action_id}' in {self.db_path}.")
            self.shortcuts_changed.emit() # Emit even if no custom shortcut was present, as the "effective" shortcut might change
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error resetting shortcut for {action_id} in {self.db_path}: {e}")
            return False
        finally:
            conn.close()

    def reset_all_shortcuts(self) -> bool:
        """
        Resets all user-customized shortcuts to their defaults by clearing the shortcuts table.
        Returns True on success, False on failure.
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM shortcuts")
            conn.commit()
            logger.info(f"All custom shortcuts have been reset in {self.db_path}.")
            self.shortcuts_changed.emit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Error resetting all shortcuts in {self.db_path}: {e}")
            return False
        finally:
            conn.close()