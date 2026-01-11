"""Stats component for combat entities."""

from dataclasses import dataclass, field
from ..core.component import Component


@dataclass
class StatsComponent(Component):
    """Combat statistics for player and monsters."""

    # Health
    max_hp: int = 100
    current_hp: int = 100

    # Offense
    base_damage: float = 10.0
    attack_speed: float = 1.0       # Attacks per second
    crit_chance: float = 0.05       # 0.0 to 1.0
    crit_multiplier: float = 2.0
    true_damage: float = 0.0        # Ignores defense
    area_damage: float = 0.0        # Splash damage
    life_steal: float = 0.0         # 0.0 to 1.0, % of damage healed

    # Defense
    defense: int = 0                # Flat damage reduction
    resistance: float = 0.0         # % damage reduction (0.0 to 1.0)
    dodge_chance: float = 0.0       # 0.0 to 1.0

    def is_alive(self) -> bool:
        """Check if entity is still alive."""
        return self.current_hp > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage and return actual damage taken."""
        actual_damage = min(amount, self.current_hp)
        self.current_hp -= actual_damage
        return actual_damage

    def heal(self, amount: int) -> int:
        """Heal and return actual healing done."""
        missing_hp = self.max_hp - self.current_hp
        actual_heal = min(amount, missing_hp)
        self.current_hp += actual_heal
        return actual_heal

    def full_heal(self) -> None:
        """Restore HP to maximum."""
        self.current_hp = self.max_hp

    @property
    def hp_percent(self) -> float:
        """Get HP as percentage."""
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0
