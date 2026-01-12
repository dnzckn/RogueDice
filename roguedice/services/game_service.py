"""Game service - main game loop and orchestration."""

from typing import Optional, List
from dataclasses import dataclass, field
import random
import copy

from ..core.world import World
from ..factories.board_factory import BoardFactory
from ..factories.player_factory import PlayerFactory
from ..factories.item_factory import ItemFactory
from ..factories.monster_factory import MonsterFactory
from ..systems.movement_system import MovementSystem, MoveResult
from ..systems.combat_system import CombatSystem, CombatResult
from ..systems.loot_system import LootSystem
from ..systems.spawn_system import SpawnSystem
from ..systems.equipment_system import EquipmentSystem
from ..components.stats import StatsComponent
from ..components.player import PlayerComponent
from ..components.position import PositionComponent
from ..components.inventory import InventoryComponent
from ..components.equipment import EquipmentComponent
from ..components.item import ItemComponent
from ..components.board_square import BoardSquareComponent
from ..models.enums import SquareType, ItemType
from ..models.persistent_data import PersistentData, UPGRADES
from ..models.characters import CHARACTERS, get_character
from ..models.blessings import get_random_blessing, get_shop_blessings, Blessing, BlessingType


@dataclass
class MerchantInventory:
    """Items and blessings available at merchant."""
    items: List[int] = field(default_factory=list)
    item_prices: dict = field(default_factory=dict)
    blessings: List[Blessing] = field(default_factory=list)
    potion_price: int = 50
    has_potion: bool = True


@dataclass
class TurnResult:
    """Result of a complete turn."""
    move_result: MoveResult
    combat_result: Optional[CombatResult] = None
    pending_item: Optional[int] = None  # Item awaiting equip/sell decision
    pending_item_component: Optional[ItemComponent] = None
    blessing_received: Optional[Blessing] = None
    gold_earned: int = 0
    healed: bool = False
    monsters_spawned: List[int] = field(default_factory=list)
    opened_merchant: bool = False
    game_over: bool = False
    victory: bool = False  # Boss defeated
    is_boss_fight: bool = False


