"""Spawn system for monster spawning on the board."""

import random
from typing import List

from ..core.system import System
from ..components.board_square import BoardSquareComponent
from ..models.enums import SquareType
from ..factories.monster_factory import MonsterFactory


class SpawnSystem(System):
    """Handles monster spawning on the board."""

    SPAWN_INTERVAL_ROUNDS = 4  # Spawn new monsters every 4 rounds

    priority = 50

    def __init__(self, monster_factory: MonsterFactory):
        super().__init__()
        self.monster_factory = monster_factory
        self.last_spawn_round = 0

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

    def _spawn_monsters(self, current_round: int) -> List[int]:
        """Spawn monsters on random empty monster squares."""
        spawned_squares = []

        # Get all monster squares without monsters
        empty_monster_squares = []
        for entity_id, square in self.world.query(BoardSquareComponent):
            if (square.square_type == SquareType.MONSTER and
                not square.has_monster):
                empty_monster_squares.append((entity_id, square))

        if not empty_monster_squares:
            return []

        # Spawn on random subset (30-50% of empty squares)
        num_to_spawn = max(1, len(empty_monster_squares) // 3)
        squares_to_spawn = random.sample(
            empty_monster_squares,
            min(num_to_spawn, len(empty_monster_squares))
        )

        for square_entity_id, square in squares_to_spawn:
            # Create monster scaled to current round
            monster_id = self.monster_factory.create_monster(current_round)

            square.place_monster(monster_id)
            spawned_squares.append(square.index)

        return spawned_squares

    def initial_spawn(self, current_round: int = 1) -> List[int]:
        """
        Spawn initial monsters at game start.

        Returns:
            List of square indices where monsters spawned
        """
        spawned_squares = []

        # Spawn on ~40% of monster squares initially
        for entity_id, square in self.world.query(BoardSquareComponent):
            if square.square_type == SquareType.MONSTER:
                if random.random() < 0.4:
                    monster_id = self.monster_factory.create_monster(current_round)
                    square.place_monster(monster_id)
                    spawned_squares.append(square.index)

        return spawned_squares

    def update(self, delta_time: float) -> None:
        """Not used - spawning is event-driven."""
        pass
