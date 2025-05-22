import logging

from ..data_manager import DataManager
from .base_command import BaseCommand
# Forward declare Qt widgets for type hinting if not importing directly
# to avoid circular dependencies or heavy imports in command files.
# from PyQt6.QtWidgets import QWidget # Example if needed

logger = logging.getLogger(__name__)

class CreateTopicCommand(BaseCommand):
    def __init__(self, data_manager: DataManager,
                 parent_id: str = None, custom_title: str = None, text_content: str = ""):
        self.data_manager = data_manager
        self.parent_id = parent_id
        self.custom_title = custom_title
        self.text_content = text_content
        self.new_topic_id = None
        self._description = "Create Topic" # Default, can be refined

    def execute(self):
        self.new_topic_id = self.data_manager.create_topic(
            text_content=self.text_content,
            parent_id=self.parent_id,
            custom_title=self.custom_title
        )
        if not self.new_topic_id:
            raise RuntimeError("Failed to create topic in DataManager")

        # Determine actual title if not custom_title was provided
        actual_title = self.custom_title
        if not actual_title:
            # If DataManager generates a title, we might need to fetch it
            # For now, assume custom_title or a generic one is used for UI
            # Or, DataManager.create_topic could return (id, title)
            topic_data = self.data_manager.get_topic_details(self.new_topic_id) # Assumes method exists
            actual_title = topic_data['title'] if topic_data else "New Topic"


        self._description = f"Create Topic '{actual_title}'"
        logger.info(f"Executing: {self.description}")
        # UI updates will be handled by listeners to DataManager.topic_created signal

    def undo(self):
        logger.info(f"Undoing: {self.description}")
        if self.new_topic_id:
            deleted = self.data_manager.delete_topic(self.new_topic_id)
            if not deleted:
                # Log error, but don't raise to allow undo stack processing to continue if possible
                logger.error(f"Failed to delete topic {self.new_topic_id} during undo.")
            # UI updates will be handled by listeners to DataManager.topic_deleted signal
        else:
            logger.warning("Cannot undo CreateTopicCommand: new_topic_id is not set.")

    @property
    def description(self) -> str:
        return self._description


class ChangeTopicTitleCommand(BaseCommand):
    def __init__(self, data_manager: DataManager, topic_id: str, old_title: str, new_title: str):
        self.data_manager = data_manager
        self.topic_id = topic_id
        self.old_title = old_title
        self.new_title = new_title
        self._description = f"Rename Topic '{old_title}' to '{new_title}'"

    def execute(self):
        logger.info(f"Executing: {self.description}")
        success = self.data_manager.update_topic_title(self.topic_id, self.new_title)
        if not success:
            raise RuntimeError(f"DataManager failed to update title for topic {self.topic_id}")
        # UI updates will be handled by listeners to DataManager.topic_title_changed signal

    def undo(self):
        logger.info(f"Undoing: {self.description}")
        success = self.data_manager.update_topic_title(self.topic_id, self.old_title)
        if not success:
            logger.error(f"DataManager failed to revert title for topic {self.topic_id} during undo.")
        # UI updates will be handled by listeners to DataManager.topic_title_changed signal (when title reverts to old_title)

    @property
    def description(self) -> str:
        return self._description


class SaveTopicContentCommand(BaseCommand):
    def __init__(self, data_manager: DataManager, topic_id: str, old_content: str, new_content: str, topic_title: str = "Unknown Topic"):
        self.data_manager = data_manager
        self.topic_id = topic_id
        self.old_content = old_content
        self.new_content = new_content
        # topic_title is for description purposes, as content can be large
        self._description = f"Save Content for Topic '{topic_title}'"


    def execute(self):
        logger.info(f"Executing: {self.description}")
        success = self.data_manager.save_topic_content(self.topic_id, self.new_content)
        if not success:
            raise RuntimeError(f"DataManager failed to save content for topic {self.topic_id}")

    def undo(self):
        logger.info(f"Undoing: {self.description}")
        success = self.data_manager.save_topic_content(self.topic_id, self.old_content)
        if not success:
            logger.error(f"DataManager failed to revert content for topic {self.topic_id} during undo.")
        # Note: Undoing a save might require the editor to be reloaded with old_content.
        # This logic would typically be handled by a signal from UndoManager listened to by MainWindow/TopicEditorWidget.

    @property
    def description(self) -> str:
        return self._description


