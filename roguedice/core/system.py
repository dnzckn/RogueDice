"""Base system class for the ECS framework."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .world import World


class System(ABC):
    """
    Base class for all systems.
    Systems contain game logic and operate on entities with specific components.
    """

    priority: int = 0  # Lower = runs earlier

    def __init__(self):
        self.world: Optional['World'] = None

    @abstractmethod
    def update(self, delta_time: float) -> None:
        """Process entities each tick."""
        pass
