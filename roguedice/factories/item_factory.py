"""Factory for creating item entities."""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from ..core.world import World
from ..components.item import ItemComponent
from ..models.enums import ItemType, Rarity
from ..utils.probability import roll_rarity, calculate_item_level, scale_stat


class ItemFactory:
    """Creates item entities from templates."""

    def __init__(self, world: World, data_path: Optional[Path] = None):
        self.world = world
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "items"
        self.weapon_templates = self._load_templates("weapons.json")
        self.armor_templates = self._load_templates("armor.json")
        self.jewelry_templates = self._load_templates("jewelry.json")

    def _load_templates(self, filename: str) -> List[Dict]:
        """Load item templates from JSON file."""
        filepath = self.data_path / filename
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
                return data.get("templates", [])
        return []

    def create_item(
        self,
        current_round: int,
        item_type: Optional[ItemType] = None,
        rarity: Optional[Rarity] = None,
    ) -> int:
        """
        Create a random item entity.

        Args:
            current_round: Current game round (affects level)
            item_type: Specific item type, or None for random
            rarity: Specific rarity, or None for random roll

        Returns:
            Entity ID of created item
        """
        # Determine type
        if item_type is None:
            item_type = random.choice(list(ItemType))

        # Determine rarity
        if rarity is None:
            rarity = roll_rarity()

        # Determine level
        level = calculate_item_level(current_round)

        # Get templates for this type
        templates = self._get_templates(item_type)
        if not templates:
            # Fallback: create basic item
            return self._create_basic_item(item_type, rarity, level)

        # Pick random template
        template = random.choice(templates)

        # Create entity
        entity_id = self.world.create_entity()

        # Generate item component
        item = self._generate_item(template, item_type, rarity, level)
        self.world.add_component(entity_id, item)

        return entity_id

    def _get_templates(self, item_type: ItemType) -> List[Dict]:
        """Get templates for item type."""
        if item_type == ItemType.WEAPON:
            return self.weapon_templates
        elif item_type == ItemType.ARMOR:
            return self.armor_templates
        else:
            return self.jewelry_templates

    def _generate_item(
        self,
        template: Dict,
        item_type: ItemType,
        rarity: Rarity,
        level: int,
    ) -> ItemComponent:
        """Generate item component from template."""
        # Pick variant name based on rarity
        variants = template.get("variants", ["Basic"])
        variant_index = min(rarity.value - 1, len(variants) - 1)
        variant = variants[variant_index]

        base_name = template.get("name", "Item")
        name = f"{variant} {base_name}"  # Level displayed via T{level}: prefix in UI

        item = ItemComponent(
            name=name,
            item_type=item_type,
            rarity=rarity,
            level=level,
            template_id=template.get("id", ""),
        )

        # Apply stats based on type
        if item_type == ItemType.WEAPON:
            item.damage_bonus = scale_stat(
                template.get("base_damage", 10), level, rarity
            )
            item.attack_speed_bonus = template.get("base_attack_speed", 0) * rarity.multiplier * 0.1
            item.crit_chance_bonus = template.get("base_crit_chance", 0.05) * rarity.multiplier
            item.crit_multiplier_bonus = template.get("base_crit_multiplier", 0) * rarity.multiplier
            item.true_damage_bonus = template.get("base_true_damage", 0) * rarity.multiplier

            # Higher rarities get life steal
            if rarity.value >= Rarity.RARE.value:
                item.life_steal_bonus = 0.03 * rarity.multiplier

        elif item_type == ItemType.ARMOR:
            item.defense_bonus = int(scale_stat(
                template.get("base_defense", 5), level, rarity
            ))
            item.hp_bonus = int(scale_stat(
                template.get("base_hp", 20), level, rarity
            ))
            item.resistance_bonus = template.get("base_resistance", 0) * rarity.multiplier
            item.dodge_bonus = template.get("base_dodge", 0) * rarity.multiplier

        else:  # Jewelry
            item.damage_bonus = template.get("base_damage_bonus", 0) * rarity.multiplier * level * 0.5
            item.hp_bonus = int(template.get("base_hp_bonus", 0) * rarity.multiplier * level * 0.3)
            item.defense_bonus = int(template.get("base_defense_bonus", 0) * rarity.multiplier)
            item.attack_speed_bonus = template.get("base_attack_speed_bonus", 0) * rarity.multiplier
            item.crit_chance_bonus = template.get("base_crit_chance", 0) * rarity.multiplier
            item.crit_multiplier_bonus = template.get("base_crit_multiplier", 0) * rarity.multiplier
            item.life_steal_bonus = template.get("base_life_steal", 0) * rarity.multiplier
            item.resistance_bonus = template.get("base_resistance", 0) * rarity.multiplier
            item.dodge_bonus = template.get("base_dodge", 0) * rarity.multiplier

            if template.get("special_effect"):
                item.special_effects.append(template["special_effect"])

        return item

    def _create_basic_item(
        self,
        item_type: ItemType,
        rarity: Rarity,
        level: int,
    ) -> int:
        """Create a basic item without template."""
        entity_id = self.world.create_entity()

        names = {
            ItemType.WEAPON: "Weapon",
            ItemType.ARMOR: "Armor",
            ItemType.JEWELRY: "Trinket",
        }

        item = ItemComponent(
            name=f"{rarity.name} {names[item_type]} +{level}",
            item_type=item_type,
            rarity=rarity,
            level=level,
        )

        # Apply basic scaling
        mult = rarity.multiplier * (1 + level * 0.15)
        if item_type == ItemType.WEAPON:
            item.damage_bonus = 5 * mult
        elif item_type == ItemType.ARMOR:
            item.defense_bonus = int(3 * mult)
            item.hp_bonus = int(15 * mult)
        else:
            item.crit_chance_bonus = 0.02 * mult

        self.world.add_component(entity_id, item)
        return entity_id
