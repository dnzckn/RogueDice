"""Factory for creating board entities."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..core.world import World
from ..components.board_square import BoardSquareComponent
from ..models.enums import SquareType


class BoardFactory:
    """Creates board square entities from template."""

    SQUARE_TYPE_MAP = {
        "EMPTY": SquareType.EMPTY,
        "MONSTER": SquareType.MONSTER,
        "ITEM": SquareType.ITEM,
        "BLESSING": SquareType.BLESSING,
        "CORNER_START": SquareType.CORNER_START,
        "CORNER_SHOP": SquareType.CORNER_SHOP,
        "CORNER_REST": SquareType.CORNER_REST,
        "CORNER_BOSS": SquareType.CORNER_BOSS,
        "SPECIAL": SquareType.SPECIAL,
    }

    def __init__(self, world: World, data_path: Optional[Path] = None):
        self.world = world
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "board"
        self.board_data = self._load_board()
        self.square_entities: Dict[int, int] = {}  # index -> entity_id

    def _load_board(self) -> Dict:
        """Load board layout from JSON file."""
        filepath = self.data_path / "default_board.json"
        if filepath.exists():
            with open(filepath) as f:
                return json.load(f)
        return self._default_board()

    def _default_board(self) -> Dict:
        """Generate default board if no file exists."""
        squares = []
        blessing_indices = {5, 15, 25, 35}  # Blessing shrines

        for i in range(40):
            if i == 0:
                square = {"index": i, "type": "CORNER_START", "name": "Start"}
            elif i == 10:
                square = {"index": i, "type": "CORNER_SHOP", "name": "Merchant"}
            elif i == 20:
                square = {"index": i, "type": "CORNER_REST", "name": "Inn"}
            elif i == 30:
                square = {"index": i, "type": "CORNER_BOSS", "name": "Boss Arena"}
            elif i in blessing_indices:
                square = {"index": i, "type": "BLESSING", "name": "Shrine"}
            elif i % 3 == 1:
                square = {"index": i, "type": "MONSTER", "name": f"Danger Zone"}
            elif i % 3 == 2:
                square = {"index": i, "type": "ITEM", "name": f"Treasure"}
            else:
                square = {"index": i, "type": "EMPTY", "name": f"Path"}
            squares.append(square)

        return {"name": "Default Board", "size": 40, "squares": squares}

    def create_board(self) -> List[int]:
        """
        Create all board square entities.

        Returns:
            List of entity IDs for all squares
        """
        square_data = self.board_data.get("squares", [])
        entity_ids = []

        for square_info in square_data:
            entity_id = self._create_square(square_info)
            entity_ids.append(entity_id)
            self.square_entities[square_info["index"]] = entity_id

        return entity_ids

    def _create_square(self, square_info: Dict) -> int:
        """Create a single board square entity."""
        entity_id = self.world.create_entity()

        square_type = self.SQUARE_TYPE_MAP.get(
            square_info.get("type", "EMPTY"),
            SquareType.EMPTY
        )

        square = BoardSquareComponent(
            index=square_info.get("index", 0),
            square_type=square_type,
            name=square_info.get("name", ""),
            sprite_name=square_info.get("sprite", "grass"),
        )

        # Set item tier based on position (higher tiers later in board)
        if square_type == SquareType.ITEM:
            square.item_tier = 1 + square_info.get("index", 0) // 10

        self.world.add_component(entity_id, square)
        return entity_id

    def get_square_at(self, index: int) -> Optional[BoardSquareComponent]:
        """Get the board square component at an index."""
        entity_id = self.square_entities.get(index)
        if entity_id is not None:
            return self.world.get_component(entity_id, BoardSquareComponent)
        return None

    def get_entity_at(self, index: int) -> Optional[int]:
        """Get the entity ID of square at index."""
        return self.square_entities.get(index)
