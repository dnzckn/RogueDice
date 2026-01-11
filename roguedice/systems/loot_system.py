"""Loot system for item generation and drops."""

import random
from typing import Optional

from ..core.system import System
from ..components.item import ItemComponent
from ..components.monster import MonsterComponent
from ..components.player import PlayerComponent
from ..components.inventory import InventoryComponent
from ..models.enums import ItemType
from ..factories.item_factory import ItemFactory


class LootSystem(System):
    """Handles item drops and generation."""

    priority = 150

    def __init__(self, item_factory: ItemFactory):
        super().__init__()
        self.item_factory = item_factory

    def generate_item(
        self,
        current_round: int,
        item_type: Optional[ItemType] = None,
    ) -> int:
        """
        Generate a new item.

        Args:
            current_round: Current game round
            item_type: Specific type or None for random

        Returns:
            Entity ID of created item
        """
        return self.item_factory.create_item(current_round, item_type)

    def roll_monster_drop(
        self,
        monster_id: int,
        current_round: int,
    ) -> Optional[int]:
        """
        Roll for item drop from monster.

        Args:
            monster_id: Entity ID of defeated monster
            current_round: Current game round

        Returns:
            Entity ID of dropped item, or None if no drop
        """
        monster = self.world.get_component(monster_id, MonsterComponent)
        if not monster:
            return None

        # Check drop chance
        if random.random() < monster.drop_chance:
            return self.item_factory.create_item(current_round)

        return None

    def add_item_to_player(self, player_id: int, item_id: int) -> bool:
        """
        Add item to player inventory.

        Args:
            player_id: Entity ID of player
            item_id: Entity ID of item

        Returns:
            True if added successfully
        """
        inventory = self.world.get_component(player_id, InventoryComponent)
        player = self.world.get_component(player_id, PlayerComponent)

        if inventory and inventory.add_item(item_id):
            if player:
                player.items_collected += 1
            return True
        return False

    def update(self, delta_time: float) -> None:
        """Not used - loot is event-driven."""
        pass
