"""Abstract base collector for credential collection tasks."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional


class BaseCollector(ABC):
    """Abstract base class for credential collection strategies."""

    def __init__(self, task_id: str, config: dict[str, Any]):
        self.task_id = task_id
        self.config = config
        self._cancelled = False

    @property
    def name(self) -> str:
        """Human-readable collector name."""
        return "base"

    @abstractmethod
    async def execute(self) -> AsyncGenerator[dict, None]:
        """Execute the collection task.
        
        Yields step update dictionaries with keys:
            - step: str (step name)
            - status: str ('running' | 'completed' | 'failed')
            - message: str
            - progress: int (0-100)
            - data: dict (optional result data)
        """
        if False:  # pragma: no cover
            yield {}  # Make generator type work

    @abstractmethod
    async def cleanup(self):
        """Clean up resources after task completion or cancellation."""
        ...

    def cancel(self):
        """Request cancellation of the current task."""
        self._cancelled = True
