"""ECS World container - the heart of the entity component system."""

from typing import Type, TypeVar, Optional, Iterator, Tuple, List, Dict
from collections import defaultdict

from .entity import EntityManager
from .component import Component, T
from .system import System


class World:
    """
    The ECS World - container for all entities and their components.

    This is the main interface for the game to interact with entities.
    """

    def __init__(self):
        self.entities = EntityManager()
        self._components: Dict[Type[Component], Dict[int, Component]] = defaultdict(dict)
        self._systems: List[System] = []

    def create_entity(self) -> int:
        """Create a new entity and return its ID."""
        return self.entities.create()

    def destroy_entity(self, entity_id: int) -> None:
        """Destroy an entity and all its components."""
        for component_store in self._components.values():
            component_store.pop(entity_id, None)
        self.entities.destroy(entity_id)

    def add_component(self, entity_id: int, component: Component) -> None:
        """Attach a component to an entity."""
        self._components[type(component)][entity_id] = component

    def remove_component(self, entity_id: int, component_type: Type[T]) -> Optional[T]:
        """Remove a component from an entity and return it."""
        return self._components[component_type].pop(entity_id, None)

    def get_component(self, entity_id: int, component_type: Type[T]) -> Optional[T]:
        """Get a specific component from an entity."""
        return self._components[component_type].get(entity_id)

    def has_component(self, entity_id: int, component_type: Type[Component]) -> bool:
        """Check if entity has a component."""
        return entity_id in self._components[component_type]

    def get_all_components(self, component_type: Type[T]) -> Dict[int, T]:
        """Get all entities with a specific component type."""
        return dict(self._components[component_type])

    def query(self, *component_types: Type[Component]) -> Iterator[Tuple]:
        """
        Query entities that have ALL specified components.

        Yields tuples of (entity_id, component1, component2, ...).
        """
        if not component_types:
            return

        # Find entities with first component type
        first_type = component_types[0]
        candidate_entities = set(self._components[first_type].keys())

        # Intersect with entities having other component types
        for comp_type in component_types[1:]:
            candidate_entities &= set(self._components[comp_type].keys())

        # Yield entities with all their requested components
        for entity_id in candidate_entities:
            if self.entities.is_alive(entity_id):
                components = tuple(
                    self._components[comp_type][entity_id]
                    for comp_type in component_types
                )
                yield (entity_id, *components)

    def query_single(self, *component_types: Type[Component]) -> Optional[Tuple]:
        """Query for a single entity (useful for player, etc.)."""
        for result in self.query(*component_types):
            return result
        return None

    def register_system(self, system: System) -> None:
        """Register a system with this world."""
        system.world = self
        self._systems.append(system)
        # Sort by priority
        self._systems.sort(key=lambda s: s.priority)

    def get_system(self, system_type: Type[System]) -> Optional[System]:
        """Get a registered system by type."""
        for system in self._systems:
            if isinstance(system, system_type):
                return system
        return None

    def update(self, delta_time: float = 0.0) -> None:
        """Update all registered systems."""
        for system in self._systems:
            system.update(delta_time)
