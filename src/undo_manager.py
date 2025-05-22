import logging
from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional

from src.commands.base_command import BaseCommand

logger = logging.getLogger(__name__)

class UndoManager(QObject):
    """
    Manages undo and redo stacks for commands.
    Emits signals when the state of the stacks or the ability to undo/redo changes.
    """
    can_undo_changed = pyqtSignal(bool)
    can_redo_changed = pyqtSignal(bool)
    undo_text_changed = pyqtSignal(str) # Emits the description of the next undoable command
    redo_text_changed = pyqtSignal(str) # Emits the description of the next redoable command
    command_executed = pyqtSignal(BaseCommand) # Emits the command that was just executed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._undo_stack: List[BaseCommand] = []
        self._redo_stack: List[BaseCommand] = []
        self._update_signals()

    def _update_signals(self):
        """Updates all relevant signals based on current stack states."""
        can_undo = self.can_undo()
        can_redo = self.can_redo()

        self.can_undo_changed.emit(can_undo)
        self.can_redo_changed.emit(can_redo)

        undo_desc = self._undo_stack[-1].description if can_undo else ""
        redo_desc = self._redo_stack[-1].description if can_redo else ""
        
        self.undo_text_changed.emit(f"Undo {undo_desc}" if undo_desc else "Undo")
        self.redo_text_changed.emit(f"Redo {redo_desc}" if redo_desc else "Redo")

    def execute_command(self, command: BaseCommand):
        """
        Executes a command, adds it to the undo stack, and clears the redo stack.
        """
        try:
            command.execute()
            self._undo_stack.append(command)
            if self._redo_stack: # Clear redo stack only if it's not empty
                self._redo_stack.clear()
            
            logger.info(f"Command executed: {command.description}")
            self.command_executed.emit(command) # Emit signal after successful execution
        except Exception as e:
            logger.error(f"Error executing command '{command.description}': {e}", exc_info=True)
            # Optionally, re-raise or handle more gracefully (e.g., show error to user)
            # For now, we let the exception propagate if not caught by command.execute()
            raise
        finally:
            self._update_signals()


    def undo(self):
        """
        Undoes the last command from the undo stack and moves it to the redo stack.
        """
        if not self.can_undo():
            logger.warning("Undo called but nothing to undo.")
            return

        command = self._undo_stack.pop()
        try:
            command.undo()
            self._redo_stack.append(command)
            logger.info(f"Command undone: {command.description}")
        except Exception as e:
            logger.error(f"Error undoing command '{command.description}': {e}", exc_info=True)
            # If undo fails, put command back on undo stack to maintain consistent state
            self._undo_stack.append(command) 
            # Optionally, re-raise or handle more gracefully
            raise
        finally:
            self._update_signals()

    def redo(self):
        """
        Redoes the last command from the redo stack and moves it to the undo stack.
        """
        if not self.can_redo():
            logger.warning("Redo called but nothing to redo.")
            return

        command = self._redo_stack.pop()
        try:
            command.redo() # or command.execute() if redo is not overridden
            self._undo_stack.append(command)
            logger.info(f"Command redone: {command.description}")
        except Exception as e:
            logger.error(f"Error redoing command '{command.description}': {e}", exc_info=True)
            # If redo fails, put command back on redo stack
            self._redo_stack.append(command)
            # Optionally, re-raise or handle more gracefully
            raise
        finally:
            self._update_signals()

    def can_undo(self) -> bool:
        """Returns True if there are commands in the undo stack."""
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        """Returns True if there are commands in the redo stack."""
        return bool(self._redo_stack)

    def clear_stacks(self):
        """Clears both undo and redo stacks."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.info("Undo/Redo stacks cleared.")
        self._update_signals()

    def get_undo_stack_descriptions(self) -> List[str]:
        """Returns a list of descriptions for commands in the undo stack."""
        return [cmd.description for cmd in reversed(self._undo_stack)]

    def get_redo_stack_descriptions(self) -> List[str]:
        """Returns a list of descriptions for commands in the redo stack."""
        return [cmd.description for cmd in reversed(self._redo_stack)]