class ExtractTextCommand(BaseCommand):
    def __init__(self, data_manager: DataManager,
                 parent_topic_id: str, selected_text: str, start_char: int, end_char: int):
        self.data_manager = data_manager
        self.parent_topic_id = parent_topic_id
        self.selected_text = selected_text
        self.start_char = start_char
        self.end_char = end_char
        
        self.child_topic_id = None
        self.extraction_id = None
        self.child_topic_title = "" # Will be set in execute
        self._description = "Extract Text" # Default, refined in execute

    def execute(self):
        # 1. Create the child topic with the selected text
        self.child_topic_id = self.data_manager.create_topic(
            text_content=self.selected_text,
            parent_id=self.parent_topic_id 
            # Title will be auto-generated by DataManager or we can pass one
        )
        if not self.child_topic_id:
            raise RuntimeError("Failed to create child topic for extraction in DataManager.")

        # Fetch the generated title for the description and UI
        child_topic_data = self.data_manager.get_topic_details(self.child_topic_id) # Assumes method exists
        self.child_topic_title = child_topic_data['title'] if child_topic_data else "New Extract"
        self._description = f"Extract Text to '{self.child_topic_title}'"
        logger.info(f"Executing: {self.description}")

        # 2. Create the extraction link
        self.extraction_id = self.data_manager.create_extraction(
            parent_topic_id=self.parent_topic_id,
            child_topic_id=self.child_topic_id,
            start_char=self.start_char,
            end_char=self.end_char
        )
        if not self.extraction_id:
            # Attempt to clean up the created child topic if extraction link fails
            logger.error(f"Failed to create extraction link. Attempting to delete orphaned child topic {self.child_topic_id}")
            self.data_manager.delete_topic(self.child_topic_id) # Rollback child topic creation
            self.child_topic_id = None # Nullify to prevent issues in undo
            raise RuntimeError("Failed to create extraction link in DataManager.")
        # UI updates for new child topic and parent highlighting will be handled by listeners
        # to DataManager.topic_created and DataManager.extraction_created signals.

    def undo(self):
        logger.info(f"Undoing: {self.description}")
        # Order of undo: remove extraction link, then remove child topic
        if self.extraction_id:
            deleted_extraction = self.data_manager.delete_extraction(self.extraction_id)
            if not deleted_extraction:
                logger.error(f"Failed to delete extraction {self.extraction_id} during undo.")
        
        if self.child_topic_id:
            deleted_topic = self.data_manager.delete_topic(self.child_topic_id)
            if not deleted_topic:
                logger.error(f"Failed to delete child topic {self.child_topic_id} during undo.")
            # UI updates for removing child topic and parent highlighting will be handled by listeners
            # to DataManager.topic_deleted and DataManager.extraction_deleted signals.

    @property
    def description(self) -> str:
        return self._description


class MoveTopicCommand(BaseCommand):
    def __init__(self, data_manager: DataManager,
                 topic_id: str,
                 old_parent_id: str, old_display_order: int,
                 new_parent_id: str, new_display_order: int):
        self.data_manager = data_manager
        self.topic_id = topic_id
        self.old_parent_id = old_parent_id
        self.old_display_order = old_display_order
        self.new_parent_id = new_parent_id
        self.new_display_order = new_display_order
        
        # Fetch topic title for a more descriptive message
        # This assumes DataManager has a way to get topic details by ID
        topic_data = self.data_manager.get_topic_details(self.topic_id) # Assumes method exists
        topic_title = topic_data['title'] if topic_data else topic_id
        self._description = f"Move Topic '{topic_title}'"

    def execute(self):
        logger.info(f"Executing: {self.description} to parent '{self.new_parent_id}' at order {self.new_display_order}")
        success = self.data_manager.move_topic(self.topic_id, self.new_parent_id, self.new_display_order)
        if not success:
            raise RuntimeError(f"DataManager failed to move topic {self.topic_id}")
        # UI updates will be handled by listeners to DataManager.topic_moved signal

    def undo(self):
        logger.info(f"Undoing: {self.description}, moving back to parent '{self.old_parent_id}' at order {self.old_display_order}")
        success = self.data_manager.move_topic(self.topic_id, self.old_parent_id, self.old_display_order)
        if not success:
            logger.error(f"DataManager failed to revert move for topic {self.topic_id} during undo.")
        # UI updates will be handled by listeners to DataManager.topic_moved signal (when reverting)

    @property
    def description(self) -> str:
        return self._description


