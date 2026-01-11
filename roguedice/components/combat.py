"""Combat state component for tracking active combat."""

from dataclasses import dataclass, field
from typing import List, Optional
from ..core.component import Component


@dataclass
class CombatStateComponent(Component):
    """Active combat state."""

    in_combat: bool = False
    opponent_id: Optional[int] = None
    combat_tick: int = 0
    next_attack_tick: float = 0.0
    opponent_next_attack_tick: float = 0.0
    combat_log: List[str] = field(default_factory=list)

    # Combat results
    victory: Optional[bool] = None
    damage_dealt: int = 0
    damage_taken: int = 0

    def start_combat(self, opponent_id: int) -> None:
        """Initialize combat with an opponent."""
        self.in_combat = True
        self.opponent_id = opponent_id
        self.combat_tick = 0
        self.next_attack_tick = 0.0
        self.opponent_next_attack_tick = 0.0
        self.combat_log = ["Combat started!"]
        self.victory = None
        self.damage_dealt = 0
        self.damage_taken = 0

    def end_combat(self, victory: bool) -> None:
        """End combat with result."""
        self.in_combat = False
        self.victory = victory
        result = "VICTORY!" if victory else "DEFEAT..."
        self.combat_log.append(f"Combat ended: {result}")

    def add_log(self, message: str) -> None:
        """Add a message to combat log."""
        self.combat_log.append(message)

    def clear(self) -> None:
        """Clear combat state."""
        self.in_combat = False
        self.opponent_id = None
        self.combat_tick = 0
        self.next_attack_tick = 0.0
        self.opponent_next_attack_tick = 0.0
        self.victory = None
