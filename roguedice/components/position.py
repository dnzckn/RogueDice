"""Position component for board location."""

from dataclasses import dataclass
from ..core.component import Component


BOARD_SIZE = 40


@dataclass
class PositionComponent(Component):
    """Position on the game board."""

    square_index: int = 0  # 0-39 for 40 squares

    def advance(self, spaces: int, board_size: int = BOARD_SIZE) -> int:
        """
        Move forward by spaces.

        Returns:
            Number of laps (full board circuits) completed.
        """
        old_pos = self.square_index
        new_pos = old_pos + spaces
        self.square_index = new_pos % board_size

        # Calculate laps completed
        laps = new_pos // board_size
        return laps

    def set_position(self, index: int) -> None:
        """Set position directly."""
        self.square_index = index % BOARD_SIZE

    @property
    def side(self) -> int:
        """Get which side of the board (0-3)."""
        return self.square_index // 10

    @property
    def position_on_side(self) -> int:
        """Get position on current side (0-9)."""
        return self.square_index % 10