class DeleteMultipleTopicsCommand(BaseCommand):
    def __init__(self, data_manager: DataManager, topic_ids: list[str]):
        self.data_manager = data_manager
        # Store only top-level selected IDs. DM handles children.
        self.top_level_topic_ids = list(set(topic_ids)) # Ensure unique IDs
        self._deleted_topics_data = [] # Stores list of dicts for all deleted topics (incl. descendants)
        self._description = f"Delete {len(self.top_level_topic_ids)} topic(s)"
        if len(self.top_level_topic_ids) == 1:
            # Try to get a more specific title if only one topic is selected
            # This might be too slow if get_topic_details is expensive and called here.
            # Consider fetching title in execute or relying on a generic message.
            # For now, keeping it simple.
            # topic_data = self.data_manager.get_topic_details(self.top_level_topic_ids[0])
            # if topic_data:
            #     self._description = f"Delete Topic '{topic_data['title']}'"
            # else:
            self._description = f"Delete Topic" # Generic for one
        else:
            self._description = f"Delete {len(self.top_level_topic_ids)} Topics"


    def execute(self):
        logger.info(f"Executing: {self.description}")
        self._deleted_topics_data = [] # Clear previous data if any (e.g., re-execution)

        # Important: Fetch details *before* deleting.
        # We need to collect all descendants for each top-level ID.
        all_ids_to_fetch_details_for = set()
        temp_all_deleted_topic_details = []

        for topic_id in self.top_level_topic_ids:
            # Get details for the topic and all its descendants
            # This list is already ordered (parent before children)
            descendant_details = self.data_manager.get_topic_and_all_descendants_details(topic_id)
            if not descendant_details:
                logger.warning(f"Could not retrieve details for topic {topic_id} or its descendants. It might have been already deleted.")
                # Continue to attempt deletion of other topics if any.
                # If this topic was the only one, the command might effectively do nothing.
            else:
                temp_all_deleted_topic_details.extend(descendant_details)
        
        # Ensure uniqueness and correct order for undo (parents before children)
        # get_topic_and_all_descendants_details should provide them in a suitable order (pre-order traversal)
        # We store them in the order they are fetched, which should be suitable for restoration.
        # To ensure no duplicates if multiple selected items lead to the same descendant (not typical for tree selection):
        seen_ids = set()
        for details in temp_all_deleted_topic_details:
            if details['id'] not in seen_ids:
                self._deleted_topics_data.append(details)
                seen_ids.add(details['id'])
        
        # Sort by depth (approximated by parent_id presence) then creation for stable undo
        # This is complex. For now, rely on the order from get_topic_and_all_descendants_details.
        # A more robust way for undo is to restore in the exact order of deletion,
        # or ensure parents are created before children. The current structure of _deleted_topics_data
        # (list of dicts from pre-order traversal) should be fine.

        # Now, perform the deletions for the top-level selected items
        # DataManager's delete_topic will handle cascading.
        deleted_count = 0
        for topic_id in self.top_level_topic_ids:
            # Check if topic still exists (it might have been deleted as a child of another selected topic)
            # A simple check: is it still in our _deleted_topics_data list by ID?
            # More accurately, the DataManager.delete_topic will handle non-existent topics gracefully.
            if any(t['id'] == topic_id for t in self._deleted_topics_data): # Check if it was part of the collected data
                if self.data_manager.delete_topic(topic_id):
                    deleted_count +=1
                else:
                    # If a top-level delete fails, we have a problem.
                    # The _deleted_topics_data might be partially relevant.
                    # For now, log and continue, but this indicates an issue.
                    logger.error(f"Failed to delete topic {topic_id} during multi-delete operation.")
                    # Potentially raise an error or handle partial success/failure.
                    # For simplicity, we assume DM's delete_topic is robust.
            else:
                logger.info(f"Topic {topic_id} was likely deleted as a descendant of another selected topic. Skipping explicit delete.")


        if not self._deleted_topics_data: # No topics were actually processed for deletion
             logger.warning(f"DeleteMultipleTopicsCommand: No topic data was collected for deletion. Command may have no effect.")
             # This can happen if all specified topic_ids were already deleted or invalid.
        
        # Refine description based on actual number of top-level items processed for deletion
        # This is tricky because _deleted_topics_data contains all descendants.
        # The initial description based on self.top_level_topic_ids is probably best.
        logger.info(f"DeleteMultipleTopicsCommand: execute completed. {len(self._deleted_topics_data)} total items (incl. children) marked for undo.")


    def undo(self):
        logger.info(f"Undoing: {self.description}")
        if not self._deleted_topics_data:
            logger.warning("Cannot undo DeleteMultipleTopicsCommand: no data to restore.")
            return

        # Restore topics. The order matters: parents must be restored before children.
        # The _deleted_topics_data should be in pre-order (parent before children).
        restored_count = 0
        for topic_data in self._deleted_topics_data:
            # Ensure all necessary fields are present from get_topic_and_all_descendants_details
            # 'content' was added to topic_data in that method.
            # 'display_order' should also be there.
            restored_id = self.data_manager.create_topic(
                topic_id=topic_data['id'],
                parent_id=topic_data.get('parent_id'), # Use .get for safety
                custom_title=topic_data['title'],
                text_content=topic_data.get('content', ''), # Ensure content exists
                text_file_uuid=topic_data['text_file_uuid'],
                created_at=topic_data['created_at'],
                updated_at=topic_data['updated_at'],
                display_order=topic_data.get('display_order') # Ensure display_order is handled
            )
            if restored_id:
                restored_count += 1
            else:
                logger.error(f"Failed to restore topic {topic_data['id']} during undo.")
                # This is problematic. The undo is partial.
        
        logger.info(f"DeleteMultipleTopicsCommand: undo completed. {restored_count}/{len(self._deleted_topics_data)} topics attempted to restore.")
        # UI updates will be handled by listeners to DataManager.topic_created signal

    @property
    def description(self) -> str:
        return self._description

# A helper method in DataManager like get_topic_details(topic_id) -> dict
# would be useful for commands to fetch topic titles for descriptions.
# Example:
# def get_topic_details(self, topic_id):
#     conn = self._get_db_connection()
#     cursor = conn.cursor()
#     try:
#         cursor.execute("SELECT id, title, parent_id, created_at, updated_at FROM topics WHERE id = ?", (topic_id,))
#         row = cursor.fetchone()
#         return dict(row) if row else None
#     finally:
#         conn.close()
# This should be added to data_manager.py