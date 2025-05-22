import abc

class BaseCommand(abc.ABC):
    """
    Abstract base class for all command objects.
    Commands encapsulate an action and the means to undo/redo it.
    """

    @abc.abstractmethod
    def execute(self):
        """
        Executes the command.
        This method should perform the actual operation.
        """
        pass

    @abc.abstractmethod
    def undo(self):
        """
        Undoes the command.
        This method should revert the changes made by execute().
        """
        pass

    def redo(self):
        """
        Re-executes the command.
        The default implementation is to simply call execute().
        Subclasses can override this if a different redo behavior is needed.
        """
        self.execute()

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """
        Returns a user-friendly description of the command.
        e.g., "Create Topic 'My New Topic'"
        """
        pass