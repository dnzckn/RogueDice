"""Item component for item properties."""

from dataclasses import dataclass, field
from typing import List
from ..core.component import Component
from ..models.enums import ItemType, Rarity


@dataclass
class ItemComponent(Component):
    """Properties of an item."""

    name: str = ""
    item_type: ItemType = ItemType.WEAPON
    rarity: Rarity = Rarity.COMMON
    level: int = 1
    template_id: str = ""  # Reference to base template

    # Stat modifiers (added to base stats when equipped)
    damage_bonus: float = 0.0
    attack_speed_bonus: float = 0.0
    crit_chance_bonus: float = 0.0
    crit_multiplier_bonus: float = 0.0
    true_damage_bonus: float = 0.0
    life_steal_bonus: float = 0.0

    defense_bonus: int = 0
    hp_bonus: int = 0
    resistance_bonus: float = 0.0
    dodge_bonus: float = 0.0

    # Special effects (for jewelry)
    special_effects: List[str] = field(default_factory=list)

    @property
    def sell_value(self) -> int:
        """Calculate gold value when selling this item."""
        base_value = 10
        level_factor = 1 + (self.level - 1) * 0.2  # +20% per level
        rarity_multiplier = self.rarity.multiplier
        return int(base_value * level_factor * rarity_multiplier)

    @property
    def display_name(self) -> str:
        """Get formatted display name with tier prefix."""
        return f"T{self.level}: {self.base_name}"

    @property
    def base_name(self) -> str:
        """Get the item name without any level suffix."""
        # Strip old format " +{level}" if present
        name = self.name
        suffix = f" +{self.level}"
        if name.endswith(suffix):
            name = name[:-len(suffix)]
        return name

    @property
    def stat_summary(self) -> str:
        """Get a short summary of item stats."""
        stats = []
        if self.damage_bonus > 0:
            stats.append(f"+{self.damage_bonus:.0f} dmg")
        if self.attack_speed_bonus > 0:
            stats.append(f"+{self.attack_speed_bonus * 100:.0f}% spd")
        if self.crit_chance_bonus > 0:
            stats.append(f"+{self.crit_chance_bonus * 100:.0f}% crit")
        if self.defense_bonus > 0:
            stats.append(f"+{self.defense_bonus} def")
        if self.hp_bonus > 0:
            stats.append(f"+{self.hp_bonus} HP")
        if self.life_steal_bonus > 0:
            stats.append(f"+{self.life_steal_bonus * 100:.0f}% ls")
        if self.dodge_bonus > 0:
            stats.append(f"+{self.dodge_bonus * 100:.0f}% dodge")
        return ", ".join(stats) if stats else "no bonuses"

    @property
    def is_weapon(self) -> bool:
        return self.item_type == ItemType.WEAPON

    @property
    def is_armor(self) -> bool:
        return self.item_type == ItemType.ARMOR

    @property
    def is_jewelry(self) -> bool:
        return self.item_type == ItemType.JEWELRY
