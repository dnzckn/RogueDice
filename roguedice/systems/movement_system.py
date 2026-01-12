"""Movement system for player movement around the board."""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

from ..core.system import System
from ..components.position import PositionComponent, BOARD_SIZE
from ..components.player import PlayerComponent
from ..components.board_square import BoardSquareComponent
from ..utils.dice import roll_for_character, format_roll


@dataclass
class MoveResult:
    """Result of a movement action."""
    rolls: List[int]  # Individual die results
    modifier: int  # Flat modifier (e.g., +2 from "2d4+2")
    total: int  # Total movement
    roll_text: str  # Formatted roll string (e.g., "3+4+2=9")
    from_square: int
    to_square: int
    laps_completed: int
    new_round: int
    square_entity: Optional[int]
    square_component: Optional[BoardSquareComponent]
    # Extra info from special dice mechanics
    rolled_doubles: bool = False
    exploded: bool = False
    cursed: bool = False
    random_die: Optional[int] = None

    @property
    def dice(self) -> Tuple[int, ...]:
        """Legacy compatibility - returns rolls as tuple with total appended."""
        return tuple(self.rolls) + (self.total,)


class MovementSystem(System):
    """Handles player movement around the board."""

    priority = 10

    def __init__(self, board_factory=None):
        super().__init__()
        self.board_factory = board_factory

    def move_player(self, player_id: int) -> MoveResult:
        """
        Roll dice and move player using character's dice formula.

        Args:
            player_id: Entity ID of player

        Returns:
            MoveResult with movement info
        """
        position = self.world.get_component(player_id, PositionComponent)
        player = self.world.get_component(player_id, PlayerComponent)

        if not position or not player:
            raise ValueError("Player missing required components")

        # Roll using character's dice formula with special mechanics
        rolls, modifier, total, extra_info = roll_for_character(
            player.character_id,
            momentum=player.momentum,
            death_stacks=player.death_stacks,
        )
        roll_text = format_roll(rolls, modifier, total, extra_info)
        old_position = position.square_index

        # Update player roll info for UI
        player.last_roll_doubled = extra_info.get("rolled_doubles", False)
        player.last_roll_exploded = extra_info.get("exploded", False)
        player.last_roll_cursed = extra_info.get("cursed", False)

        # Handle doubles rolled (for Paladin shield)
        if extra_info.get("rolled_doubles"):
            player.on_doubles_rolled(total)

        # Move
        laps = position.advance(total, BOARD_SIZE)

        # Update round if lap completed
        if laps > 0:
            player.complete_lap()

        # Get landing square info
        square_entity = None
        square_component = None
        if self.board_factory:
            square_entity = self.board_factory.get_entity_at(position.square_index)
            square_component = self.board_factory.get_square_at(position.square_index)

        return MoveResult(
            rolls=rolls,
            modifier=modifier,
            total=total,
            roll_text=roll_text,
            from_square=old_position,
            to_square=position.square_index,
            laps_completed=laps,
            new_round=player.current_round,
            square_entity=square_entity,
            square_component=square_component,
            rolled_doubles=extra_info.get("rolled_doubles", False),
            exploded=extra_info.get("exploded", False),
            cursed=extra_info.get("cursed", False),
            random_die=extra_info.get("random_die"),
        )

    def get_player_position(self, player_id: int) -> int:
        """Get current player position."""
        position = self.world.get_component(player_id, PositionComponent)
        return position.square_index if position else 0

    def update(self, delta_time: float) -> None:
        """Not used - movement is event-driven."""
        pass
