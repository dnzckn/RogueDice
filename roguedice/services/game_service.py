"""Game service - main game loop and orchestration."""

from typing import Optional, List
from dataclasses import dataclass, field

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
from ..models.enums import SquareType


@dataclass
class TurnResult:
    """Result of a complete turn."""
    move_result: MoveResult
    combat_result: Optional[CombatResult] = None
    item_received: Optional[int] = None
    item_component: Optional[ItemComponent] = None
    gold_earned: int = 0
    healed: bool = False
    monsters_spawned: List[int] = field(default_factory=list)
    game_over: bool = False


class GameService:
    """
    Main game service that orchestrates all game logic.
    """

    def __init__(self):
        self.world = World()
        self.player_id: Optional[int] = None
        self.is_game_over = False

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

    def new_game(self, player_name: str = "Hero") -> None:
        """Start a new game."""
        self.world = World()
        self.is_game_over = False

        # Initialize factories
        self.board_factory = BoardFactory(self.world)
        self.player_factory = PlayerFactory(self.world)
        self.item_factory = ItemFactory(self.world)
        self.monster_factory = MonsterFactory(self.world)

        # Create board
        self.board_factory.create_board()

        # Create player
        self.player_id = self.player_factory.create_player(player_name)

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

    def take_turn(self) -> TurnResult:
        """
        Execute a complete turn.

        Returns:
            TurnResult with all turn events
        """
        if self.is_game_over or not self.player_id:
            return TurnResult(
                move_result=MoveResult(
                    dice=(0, 0, 0),
                    from_square=0,
                    to_square=0,
                    laps_completed=0,
                    new_round=0,
                    square_entity=None,
                    square_component=None,
                ),
                game_over=True,
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

        # Process landing square
        square = move_result.square_component
        if square:
            self._process_square(square, result, player, player_stats)

        # Check game over
        if not player_stats.is_alive():
            self.is_game_over = True
            result.game_over = True

        return result

    def _process_square(
        self,
        square: BoardSquareComponent,
        result: TurnResult,
        player: PlayerComponent,
        player_stats: StatsComponent,
    ) -> None:
        """Process landing on a square."""

        if square.triggers_combat and square.monster_entity_id:
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
                    result.item_received = dropped_item
                    result.item_component = self.world.get_component(
                        dropped_item, ItemComponent
                    )
                    self.loot_system.add_item_to_player(self.player_id, dropped_item)
                    combat_result.item_dropped = True

                # Clear monster from square
                self.world.destroy_entity(square.monster_entity_id)
                square.clear_monster()

        elif square.grants_item:
            # Grant item from square
            item_id = self.loot_system.generate_item(player.current_round)
            result.item_received = item_id
            result.item_component = self.world.get_component(item_id, ItemComponent)
            self.loot_system.add_item_to_player(self.player_id, item_id)

        elif square.square_type == SquareType.CORNER_REST:
            # Heal at inn
            player_stats.full_heal()
            result.healed = True

        elif square.square_type == SquareType.CORNER_SHOP:
            # Shop - could implement shopping later
            pass

    def equip_item(self, item_id: int) -> bool:
        """Equip an item from inventory."""
        if self.player_id and self.equipment_system:
            self.equipment_system.equip_item(self.player_id, item_id)
            return True
        return False

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
