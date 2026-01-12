"""Item component for item properties."""

from dataclasses import dataclass, field
from typing import List
from ..core.component import Component
from ..models.enums import ItemType, Rarity, ItemTheme, Element


@dataclass
class ItemComponent(Component):
    """Properties of an item."""

    name: str = ""
    item_type: ItemType = ItemType.WEAPON
    rarity: Rarity = Rarity.COMMON
    level: int = 1
    template_id: str = ""  # Reference to base template

    # Theme system
    theme: ItemTheme = ItemTheme.NONE
    element: Element = Element.NONE  # Only used if theme == ELEMENTAL

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
        """Get formatted display name with tier prefix and theme."""
        theme_prefix = f"[{self.theme_display}] " if self.theme != ItemTheme.NONE else ""
        return f"{theme_prefix}T{self.level}: {self.base_name}"

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

    @property
    def theme_display(self) -> str:
        """Get theme display string for UI."""
        if self.theme == ItemTheme.NONE:
            return ""
        if self.theme == ItemTheme.ELEMENTAL and self.element != Element.NONE:
            return f"{self.element.display_name} {self.theme.display_name}"
        return self.theme.display_name

    @property
    def theme_effect_description(self) -> str:
        """Get description of theme effect for tooltips."""
        if self.theme == ItemTheme.NONE:
            return ""
        elif self.theme == ItemTheme.CYBERPUNK:
            return "Bonus gold + Neural Hack reduces enemy damage"
        elif self.theme == ItemTheme.STEAMPUNK:
            return "Builds pressure, releases STEAM BURST!"
        elif self.theme == ItemTheme.MAGICAL:
            return "Mana Burst with Arcane Amplification"
        elif self.theme == ItemTheme.ELEMENTAL:
            return self._get_element_description()
        elif self.theme == ItemTheme.ANGELIC:
            return "Divine healing + Guardian Angel saves you once!"
        elif self.theme == ItemTheme.DEMONIC:
            return "Blood Pact: More damage at low HP + Soul Harvest"
        return ""

    def _get_element_description(self) -> str:
        """Get element-specific effect description."""
        if self.element == Element.FIRE:
            return "INFERNO: Stacking burns up to 3x damage!"
        elif self.element == Element.WATER:
            return "Tidal Wave: Flinch + Soaked (+25% dmg taken)"
        elif self.element == Element.WIND:
            return "Zephyr: Free Gust attacks + Dodge bonus"
        elif self.element == Element.EARTH:
            return "Fortress: Damage reduction + Tremor stuns"
        elif self.element == Element.ELECTRIC:
            return "Storm: Paralyze + bonus damage (Chain with Water!)"
        return ""
