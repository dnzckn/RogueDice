"""Monster component for monster-specific data."""

from dataclasses import dataclass, field
from typing import List, Dict
from ..core.component import Component


@dataclass
class MonsterComponent(Component):
    """Monster-specific data."""

    name: str = ""
    template_id: str = ""
    tier: int = 1  # Difficulty tier

    # Visual
    sprite_name: str = "goblin"

    # Loot
    drop_chance: float = 0.5
    drop_table_id: str = ""

    # Experience/rewards
    gold_reward: int = 10
    xp_reward: int = 10

    # Special moves (for bosses) - list of {name, damage_mult, animation, effect}
    special_moves: List[Dict] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Get display name with tier indicator."""
        if self.tier > 1:
            return f"{self.name} (Tier {self.tier})"
        return self.name
