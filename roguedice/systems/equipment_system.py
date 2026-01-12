"""Equipment system for managing equipped items and stat calculation."""

from typing import Optional

from ..core.system import System
from ..components.stats import StatsComponent
from ..components.equipment import EquipmentComponent
from ..components.inventory import InventoryComponent
from ..components.item import ItemComponent
from ..components.player import PlayerComponent
from ..models.enums import ItemType
from ..models.characters import get_character


class EquipmentSystem(System):
    """Handles equipping items and stat calculation."""

    priority = 80

    def equip_item(self, entity_id: int, item_id: int) -> Optional[int]:
        """
        Equip an item from inventory.

        Args:
            entity_id: Entity that's equipping
            item_id: Item entity to equip

        Returns:
            Previously equipped item ID, or None
        """
        equipment = self.world.get_component(entity_id, EquipmentComponent)
        inventory = self.world.get_component(entity_id, InventoryComponent)
        item = self.world.get_component(item_id, ItemComponent)

        if not all([equipment, inventory, item]):
            return None

        # Remove from inventory
        if not inventory.remove_item(item_id):
            return None

        # Equip based on type
        old_item = None
        if item.item_type == ItemType.WEAPON:
            old_item = equipment.equip_weapon(item_id)
        elif item.item_type == ItemType.ARMOR:
            old_item = equipment.equip_armor(item_id)
        elif item.item_type == ItemType.JEWELRY:
            old_item = equipment.equip_ring(item_id)

        # Put old item in inventory
        if old_item is not None:
            inventory.add_item(old_item)

        # Recalculate stats
        self.recalculate_stats(entity_id)

        return old_item

    def unequip_item(self, entity_id: int, slot: str) -> Optional[int]:
        """
        Unequip an item to inventory.

        Args:
            entity_id: Entity that's unequipping
            slot: "weapon", "armor", or "ring"

        Returns:
            Unequipped item ID, or None
        """
        equipment = self.world.get_component(entity_id, EquipmentComponent)
        inventory = self.world.get_component(entity_id, InventoryComponent)

        if not all([equipment, inventory]):
            return None

        # Check inventory space
        if inventory.is_full:
            return None

        # Unequip
        item_id = None
        if slot == "weapon":
            item_id = equipment.unequip_weapon()
        elif slot == "armor":
            item_id = equipment.unequip_armor()
        elif slot == "ring":
            item_id = equipment.unequip_ring()

        # Add to inventory
        if item_id is not None:
            inventory.add_item(item_id)
            self.recalculate_stats(entity_id)

        return item_id

    def recalculate_stats(self, entity_id: int) -> None:
        """
        Recalculate entity stats based on equipment and character.

        Args:
            entity_id: Entity to recalculate
        """
        stats = self.world.get_component(entity_id, StatsComponent)
        equipment = self.world.get_component(entity_id, EquipmentComponent)
        player = self.world.get_component(entity_id, PlayerComponent)

        if not all([stats, equipment]):
            return

        # Get character multipliers
        char = get_character(player.character_id if player else "warrior")

        # Base stats with character multipliers
        base_hp = int(100 * char.hp_mult)
        base_damage = 10 * char.damage_mult
        base_attack_speed = 1.0 * char.attack_speed_mult
        base_crit_chance = 0.05 * char.crit_chance_mult
        base_crit_mult = 2.0 * char.crit_damage_mult
        base_defense = int(5 * char.defense_mult)
        base_resistance = 0.0
        base_dodge = 0.0
        base_life_steal = char.life_steal_base
        base_true_damage = 0.0

        # Add bonuses from all equipped items
        for item_id in equipment.get_all_equipped():
            item = self.world.get_component(item_id, ItemComponent)
            if item:
                base_damage += item.damage_bonus
                base_attack_speed += item.attack_speed_bonus
                base_crit_chance += item.crit_chance_bonus
                base_crit_mult += item.crit_multiplier_bonus
                base_defense += item.defense_bonus
                base_hp += item.hp_bonus
                base_resistance += item.resistance_bonus
                base_dodge += item.dodge_bonus
                base_life_steal += item.life_steal_bonus
                base_true_damage += item.true_damage_bonus

        # Apply to stats
        old_hp_percent = stats.hp_percent
        stats.max_hp = max(1, int(base_hp))
        stats.current_hp = max(1, int(stats.max_hp * old_hp_percent))
        stats.base_damage = max(1, base_damage)
        stats.attack_speed = max(0.1, base_attack_speed)
        stats.crit_chance = min(1.0, max(0, base_crit_chance))
        stats.crit_multiplier = max(1.0, base_crit_mult)
        stats.defense = max(0, base_defense)
        stats.resistance = min(0.9, max(0, base_resistance))
        stats.dodge_chance = min(0.9, max(0, base_dodge))
        stats.life_steal = min(1.0, max(0, base_life_steal))
        stats.true_damage = max(0, base_true_damage)

    def update(self, delta_time: float) -> None:
        """Not used - equipment changes are event-driven."""
        pass
