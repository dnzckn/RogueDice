"""Board square component for square properties."""

from dataclasses import dataclass
from typing import Optional
from ..core.component import Component
from ..models.enums import SquareType


@dataclass
class BoardSquareComponent(Component):
    """Properties of a board square."""

    index: int = 0
    square_type: SquareType = SquareType.EMPTY
    name: str = ""

    # For monster squares
    has_monster: bool = False
    monster_entity_id: Optional[int] = None

    # For item squares
    item_tier: int = 1

    # Visual
    sprite_name: str = "grass"

    def place_monster(self, monster_id: int) -> None:
        """Place a monster on this square."""
        self.has_monster = True
        self.monster_entity_id = monster_id

    def clear_monster(self) -> Optional[int]:
        """Remove monster from square, return its ID."""
        monster_id = self.monster_entity_id
        self.has_monster = False
        self.monster_entity_id = None
        return monster_id

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
