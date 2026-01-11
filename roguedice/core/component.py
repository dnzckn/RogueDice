"""Base component class for the ECS framework."""

from dataclasses import dataclass
from typing import TypeVar


@dataclass
class Component:
    """
    Base class for all components.
    Components are pure data containers with no logic.
    """
    pass


# Type variable for generic component operations
T = TypeVar('T', bound=Component)