class GameService:
    """
    Main game service that orchestrates all game logic.
    """

    BOSS_SPAWN_ROUND = 21  # Boss spawns after round 20

    def __init__(self):
        self.world = World()
        self.player_id: Optional[int] = None
        self.is_game_over = False
        self.is_victory = False

        # Persistent data (survives between runs)
        self.persistent = PersistentData.load()

        # Factories
        self.board_factory: Optional[BoardFactory] = None
        self.player_factory: Optional[PlayerFactory] = None
        self.item_factory: Optional[ItemFactory] = None
        self.monster_factory: Optional[MonsterFactory] = None

        # Systems
        self.movement_system: Optional[MovementSystem] = None
        self.combat_system: Optional[CombatSystem] = None
        self.loot_system: Optional[LootSystem] = None
        self.spawn_system: Optional[SpawnSystem] = None
        self.equipment_system: Optional[EquipmentSystem] = None

        # Merchant
        self.merchant_inventory: Optional[MerchantInventory] = None

        # Boss tracking
        self.boss_entity_id: Optional[int] = None
        self.boss_active: bool = False

    def new_game(
        self,
        player_name: str = "Hero",
        character_id: Optional[str] = None,
    ) -> None:
        """Start a new game."""
        self.world = World()
        self.is_game_over = False
        self.is_victory = False
        self.boss_entity_id = None
        self.boss_active = False

        # Use selected character from persistent data if not specified
        if character_id is None:
            character_id = self.persistent.selected_character

        # Initialize factories
        self.board_factory = BoardFactory(self.world)
        self.player_factory = PlayerFactory(self.world)
        self.item_factory = ItemFactory(self.world)
        self.monster_factory = MonsterFactory(self.world)

        # Create board
        self.board_factory.create_board()

        # Create player with character and upgrades
        self.player_id = self.player_factory.create_player(
            name=player_name,
            character_id=character_id,
            persistent=self.persistent,
        )

        # Initialize systems
        self.movement_system = MovementSystem(self.board_factory)
        self.movement_system.world = self.world

        self.combat_system = CombatSystem()
        self.combat_system.world = self.world

        self.loot_system = LootSystem(self.item_factory)
        self.loot_system.world = self.world

        self.spawn_system = SpawnSystem(self.monster_factory)
        self.spawn_system.world = self.world

        self.equipment_system = EquipmentSystem()
        self.equipment_system.world = self.world

        # Initial monster spawn
        self.spawn_system.initial_spawn()

        # Grant starting item if unlocked (rare_start feature)
        if self.persistent.has_feature("rare_start"):
            self._grant_starting_item()

    def _grant_starting_item(self) -> None:
        """Grant a random Rare item at game start (if unlocked)."""
        from ..models.enums import Rarity
        item_id = self.item_factory.create_item(
            current_round=1,
            rarity=Rarity.RARE,
        )
        # Auto-equip the starting item
        if item_id:
            item = self.world.get_component(item_id, ItemComponent)
            equipment = self.world.get_component(self.player_id, EquipmentComponent)
            if item and equipment:
                if item.is_weapon:
                    equipment.weapon = item_id
                elif item.is_armor:
                    equipment.armor = item_id
                elif item.is_jewelry:
                    equipment.jewelry_slots[0] = item_id
                self.equipment_system.recalculate_stats(self.player_id)

    def take_turn(self) -> TurnResult:
        """
        Execute a complete turn.

        Returns:
            TurnResult with all turn events
        """
        if self.is_game_over or self.is_victory or not self.player_id:
            return TurnResult(
                move_result=MoveResult(
                    rolls=[0],
                    modifier=0,
                    total=0,
                    roll_text="0=0",
                    from_square=0,
                    to_square=0,
                    laps_completed=0,
                    new_round=0,
                    square_entity=None,
                    square_component=None,
                ),
                game_over=self.is_game_over,
                victory=self.is_victory,
            )

        player = self.world.get_component(self.player_id, PlayerComponent)
        player_stats = self.world.get_component(self.player_id, StatsComponent)

        # Move player
        move_result = self.movement_system.move_player(self.player_id)

        result = TurnResult(move_result=move_result)

        # Check for monster spawn (every 4 rounds)
        if move_result.laps_completed > 0:
            result.monsters_spawned = self.spawn_system.check_and_spawn(
                player.current_round
            )

            # Check for boss spawn
            if player.current_round >= self.BOSS_SPAWN_ROUND and not player.boss_defeated:
                self._spawn_boss()

        # Process landing square
        square = move_result.square_component
        if square:
            self._process_square(square, result, player, player_stats)

        # Force boss fight at round 21+ if boss is active and not yet fought
        if (player.current_round >= self.BOSS_SPAWN_ROUND and
            self.boss_active and
            not player.boss_defeated and
            not result.combat_result):
            # The dragon has awakened - force the confrontation!
            boss_square = self.board_factory.get_square_at(30)
            if boss_square and boss_square.monster_entity_id:
                self._force_boss_fight(result, player, player_stats, boss_square)

        # Check game over
        if not player_stats.is_alive():
            self.is_game_over = True
            result.game_over = True
            self._end_run()

        return result

    def _spawn_boss(self) -> None:
        """Spawn the boss at the boss arena."""
        if self.boss_active:
            return

        # Get boss square (index 30)
        boss_square = self.board_factory.get_square_at(30)
        if boss_square and not boss_square.has_monster:
            player = self.world.get_component(self.player_id, PlayerComponent)
            # Create a powerful boss monster
            boss_id = self.monster_factory.create_monster(
                current_round=player.current_round + 5,  # Boss is stronger
                template_id="boss_dragon",
            )
            if boss_id:
                boss_square.place_monster(boss_id)
                self.boss_entity_id = boss_id
                self.boss_active = True

    def _force_boss_fight(
        self,
        result: TurnResult,
        player: PlayerComponent,
        player_stats: StatsComponent,
        boss_square: 'BoardSquareComponent',
    ) -> None:
        """Force the boss fight - the dragon has broken free!"""
        result.is_boss_fight = True

        # Apply blessing bonuses
        self._apply_blessing_combat_bonuses(player, player_stats)

        # Combat with the boss!
        combat_result = self.combat_system.run_full_combat(
            self.player_id,
            boss_square.monster_entity_id,
        )
        result.combat_result = combat_result

        if combat_result.victory:
            # Earn gold
            result.gold_earned = combat_result.gold_earned
            player.add_gold(combat_result.gold_earned)
            player.monsters_killed += 1

            # Clear the boss
            self.world.destroy_entity(boss_square.monster_entity_id)
            boss_square.clear_monster()

            # Boss defeated!
            player.boss_defeated = True
            self.boss_active = False
            self.is_victory = True
            result.victory = True
            self.persistent.record_boss_victory()

    def _process_square(
        self,
        square: BoardSquareComponent,
        result: TurnResult,
        player: PlayerComponent,
        player_stats: StatsComponent,
    ) -> None:
        """Process landing on a square."""

        if square.triggers_combat and square.monster_entity_id:
            # Check if this is the boss
            is_boss = square.monster_entity_id == self.boss_entity_id
            result.is_boss_fight = is_boss

            # Apply blessing bonuses to stats temporarily
            self._apply_blessing_combat_bonuses(player, player_stats)

            # Combat!
            combat_result = self.combat_system.run_full_combat(
                self.player_id,
                square.monster_entity_id,
            )
            result.combat_result = combat_result

            if combat_result.victory:
                # Earn gold
                result.gold_earned = combat_result.gold_earned
                player.add_gold(combat_result.gold_earned)
                player.monsters_killed += 1

                # Check for item drop
                dropped_item = self.loot_system.roll_monster_drop(
                    square.monster_entity_id,
                    player.current_round,
                )
                if dropped_item:
                    result.pending_item = dropped_item
                    result.pending_item_component = self.world.get_component(
                        dropped_item, ItemComponent
                    )
                    combat_result.item_dropped = True

                # Clear monster from square
                self.world.destroy_entity(square.monster_entity_id)
                square.clear_monster()

                # Check if boss was defeated
                if is_boss:
                    player.boss_defeated = True
                    self.boss_active = False
                    self.is_victory = True
                    result.victory = True
                    unlock = self.persistent.record_boss_victory()
                    self.persistent.save()

            # Remove temporary blessing bonuses
            self._remove_blessing_combat_bonuses(player, player_stats)

        elif square.grants_item:
            # Grant item from square (pending decision)
            item_id = self.loot_system.generate_item(player.current_round)
            result.pending_item = item_id
            result.pending_item_component = self.world.get_component(
                item_id, ItemComponent
            )

        elif square.square_type == SquareType.BLESSING:
            # Grant blessing
            include_rare = player.current_round >= 10
            double = self.persistent.has_feature("double_blessings")

            blessing = get_random_blessing(include_rare)
            player.add_blessing(blessing)
            result.blessing_received = blessing

            # Apply immediate effect for permanent blessings
            if blessing.is_permanent:
                self._apply_permanent_blessing(blessing, player_stats)

            # Second blessing if double_blessings unlocked
            if double:
                blessing2 = get_random_blessing(include_rare)
                player.add_blessing(blessing2)
                if blessing2.is_permanent:
                    self._apply_permanent_blessing(blessing2, player_stats)

        elif square.square_type == SquareType.CORNER_REST:
            # Heal at inn
            character = get_character(player.character_id)
            heal_mult = character.heal_on_rest_mult
            if heal_mult > 1.0:
                # Paladin bonus healing
                heal_amount = int(player_stats.max_hp * heal_mult)
                player_stats.heal(heal_amount)
            else:
                player_stats.full_heal()
            result.healed = True

        elif square.square_type == SquareType.CORNER_SHOP:
            # Open merchant
            self._generate_merchant_inventory(player.current_round)
            result.opened_merchant = True

        elif square.square_type == SquareType.CURSE:
            # CURSE: Spawn monsters on random empty monster squares!
            result.monsters_spawned = self._trigger_curse(player.current_round)

    def _trigger_curse(self, current_round: int) -> List[int]:
        """Trigger curse effect - spawn 2-4 monsters on random empty squares."""
        import random
        spawned_squares = []

        # Get all empty monster squares
        empty_monster_squares = []
        for entity_id, square in self.world.query(BoardSquareComponent):
            if (square.square_type == SquareType.MONSTER and
                not square.has_monster):
                empty_monster_squares.append((entity_id, square))

        if not empty_monster_squares:
            return []

        # Spawn 2-4 monsters (more at higher rounds)
        num_to_spawn = min(len(empty_monster_squares), random.randint(2, 4))

        squares_to_spawn = random.sample(empty_monster_squares, num_to_spawn)

        for square_entity_id, square in squares_to_spawn:
            monster_id = self.monster_factory.create_monster(current_round)
            square.place_monster(monster_id)
            spawned_squares.append(square.index)

        return spawned_squares

    def _apply_blessing_combat_bonuses(
        self, player: PlayerComponent, stats: StatsComponent
    ) -> None:
        """Apply temporary blessing bonuses before combat."""
        for blessing in player.active_blessings:
            if blessing.blessing_type == BlessingType.CRIT_BOOST:
                stats.crit_chance += blessing.value
            elif blessing.blessing_type == BlessingType.DAMAGE_BOOST:
                stats.base_damage += blessing.value
            elif blessing.blessing_type == BlessingType.DEFENSE_BOOST:
                stats.defense += int(blessing.value)
            elif blessing.blessing_type == BlessingType.ATTACK_SPEED:
                stats.attack_speed += blessing.value
            elif blessing.blessing_type == BlessingType.LIFE_STEAL:
                stats.life_steal += blessing.value
            elif blessing.blessing_type == BlessingType.DODGE:
                stats.dodge_chance += blessing.value

    def _remove_blessing_combat_bonuses(
        self, player: PlayerComponent, stats: StatsComponent
    ) -> None:
        """Remove temporary blessing bonuses after combat."""
        for blessing in player.active_blessings:
            if blessing.is_permanent:
                continue  # Permanent blessings already applied to base
            if blessing.blessing_type == BlessingType.CRIT_BOOST:
                stats.crit_chance -= blessing.value
            elif blessing.blessing_type == BlessingType.DAMAGE_BOOST:
                stats.base_damage -= blessing.value
            elif blessing.blessing_type == BlessingType.DEFENSE_BOOST:
                stats.defense -= int(blessing.value)
            elif blessing.blessing_type == BlessingType.ATTACK_SPEED:
                stats.attack_speed -= blessing.value
            elif blessing.blessing_type == BlessingType.LIFE_STEAL:
                stats.life_steal -= blessing.value
            elif blessing.blessing_type == BlessingType.DODGE:
                stats.dodge_chance -= blessing.value

    def _apply_permanent_blessing(
        self, blessing: Blessing, stats: StatsComponent
    ) -> None:
        """Apply a permanent blessing effect to base stats."""
        if blessing.blessing_type == BlessingType.MAX_HP:
            stats.max_hp += int(blessing.value)
            stats.current_hp += int(blessing.value)

    def _generate_merchant_inventory(self, current_round: int) -> None:
        """Generate items and blessings for merchant."""
        self.merchant_inventory = MerchantInventory()

        # Generate 3-5 items
        num_items = random.randint(3, 5)
        for _ in range(num_items):
            item_id = self.item_factory.create_item(current_round)
            item = self.world.get_component(item_id, ItemComponent)
            if item:
                # Price is 2-3x sell value
                price = int(item.sell_value * random.uniform(2.0, 3.0))
                self.merchant_inventory.items.append(item_id)
                self.merchant_inventory.item_prices[item_id] = price

        # Generate 1-2 blessings
        self.merchant_inventory.blessings = get_shop_blessings(2, current_round)

        # Potion price scales with round
        self.merchant_inventory.potion_price = 50 + current_round * 5
        self.merchant_inventory.has_potion = True

    def equip_pending_item(self, item_id: int, slot_index: int = 0) -> int:
        """
        Equip a pending item, selling the replaced item.

        Returns:
            Gold earned from selling old item (0 if slot was empty)
        """
        if not self.player_id:
            return 0

        equipment = self.world.get_component(self.player_id, EquipmentComponent)
        player = self.world.get_component(self.player_id, PlayerComponent)
        item = self.world.get_component(item_id, ItemComponent)

        if not item or not equipment:
            return 0

        # Get old item in slot
        old_item_id = None
        if item.item_type == ItemType.WEAPON:
            old_item_id = equipment.weapon
            equipment.weapon = item_id
        elif item.item_type == ItemType.ARMOR:
            # Check if character can equip armor
            character = get_character(player.character_id)
            if not character.can_equip_armor:
                # Can't equip armor - auto-sell
                return self.sell_item(item_id)
            old_item_id = equipment.armor
            equipment.armor = item_id
        elif item.item_type == ItemType.JEWELRY:
            old_item_id = equipment.ring
            equipment.ring = item_id

        # Sell old item
        gold_earned = 0
        if old_item_id:
            old_item = self.world.get_component(old_item_id, ItemComponent)
            if old_item:
                gold_earned = old_item.sell_value
                player.add_gold(gold_earned)
            self.world.destroy_entity(old_item_id)

        # Recalculate stats
        self.equipment_system.recalculate_stats(self.player_id)
        player.items_collected += 1

        return gold_earned

    def sell_item(self, item_id: int) -> int:
        """
        Sell item directly for gold.

        Returns:
            Gold earned
        """
        if not self.player_id:
            return 0

        player = self.world.get_component(self.player_id, PlayerComponent)
        item = self.world.get_component(item_id, ItemComponent)

        if not item:
            return 0

        gold = item.sell_value
        player.add_gold(gold)
        self.world.destroy_entity(item_id)

        return gold

    def use_potion(self) -> bool:
        """Use potion to fully heal. Returns True if successful."""
        if not self.player_id:
            return False

        player = self.world.get_component(self.player_id, PlayerComponent)
        stats = self.world.get_component(self.player_id, StatsComponent)

        if player.use_potion():
            stats.full_heal()
            return True
        return False

    def purchase_merchant_item(self, item_id: int) -> bool:
        """Purchase item from merchant. Returns True if successful."""
        if not self.merchant_inventory or item_id not in self.merchant_inventory.item_prices:
            return False

        player = self.world.get_component(self.player_id, PlayerComponent)
        price = self.merchant_inventory.item_prices[item_id]

        if player.spend_gold(price):
            self.merchant_inventory.items.remove(item_id)
            del self.merchant_inventory.item_prices[item_id]
            return True
        return False

    def purchase_merchant_blessing(self, blessing_index: int) -> bool:
        """Purchase blessing from merchant. Returns True if successful."""
        if not self.merchant_inventory:
            return False

        if blessing_index >= len(self.merchant_inventory.blessings):
            return False

        blessing = self.merchant_inventory.blessings[blessing_index]
        player = self.world.get_component(self.player_id, PlayerComponent)
        stats = self.world.get_component(self.player_id, StatsComponent)

        if player.spend_gold(blessing.shop_price):
            self.merchant_inventory.blessings.pop(blessing_index)
            player.add_blessing(blessing)
            if blessing.is_permanent:
                self._apply_permanent_blessing(blessing, stats)
            return True
        return False

    def purchase_merchant_potion(self) -> bool:
        """Purchase potion from merchant. Returns True if successful."""
        if not self.merchant_inventory or not self.merchant_inventory.has_potion:
            return False

        player = self.world.get_component(self.player_id, PlayerComponent)

        if player.potion_count >= player.max_potions:
            return False

        if player.spend_gold(self.merchant_inventory.potion_price):
            player.add_potion()
            self.merchant_inventory.has_potion = False
            return True
        return False

    def continue_after_victory(self) -> None:
        """Continue playing after boss victory (for fun, no new rewards)."""
        player = self.world.get_component(self.player_id, PlayerComponent)
        player.continuing_after_boss = True
        self.is_victory = False  # Allow more turns

    def end_run(self) -> None:
        """End the current run and transfer gold to persistent."""
        self._end_run()

    def _end_run(self) -> None:
        """Internal: End run and save persistent data."""
        if not self.player_id:
            return

        player = self.world.get_component(self.player_id, PlayerComponent)
        if player and not player.continuing_after_boss:
            # Only add gold if not continuing (already added during victory)
            self.persistent.record_run_end(
                player.current_round,
                player.monsters_killed,
                player.gold,
            )
            self.persistent.save()

    # === Accessors ===

    def get_player_stats(self) -> Optional[StatsComponent]:
        """Get player stats."""
        if self.player_id:
            return self.world.get_component(self.player_id, StatsComponent)
        return None

    def get_player_data(self) -> Optional[PlayerComponent]:
        """Get player data."""
        if self.player_id:
            return self.world.get_component(self.player_id, PlayerComponent)
        return None

    def get_player_position(self) -> int:
        """Get player's current position."""
        if self.player_id:
            pos = self.world.get_component(self.player_id, PositionComponent)
            return pos.square_index if pos else 0
        return 0

    def get_player_inventory(self) -> List[int]:
        """Get player's inventory item IDs."""
        if self.player_id:
            inv = self.world.get_component(self.player_id, InventoryComponent)
            return inv.items if inv else []
        return []

    def get_player_equipment(self) -> Optional[EquipmentComponent]:
        """Get player's equipment."""
        if self.player_id:
            return self.world.get_component(self.player_id, EquipmentComponent)
        return None

    def get_item(self, item_id: int) -> Optional[ItemComponent]:
        """Get item component by ID."""
        return self.world.get_component(item_id, ItemComponent)

    def get_board_squares(self) -> List[BoardSquareComponent]:
        """Get all board squares."""
        return [
            square
            for _, square in self.world.query(BoardSquareComponent)
        ]

    def get_character_info(self, character_id: str = None):
        """Get character template info."""
        if character_id is None and self.player_id:
            player = self.world.get_component(self.player_id, PlayerComponent)
            character_id = player.character_id if player else "warrior"
        return get_character(character_id or "warrior")
