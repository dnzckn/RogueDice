"""Factory for creating player entity."""

from typing import Optional

from ..core.world import World
from ..components.stats import StatsComponent
from ..components.position import PositionComponent
from ..components.player import PlayerComponent
from ..components.inventory import InventoryComponent
from ..components.equipment import EquipmentComponent
from ..components.combat import CombatStateComponent
from ..models.characters import get_character, CharacterTemplate
from ..models.persistent_data import PersistentData


class PlayerFactory:
    """Creates the player entity."""

    def __init__(self, world: World):
        self.world = world

    def create_player(
        self,
        name: str = "Hero",
        character_id: str = "warrior",
        persistent: Optional[PersistentData] = None,
    ) -> int:
        """
        Create the player entity with all required components.

        Args:
            name: Player name
            character_id: Character template ID
            persistent: Persistent data for applying upgrades

        Returns:
            Entity ID of created player
        """
        entity_id = self.world.create_entity()

        # Get character template
        character = get_character(character_id)

        # Calculate base stats with character modifiers
        base_hp = int(100 * character.hp_mult)
        base_damage = 10 * character.damage_mult
        base_crit = 0.05 * character.crit_chance_mult
        base_crit_mult = 2.0 * character.crit_damage_mult
        base_speed = 1.0 * character.attack_speed_mult
        base_defense = int(0 * character.defense_mult)  # 0 base defense
        base_life_steal = character.life_steal_base

        # Apply permanent upgrades
        if persistent:
            base_hp += int(persistent.get_upgrade_effect("vitality"))
            base_damage += persistent.get_upgrade_effect("strength")
            base_crit += persistent.get_upgrade_effect("precision")
            base_defense += int(persistent.get_upgrade_effect("fortitude"))
            base_speed += persistent.get_upgrade_effect("swiftness")
            base_life_steal += persistent.get_upgrade_effect("vampirism")

            # Apply minigame mastery bonuses
            mastery_bonuses = persistent.get_mastery_bonuses()
            if "crit" in mastery_bonuses:
                base_crit += mastery_bonuses["crit"]  # Timing mastery
            if "damage" in mastery_bonuses:
                base_damage += mastery_bonuses["damage"]  # Archery mastery

        # Stats
        stats = StatsComponent(
            max_hp=base_hp,
            current_hp=base_hp,
            base_damage=base_damage,
            attack_speed=base_speed,
            crit_chance=base_crit,
            crit_multiplier=base_crit_mult,
            defense=base_defense,
            life_steal=base_life_steal,
        )
        self.world.add_component(entity_id, stats)

        # Position (start at square 0)
        position = PositionComponent(square_index=0)
        self.world.add_component(entity_id, position)

        # Starting potions and gold
        starting_potions = 1
        starting_gold = 0
        gold_mult = character.gold_mult
        max_potions = 1

        if persistent:
            starting_potions = persistent.get_starting_potions()
            max_potions = starting_potions
            starting_gold = int(persistent.get_upgrade_effect("prosperity"))

            # Apply minigame mastery bonuses for gold and potions
            mastery_bonuses = persistent.get_mastery_bonuses()
            if "gold" in mastery_bonuses:
                gold_mult += mastery_bonuses["gold"]  # Roulette mastery
            if "potion" in mastery_bonuses:
                max_potions += int(mastery_bonuses["potion"])  # Claw mastery
                starting_potions += int(mastery_bonuses["potion"])

        # Player data
        player = PlayerComponent(
            name=name,
            character_id=character_id,
            potion_count=starting_potions,
            max_potions=max_potions,
            gold=starting_gold,
            gold_multiplier=gold_mult,
        )
        self.world.add_component(entity_id, player)

        # Inventory (still exists but largely unused with auto-sell)
        inventory = InventoryComponent(max_capacity=20)
        self.world.add_component(entity_id, inventory)

        # Equipment
        equipment = EquipmentComponent()
        self.world.add_component(entity_id, equipment)

        # Combat state
        combat = CombatStateComponent()
        self.world.add_component(entity_id, combat)

        return entity_id

    def get_character_info(self, character_id: str) -> CharacterTemplate:
        """Get character template info."""
        return get_character(character_id)
