"""Entity ID management for the ECS framework."""

import itertools
from typing import Generator, Set


class EntityManager:
    """Manages entity IDs and their lifecycle."""

    def __init__(self):
        self._id_counter = itertools.count(1)
        self._alive_entities: Set[int] = set()

    def create(self) -> int:
        """Create a new entity and return its ID."""
        entity_id = next(self._id_counter)
        self._alive_entities.add(entity_id)
        return entity_id

    def destroy(self, entity_id: int) -> None:
        """Mark an entity as destroyed."""
        self._alive_entities.discard(entity_id)

    def is_alive(self, entity_id: int) -> bool:
        """Check if entity exists."""
        return entity_id in self._alive_entities

    def all_entities(self) -> Generator[int, None, None]:
        """Iterate over all living entities."""
        yield from self._alive_entities

    def count(self) -> int:
        """Return number of living entities."""
        return len(self._alive_entities)
