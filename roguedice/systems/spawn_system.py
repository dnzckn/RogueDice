"""Spawn system for monster and boon spawning on the board."""

import random
from typing import List, Tuple

from ..core.system import System
from ..components.board_square import BoardSquareComponent
from ..models.enums import SquareType
from ..factories.monster_factory import MonsterFactory


class SpawnSystem(System):
    """Handles monster and boon spawning on the board."""

    SPAWN_INTERVAL_ROUNDS = 4  # Spawn new monsters every 4 rounds

    # Special square indices that should never have content spawned
    SPECIAL_INDICES = {0, 5, 8, 10, 15, 18, 20, 25, 28, 30, 35, 38}  # corners, arcade, curse

    priority = 50

    def __init__(self, monster_factory: MonsterFactory):
        super().__init__()
        self.monster_factory = monster_factory
        self.last_spawn_round = 0

    def _get_empty_squares(self, exclude_index: int = -1) -> List[Tuple[int, BoardSquareComponent]]:
        """Get all EMPTY squares that can have content spawned on them."""
        empty_squares = []
        for entity_id, square in self.world.query(BoardSquareComponent):
            if square.index in self.SPECIAL_INDICES:
                continue
            if square.index == exclude_index:
                continue
            if square.square_type == SquareType.EMPTY:
                empty_squares.append((entity_id, square))
        return empty_squares

    def check_and_spawn(self, current_round: int) -> List[int]:
        """
        Check if it's time to spawn monsters and do so.

        Args:
            current_round: Current game round

        Returns:
            List of square indices where monsters spawned
        """
        # Calculate spawn round (every 4 rounds)
        spawn_round = (current_round // self.SPAWN_INTERVAL_ROUNDS) * self.SPAWN_INTERVAL_ROUNDS

        if spawn_round > self.last_spawn_round and spawn_round > 0:
            self.last_spawn_round = spawn_round
            return self._spawn_monsters(current_round)

        return []

    def _spawn_monsters(self, current_round: int, count: int = 0) -> List[int]:
        """
        Spawn monsters on random empty squares.

        Args:
            current_round: Current game round for scaling
            count: Number of monsters to spawn (0 = auto based on available squares)
        """
        spawned_squares = []
        empty_squares = self._get_empty_squares()

        if not empty_squares:
            return []

        # Determine how many to spawn
        if count <= 0:
            count = max(1, len(empty_squares) // 4)  # ~25% of empty squares

        # Don't spawn more than available
        count = min(count, len(empty_squares))
        squares_to_spawn = random.sample(empty_squares, count)

        for square_entity_id, square in squares_to_spawn:
            # Create monster scaled to current round
            monster_id = self.monster_factory.create_monster(current_round)
            # Convert square to MONSTER type and place monster
            square.square_type = SquareType.MONSTER
            square.place_monster(monster_id)
            spawned_squares.append(square.index)

        return spawned_squares

    def spawn_monster_on_square(self, square: BoardSquareComponent, current_round: int) -> bool:
        """
        Spawn a single monster on a specific square.
        Converts the square to MONSTER type.

        Returns:
            True if monster was spawned, False if square was invalid
        """
        if square.index in self.SPECIAL_INDICES:
            return False

        monster_id = self.monster_factory.create_monster(current_round)
        square.square_type = SquareType.MONSTER
        square.place_monster(monster_id)
        return True

    def initial_spawn(self, current_round: int = 1) -> List[int]:
        """
        Spawn initial content at game start.
        - Spawns 18-22 monsters (fills almost the entire board)
        - Spawns 4-6 boons (items/blessings)

        Returns:
            List of square indices where content spawned
        """
        spawned_squares = []
        empty_squares = self._get_empty_squares()

        if not empty_squares:
            return []

        # Shuffle for random distribution
        random.shuffle(empty_squares)

        # Spawn 18-22 monsters initially (fill most of the board with danger!)
        num_monsters = random.randint(18, 22)
        num_monsters = min(num_monsters, len(empty_squares))

        for i in range(num_monsters):
            entity_id, square = empty_squares[i]
            monster_id = self.monster_factory.create_monster(current_round)
            square.square_type = SquareType.MONSTER
            square.place_monster(monster_id)
            spawned_squares.append(square.index)

        # Spawn 4-6 boons on remaining empty squares
        remaining_empty = empty_squares[num_monsters:]
        num_boons = random.randint(4, 6)
        num_boons = min(num_boons, len(remaining_empty))

        for i in range(num_boons):
            entity_id, square = remaining_empty[i]
            # 50% item, 50% blessing
            if random.random() < 0.5:
                square.square_type = SquareType.ITEM
                square.name = "Treasure"
            else:
                square.square_type = SquareType.BLESSING
                square.name = "Shrine"
            spawned_squares.append(square.index)

        return spawned_squares

    def update(self, delta_time: float) -> None:
        """Not used - spawning is event-driven."""
        pass
