"""Board square component for square properties."""

from dataclasses import dataclass, field
from typing import Optional, List
from ..core.component import Component
from ..models.enums import SquareType


@dataclass
class BoardSquareComponent(Component):
    """Properties of a board square."""

    index: int = 0
    square_type: SquareType = SquareType.EMPTY
    name: str = ""

    # For monster squares - supports multiple monsters (1vX combat)
    monster_entity_ids: List[int] = field(default_factory=list)

    # For item squares
    item_tier: int = 1

    # Visual
    sprite_name: str = "grass"

    @property
    def has_monster(self) -> bool:
        """Check if square has any monsters."""
        return len(self.monster_entity_ids) > 0

    @property
    def monster_entity_id(self) -> Optional[int]:
        """Get first monster ID (backwards compatibility)."""
        return self.monster_entity_ids[0] if self.monster_entity_ids else None

    @property
    def monster_count(self) -> int:
        """Get number of monsters on this square."""
        return len(self.monster_entity_ids)

    def place_monster(self, monster_id: int) -> None:
        """Add a monster to this square."""
        if monster_id not in self.monster_entity_ids:
            self.monster_entity_ids.append(monster_id)

    def clear_monster(self, monster_id: Optional[int] = None) -> Optional[int]:
        """Remove a monster from square. If no ID given, removes first monster."""
        if not self.monster_entity_ids:
            return None

        if monster_id is None:
            # Remove first monster
            return self.monster_entity_ids.pop(0)
        elif monster_id in self.monster_entity_ids:
            self.monster_entity_ids.remove(monster_id)
            return monster_id
        return None

    def clear_all_monsters(self) -> List[int]:
        """Remove all monsters from square, return their IDs."""
        monster_ids = self.monster_entity_ids.copy()
        self.monster_entity_ids.clear()
        return monster_ids

    @property
    def is_corner(self) -> bool:
        """Check if this is a corner square."""
        return self.square_type in (
            SquareType.CORNER_START,
            SquareType.CORNER_SHOP,
            SquareType.CORNER_REST,
            SquareType.CORNER_BOSS,
        )

    @property
    def is_passable(self) -> bool:
        """Check if player can land here without event."""
        return self.square_type == SquareType.EMPTY

    @property
    def triggers_combat(self) -> bool:
        """Check if this square triggers combat."""
        return self.square_type == SquareType.MONSTER and self.has_monster

    @property
    def grants_item(self) -> bool:
        """Check if this square grants an item."""
        return self.square_type == SquareType.ITEM
