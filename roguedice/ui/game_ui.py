"""Pygame-based pixel art game UI with polished graphics and battle animations."""

import pygame
import sys
import math
import random
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

from ..services.game_service import GameService, TurnResult
from ..components.board_square import BoardSquareComponent
from ..components.item import ItemComponent
from ..models.enums import SquareType, Rarity, ItemType
from ..models.persistent_data import UPGRADES
from ..models.characters import CHARACTERS, get_character
from .sprites import sprites, PALETTE, RARITY_SCHEMES
from .battle_scene import BattleScene, BattleSpeed


@dataclass
class ItemSlot:
    """UI item slot with position for hover detection."""
    rect: pygame.Rect
    item_id: Optional[int]
    slot_type: str


@dataclass
class DiceAnimation:
    """Dice rolling animation state."""
    active: bool = False
    timer: float = 0.0
    duration: float = 1.2
    final_values: List[int] = None
    current_frame: int = 0
    # Per-die animation state
    die_offsets: List[Tuple[float, float]] = None  # x, y offsets for bounce
    die_rotations: List[float] = None  # rotation angles
    die_settled: List[bool] = None  # which dice have stopped
    settle_times: List[float] = None  # when each die settles
    show_total: bool = False
    total_scale: float = 1.0


@dataclass
class PlayerMovement:
    """Player token movement animation state."""
    current_pos: int = 0  # Current visual position (square index)
    target_pos: int = 0   # Target position to move to
    progress: float = 1.0  # 0.0 = at current_pos, 1.0 = at target_pos
    path: List[int] = None  # Squares to traverse
    path_index: int = 0  # Current index in path
    hop_height: float = 0.0  # Current hop height for bounce effect


class GameUI:
    """Main game UI using pygame with polished pixel art and battle scenes."""

    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 768
    BOARD_SIZE = 500
    SQUARE_SIZE = 45
    FPS = 60

    def __init__(self):
        pygame.init()
        pygame.display.set_caption("RogueDice")

        self.screen = pygame.display.set_mode(
            (self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        )
        self.clock = pygame.time.Clock()

        # Load fonts
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.font_tiny = pygame.font.Font(None, 14)

        self.game = GameService()

        self.last_turn_result: Optional[TurnResult] = None
        self.combat_log: List[str] = []
        self.message_log: List[str] = []

        # Game states
        self.state = "character_select"
        self.selected_character_index = 0
        self.pending_item_id: Optional[int] = None

        # Item slots for hover detection
        self.item_slots: List[ItemSlot] = []
        self.mouse_pos = (0, 0)
        self.hovered_slot: Optional[ItemSlot] = None

        # Animations
        self.dice_anim = DiceAnimation()
        self.player_movement = PlayerMovement()
        self.particle_effects: List[Dict] = []
        self.screen_shake = 0.0
        self.transition_alpha = 0

        # Battle scene
        self.battle_scene = BattleScene(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.pending_turn_result: Optional[TurnResult] = None

        # Cached surfaces
        self._bg_surface = None
        self._board_surface = None

    def run(self) -> None:
        """Main game loop."""
        running = True

        while running:
            dt = self.clock.tick(self.FPS) / 1000.0
            self.mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event)

            self._update(dt)
            self._draw()

            pygame.display.flip()

        pygame.quit()
        sys.exit()

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle key press events."""
        # Handle battle scene input first
        if self.battle_scene.is_active():
            self._handle_battle_keys(event)
            return

        if self.state == "character_select":
            self._handle_character_select_keys(event)
        elif self.state == "playing":
            self._handle_playing_keys(event)
        elif self.state == "item_choice":
            self._handle_item_choice_keys(event)
        elif self.state == "merchant":
            self._handle_merchant_keys(event)
        elif self.state == "game_over":
            self._handle_game_over_keys(event)
        elif self.state == "victory":
            self._handle_victory_keys(event)
        elif self.state == "settings":
            self._handle_settings_keys(event)

    def _handle_battle_keys(self, event: pygame.event.Event) -> None:
        """Handle keys during battle animation."""
        # Speed controls
        if event.key == pygame.K_1:
            self.battle_scene.set_speed(BattleSpeed.NORMAL)
        elif event.key == pygame.K_2:
            self.battle_scene.set_speed(BattleSpeed.FAST)
        elif event.key == pygame.K_3:
            self.battle_scene.set_speed(BattleSpeed.FASTER)
        elif event.key == pygame.K_4:
            self.battle_scene.set_speed(BattleSpeed.INSTANT)
        elif event.key == pygame.K_SPACE:
            # SPACE immediately finishes the battle
            self._finish_battle()

    def _handle_character_select_keys(self, event: pygame.event.Event) -> None:
        """Handle keys in character select screen."""
        character_ids = list(CHARACTERS.keys())
        cols = 2
        rows = (len(character_ids) + 1) // 2

        if event.key in (pygame.K_UP, pygame.K_w):
            self.selected_character_index = (self.selected_character_index - cols) % len(character_ids)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected_character_index = (self.selected_character_index + cols) % len(character_ids)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.selected_character_index = (self.selected_character_index - 1) % len(character_ids)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.selected_character_index = (self.selected_character_index + 1) % len(character_ids)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            char_id = character_ids[self.selected_character_index]
            char = CHARACTERS[char_id]

            if self.game.persistent.is_character_unlocked(char_id):
                self._start_game(char_id)
            elif self.game.persistent.spend_gold(char.cost):
                self.game.persistent.unlocked_characters.append(char_id)
                self.game.persistent.save()
                self._start_game(char_id)
        elif event.key == pygame.K_ESCAPE:
            char_id = self.game.persistent.selected_character
            if not self.game.persistent.is_character_unlocked(char_id):
                char_id = "warrior"
            self._start_game(char_id)

    def _start_game(self, char_id: str):
        """Start a new game with selected character."""
        self.game.persistent.selected_character = char_id
        self.game.persistent.save()
        self.game.new_game(character_id=char_id)
        self.state = "playing"
        self._board_surface = None  # Reset cached board
        self._stone_surface = None  # Reset stone surface cache
        sprites.clear_cache("dragon")  # Clear dragon sprites to use updated drawing
        # Initialize player movement at starting position
        start_pos = self.game.get_player_position() or 0
        self.player_movement = PlayerMovement(
            current_pos=start_pos,
            target_pos=start_pos,
            progress=1.0,
            path=None,
            path_index=0
        )
        char = CHARACTERS[char_id]
        self.message_log = [
            f"Playing as {char.name}!",
            f"Dice: {char.dice_description}",
            "Press SPACE to roll."
        ]
        self._add_particles(self.WINDOW_WIDTH // 2, 100, PALETTE['gold'], 20)

    def _handle_playing_keys(self, event: pygame.event.Event) -> None:
        """Handle keys during normal gameplay."""
        if event.key == pygame.K_SPACE and not self.dice_anim.active:
            self._take_turn()
        elif event.key == pygame.K_p:
            if self.game.use_potion():
                self.message_log.append("Potion used! HP restored.")
                self._add_particles(700, 200, PALETTE['green'], 15)
            else:
                self.message_log.append("No potion!")
            self.message_log = self.message_log[-8:]
        elif event.key == pygame.K_r and self.game.is_game_over:
            self.state = "game_over"
        elif event.key == pygame.K_ESCAPE:
            self.state = "settings"

    def _handle_item_choice_keys(self, event: pygame.event.Event) -> None:
        """Handle keys when choosing to equip or sell an item."""
        if not self.pending_item_id:
            self.state = "playing"
            return

        if event.key == pygame.K_e:
            gold = self.game.equip_pending_item(self.pending_item_id)
            if gold > 0:
                self.message_log.append(f"Equipped! +{gold}g")
            else:
                self.message_log.append("Equipped!")
            self._add_particles(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2, PALETTE['green'], 15)
            self.pending_item_id = None
            self.state = "playing"
        elif event.key in (pygame.K_s, pygame.K_ESCAPE):
            gold = self.game.sell_item(self.pending_item_id)
            self.message_log.append(f"Sold for {gold}g!")
            self._add_particles(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2, PALETTE['gold'], 15)
            self.pending_item_id = None
            self.state = "playing"
        self.message_log = self.message_log[-8:]

    def _handle_merchant_keys(self, event: pygame.event.Event) -> None:
        """Handle keys at merchant."""
        merchant = self.game.merchant_inventory
        if not merchant:
            self.state = "playing"
            return

        if event.key == pygame.K_ESCAPE:
            self.state = "playing"
        elif event.key == pygame.K_p:
            if self.game.purchase_merchant_potion():
                self.message_log.append("Bought potion!")
                self._add_particles(self.WINDOW_WIDTH // 2, 400, PALETTE['green'], 10)
        elif event.key == pygame.K_b and merchant.blessings:
            if self.game.purchase_merchant_blessing(0):
                self.message_log.append("Bought blessing!")
                self._add_particles(self.WINDOW_WIDTH // 2, 300, PALETTE['purple'], 10)
        elif event.key == pygame.K_n and len(merchant.blessings) > 1:
            if self.game.purchase_merchant_blessing(1):
                self.message_log.append("Bought blessing!")
        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
            idx = event.key - pygame.K_1
            if idx < len(merchant.items):
                item_id = merchant.items[idx]
                if self.game.purchase_merchant_item(item_id):
                    self.pending_item_id = item_id
                    self.state = "item_choice"
        self.message_log = self.message_log[-8:]

    def _handle_game_over_keys(self, event: pygame.event.Event) -> None:
        """Handle keys on game over screen."""
        upgrade_keys = {
            pygame.K_1: "vitality", pygame.K_2: "strength", pygame.K_3: "precision",
            pygame.K_4: "fortitude", pygame.K_5: "swiftness", pygame.K_6: "vampirism",
            pygame.K_7: "prosperity",
        }
        if event.key in upgrade_keys:
            if self.game.persistent.purchase_upgrade(upgrade_keys[event.key]):
                self.game.persistent.save()
                self.message_log.append("Upgraded!")
                self._add_particles(300, 200, PALETTE['cyan'], 10)

        char_keys = {
            pygame.K_q: "rogue", pygame.K_w: "berserker", pygame.K_e: "paladin",
            pygame.K_t: "gambler", pygame.K_y: "mage", pygame.K_u: "monk",
            pygame.K_i: "vampire", pygame.K_o: "necromancer", pygame.K_j: "jester",
            pygame.K_k: "avatar",
        }
        if event.key in char_keys:
            char_id = char_keys[event.key]
            if char_id in CHARACTERS and not self.game.persistent.is_character_unlocked(char_id):
                if self.game.persistent.unlock_character(char_id, CHARACTERS[char_id].cost):
                    self.game.persistent.save()
                    self.message_log.append(f"Unlocked {CHARACTERS[char_id].name}!")
                    self._add_particles(600, 400, PALETTE['gold'], 20)

        if event.key == pygame.K_r:
            self.state = "character_select"
        self.message_log = self.message_log[-8:]

    def _handle_victory_keys(self, event: pygame.event.Event) -> None:
        """Handle keys on victory screen."""
        if event.key == pygame.K_c:
            self.game.continue_after_victory()
            self.state = "playing"
            self.message_log.append("Continuing! No more rewards.")
        elif event.key in (pygame.K_e, pygame.K_RETURN):
            self.game.end_run()
            self.state = "game_over"

    def _handle_settings_keys(self, event: pygame.event.Event) -> None:
        """Handle keys in settings menu."""
        if event.key == pygame.K_ESCAPE:
            self.state = "playing"
        elif event.key == pygame.K_1:
            self.battle_scene.set_speed(BattleSpeed.NORMAL)
        elif event.key == pygame.K_2:
            self.battle_scene.set_speed(BattleSpeed.FAST)
        elif event.key == pygame.K_3:
            self.battle_scene.set_speed(BattleSpeed.FASTER)
        elif event.key == pygame.K_4:
            self.battle_scene.set_speed(BattleSpeed.INSTANT)

    def _take_turn(self) -> None:
        """Execute a turn with dice animation."""
        if self.game.is_game_over:
            self.state = "game_over"
            return
        if self.game.is_victory:
            self.state = "victory"
            return

        # Clear combat log from previous fight
        self.combat_log = []

        # Get starting position before the turn
        start_pos = self.game.get_player_position() or 0

        result = self.game.take_turn()
        self.last_turn_result = result

        # Calculate movement path (square by square around the board)
        end_pos = self.game.get_player_position() or 0
        total_move = result.move_result.total
        path = []
        for i in range(total_move + 1):
            path.append((start_pos + i) % 40)

        # Start player movement animation
        self.player_movement = PlayerMovement(
            current_pos=start_pos,
            target_pos=end_pos,
            progress=0.0,
            path=path,
            path_index=0,
            hop_height=0.0
        )

        # Initialize per-die animation data
        num_dice = len(result.move_result.rolls)
        settle_times = [0.4 + i * 0.15 for i in range(num_dice)]  # Staggered settling

        # Start dice animation
        self.dice_anim = DiceAnimation(
            active=True,
            timer=0,
            duration=max(settle_times) + 0.4,  # Extra time after last die settles
            final_values=result.move_result.rolls,
            die_offsets=[(0.0, 0.0) for _ in range(num_dice)],
            die_rotations=[random.uniform(0, 360) for _ in range(num_dice)],
            die_settled=[False for _ in range(num_dice)],
            settle_times=settle_times,
            show_total=False,
            total_scale=0.0,
        )

        # Reset cached board
        self._board_surface = None

        self.message_log.append(f"Rolled {result.move_result.roll_text}!")

        # Check for combat - start battle scene
        if result.combat_result:
            self.pending_turn_result = result
            self._start_battle(result)
            return  # Don't process rest until battle finishes

        # Process non-combat results immediately
        self._process_turn_result(result)

    def _start_battle(self, result: TurnResult) -> None:
        """Start the Pokemon-style battle scene."""
        player = self.game.get_player_data()
        stats = self.game.get_player_stats()

        if not player or not stats or not result.combat_result:
            return

        is_boss = result.is_boss_fight

        # Get monster name from combat result
        monster_name = result.combat_result.monster_name or "Monster"

        # Map monster name to sprite type
        monster_type_map = {
            "goblin": "goblin", "skeleton warrior": "skeleton", "skeleton": "skeleton",
            "dire wolf": "wolf", "wolf": "wolf", "giant spider": "spider", "spider": "spider",
            "orc brute": "orc", "orc": "orc", "cave troll": "troll", "troll": "troll",
            "lesser demon": "demon", "demon": "demon", "vampire lord": "vampire", "vampire": "vampire",
            "lich king": "lich", "lich": "lich", "ancient dragon": "dragon", "dragon": "dragon",
            "slime": "slime", "bat": "bat", "ghost": "ghost", "zombie": "zombie",
        }
        monster_type = monster_type_map.get(monster_name.lower(), "goblin")

        if is_boss:
            monster_type = "dragon"
            monster_name = "Ancient Dragon"

        # Get monster HP from combat result if available
        monster_max_hp = 50 + player.current_round * 10
        if is_boss:
            monster_max_hp = 200 + player.current_round * 20

        # Start battle scene
        self.battle_scene.start_battle(
            char_id=player.character_id,
            monster_type=monster_type,
            monster_name=monster_name,
            is_boss=is_boss,
            combat_result=result.combat_result,
            player_max_hp=stats.max_hp,
            monster_max_hp=monster_max_hp,
            player_start_hp=stats.current_hp + result.combat_result.damage_taken,  # HP before damage
            monster_start_hp=monster_max_hp,
        )

    def _finish_battle(self) -> None:
        """Finish battle and process turn result."""
        self.battle_scene.dismiss()

        if self.pending_turn_result:
            result = self.pending_turn_result
            self.pending_turn_result = None

            # Add combat results to log
            self.combat_log = result.combat_result.log[-10:] if result.combat_result else []
            self.screen_shake = 0.3

            if result.combat_result:
                if result.combat_result.victory:
                    msg = f"Victory! +{result.gold_earned}g"
                    if result.is_boss_fight:
                        msg = "BOSS DEFEATED! " + msg
                        self._add_particles(300, 300, PALETTE['gold'], 30)
                    self.message_log.append(msg)
                else:
                    self.message_log.append("Defeated!")

            # Process other results
            self._process_turn_result(result)

    def _process_turn_result(self, result: TurnResult) -> None:
        """Process non-combat turn results."""
        if result.blessing_received:
            self.message_log.append(f"Blessing: {result.blessing_received.name}")
            self._add_particles(300, 200, PALETTE['purple'], 15)
        if result.healed:
            self.message_log.append("Rested! HP restored.")
            self._add_particles(300, 200, PALETTE['green'], 15)
        if result.monsters_spawned:
            # Curse triggered!
            num = len(result.monsters_spawned)
            self.message_log.append(f"CURSED! {num} monsters spawned!")
            self._add_particles(300, 200, (150, 50, 180), 20)  # Purple particles
            self.screen_shake = 0.4
        if result.opened_merchant:
            self.state = "merchant"
        if result.pending_item:
            self.pending_item_id = result.pending_item
            self.state = "item_choice"
        if result.victory:
            self.state = "victory"
            self._add_particles(self.WINDOW_WIDTH // 2, 200, PALETTE['gold'], 50)
        if result.game_over:
            self.state = "game_over"
        self.message_log = self.message_log[-8:]

    def _add_particles(self, x: int, y: int, color: Tuple, count: int):
        """Add particle effects."""
        for _ in range(count):
            self.particle_effects.append({
                'x': x,
                'y': y,
                'vx': random.uniform(-100, 100),
                'vy': random.uniform(-150, -50),
                'life': random.uniform(0.5, 1.0),
                'color': color,
                'size': random.randint(2, 5),
            })

    def _update(self, dt: float) -> None:
        """Update game state and animations."""
        # Update battle scene if active
        if self.battle_scene.is_active():
            self.battle_scene.update(dt)
            return

        # Check for hovered item slot
        self.hovered_slot = None
        for slot in self.item_slots:
            if slot.rect.collidepoint(self.mouse_pos):
                self.hovered_slot = slot
                break

        # Update dice animation
        if self.dice_anim.active:
            self.dice_anim.timer += dt
            self.dice_anim.current_frame = int(self.dice_anim.timer * 15) % 6 + 1

            # Update per-die animations
            if self.dice_anim.die_offsets and self.dice_anim.settle_times:
                for i in range(len(self.dice_anim.final_values)):
                    if self.dice_anim.timer < self.dice_anim.settle_times[i]:
                        # Die is still rolling - add bounce and shake
                        bounce = math.sin(self.dice_anim.timer * 20 + i * 2) * 8
                        shake_x = random.uniform(-3, 3)
                        shake_y = random.uniform(-3, 3)
                        self.dice_anim.die_offsets[i] = (shake_x, bounce + shake_y)
                        self.dice_anim.die_rotations[i] += dt * 400  # Spin
                    elif not self.dice_anim.die_settled[i]:
                        # Die just settled - snap to position and add particles
                        self.dice_anim.die_settled[i] = True
                        self.dice_anim.die_offsets[i] = (0.0, 0.0)
                        # Add landing particles
                        dice_x = 280 - (len(self.dice_anim.final_values) * 58) // 2 + i * 58 + 24
                        self._add_particles(dice_x, 584, PALETTE['gold'], 5)

                # Show total after all dice settle
                if all(self.dice_anim.die_settled) and not self.dice_anim.show_total:
                    self.dice_anim.show_total = True
                    # Add celebration particles for total
                    self._add_particles(280, 590, PALETTE['gold'], 10)

                # Animate total scale
                if self.dice_anim.show_total and self.dice_anim.total_scale < 1.0:
                    self.dice_anim.total_scale = min(1.0, self.dice_anim.total_scale + dt * 4)

            if self.dice_anim.timer >= self.dice_anim.duration:
                self.dice_anim.active = False

        # Update player movement animation
        pm = self.player_movement
        if pm.path and pm.path_index < len(pm.path) - 1:
            # Move through path squares one by one
            move_speed = 6.0  # Squares per second
            pm.progress += dt * move_speed

            # Hop effect - arc motion between squares
            pm.hop_height = math.sin(pm.progress * math.pi) * 12

            if pm.progress >= 1.0:
                # Move to next square in path
                pm.progress = 0.0
                pm.path_index += 1
                pm.current_pos = pm.path[pm.path_index]

                # Add small dust particles when landing
                board_x, board_y = 30, 30
                x, y = self._get_square_position(pm.current_pos, board_x, board_y)
                self._add_particles(x + self.SQUARE_SIZE // 2, y + self.SQUARE_SIZE // 2 + 10,
                                  (150, 140, 120), 3)

        # Update particles
        for p in self.particle_effects[:]:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 300 * dt  # Gravity
            p['life'] -= dt
            if p['life'] <= 0:
                self.particle_effects.remove(p)

        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= dt

    def _draw(self) -> None:
        """Draw the game with polished graphics."""
        # Apply screen shake
        shake_x = int(random.uniform(-3, 3) * self.screen_shake * 10) if self.screen_shake > 0 else 0
        shake_y = int(random.uniform(-3, 3) * self.screen_shake * 10) if self.screen_shake > 0 else 0

        # Draw background
        self._draw_background()

        self.item_slots = []

        if self.state == "character_select":
            self._draw_character_select()
        else:
            # Apply shake offset
            offset_surface = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)

            self._draw_board(offset_surface)
            self._draw_player_panel(offset_surface)
            self._draw_equipment_slots(offset_surface)
            self._draw_blessings_panel(offset_surface)
            self._draw_message_log(offset_surface)
            if self.combat_log:
                self._draw_combat_log(offset_surface)

            # Draw dice animation (but not during battle)
            if not self.battle_scene.is_active() and (self.dice_anim.active or (self.last_turn_result and self.dice_anim.timer < 2)):
                self._draw_dice_result(offset_surface)

            self.screen.blit(offset_surface, (shake_x, shake_y))

            # Draw battle scene (in corner panel, over game but under overlays)
            if self.battle_scene.is_active():
                self.battle_scene.draw(self.screen)

            # Overlays (no shake)
            if self.state == "item_choice":
                self._draw_item_choice()
            elif self.state == "merchant":
                self._draw_merchant()
            elif self.state == "game_over":
                self._draw_game_over()
            elif self.state == "victory":
                self._draw_victory()
            elif self.state == "settings":
                self._draw_settings()

            # Draw tooltip last
            if self.hovered_slot and self.hovered_slot.item_id:
                self._draw_item_tooltip(self.hovered_slot)

        # Draw particles on top
        self._draw_particles()

    def _draw_background(self) -> None:
        """Draw polished background."""
        if self._bg_surface is None:
            self._bg_surface = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
            # Gradient background
            for y in range(self.WINDOW_HEIGHT):
                t = y / self.WINDOW_HEIGHT
                r = int(20 + t * 15)
                g = int(22 + t * 12)
                b = int(30 + t * 10)
                pygame.draw.line(self._bg_surface, (r, g, b), (0, y), (self.WINDOW_WIDTH, y))

            # Add subtle pattern
            for x in range(0, self.WINDOW_WIDTH, 32):
                for y in range(0, self.WINDOW_HEIGHT, 32):
                    if (x + y) % 64 == 0:
                        pygame.draw.circle(self._bg_surface, (35, 38, 45), (x, y), 2)

        self.screen.blit(self._bg_surface, (0, 0))

    def _draw_board(self, surface: pygame.Surface) -> None:
        """Draw the polished game board."""
        board_x, board_y = 30, 30

        # Draw board frame
        frame = sprites.create_panel(self.BOARD_SIZE + 20, self.BOARD_SIZE + 20, "gold")
        surface.blit(frame, (board_x - 10, board_y - 10))

        # Draw board background
        pygame.draw.rect(surface, PALETTE['wood_dark'],
                        (board_x, board_y, self.BOARD_SIZE, self.BOARD_SIZE))

        # Inner area - dark dungeon stone instead of grass
        inner_margin = self.SQUARE_SIZE
        inner_x = board_x + inner_margin
        inner_y = board_y + inner_margin
        inner_size = self.BOARD_SIZE - inner_margin * 2

        # Dark stone background with subtle pattern (cached to prevent flickering)
        if not hasattr(self, '_stone_surface') or self._stone_surface is None:
            self._stone_surface = pygame.Surface((inner_size, inner_size))
            self._stone_surface.fill((25, 22, 30))
            for tx in range(0, inner_size, 20):
                for ty in range(0, inner_size, 20):
                    shade = random.randint(-5, 5)
                    color = (30 + shade, 27 + shade, 35 + shade)
                    pygame.draw.rect(self._stone_surface, color, (tx, ty, 19, 19))
                    pygame.draw.rect(self._stone_surface, (20, 18, 25), (tx, ty, 19, 19), 1)
        surface.blit(self._stone_surface, (inner_x, inner_y))

        # Draw squares FIRST (before dragon so dragon appears on top)
        squares = self.game.get_board_squares()
        player_pos = self.game.get_player_position()

        for square in squares:
            x, y = self._get_square_position(square.index, board_x, board_y)
            # Don't draw player on tile - we'll draw it separately with animation
            tile = sprites.create_board_tile(
                self.SQUARE_SIZE - 2,
                square.square_type,
                square.has_monster,
                False  # Never draw player on tile
            )
            surface.blit(tile, (x, y))

            # Square number
            num_text = self.font_tiny.render(str(square.index), True, (200, 200, 200))
            surface.blit(num_text, (x + 2, y + 2))

        # Draw the chained dragon boss in center (AFTER squares)
        self._draw_chained_boss(surface, board_x, board_y)

        # Draw animated player token (AFTER dragon)
        self._draw_player_token(surface, board_x, board_y, player_pos)

    def _draw_chained_boss(self, surface: pygame.Surface, board_x: int, board_y: int) -> None:
        """Draw the chained dragon boss in the board center."""
        center_x = board_x + self.BOARD_SIZE // 2
        center_y = board_y + self.BOARD_SIZE // 2

        player = self.game.get_player_data()
        current_round = player.current_round if player else 1
        boss_round = 21  # Boss breaks free at round 21

        # Calculate chains remaining (all 8 chains break by round 21)
        total_chains = 8
        # Linear progression: lose ~1 chain every 2.5 rounds
        chains_broken = min(total_chains, (current_round * total_chains) // boss_round)
        chains_remaining = total_chains - chains_broken

        # Dragon sprite size
        dragon_size = 130

        # Draw position - center of inner board area
        dragon_x = center_x - dragon_size // 2
        dragon_y = center_y - dragon_size // 2 - 10

        # Get dragon sprite (no boss aura - this is decorative, not battle sprite)
        dragon = sprites.create_monster_sprite("dragon", dragon_size, is_boss=False)

        # Make a copy to modify
        dragon_display = dragon.copy()

        # Darken the dragon if still heavily chained
        if chains_remaining > 4:
            dark_overlay = pygame.Surface((dragon_size, dragon_size), pygame.SRCALPHA)
            dark_overlay.fill((0, 0, 0, 80))
            dragon_display.blit(dark_overlay, (0, 0))
        elif chains_remaining > 0:
            # Slightly darkened
            dark_overlay = pygame.Surface((dragon_size, dragon_size), pygame.SRCALPHA)
            dark_overlay.fill((0, 0, 0, 30))
            dragon_display.blit(dark_overlay, (0, 0))

        # Draw dragon
        surface.blit(dragon_display, (dragon_x, dragon_y))

        # Draw chains around the dragon
        chain_color = (100, 90, 80)
        chain_broken_color = (60, 55, 50, 100)
        chain_positions = [
            (center_x - 70, center_y - 40),  # Top-left
            (center_x + 70, center_y - 40),  # Top-right
            (center_x - 80, center_y),       # Left
            (center_x + 80, center_y),       # Right
            (center_x - 70, center_y + 40),  # Bottom-left
            (center_x + 70, center_y + 40),  # Bottom-right
            (center_x - 40, center_y - 70),  # Top-left-up
            (center_x + 40, center_y - 70),  # Top-right-up
        ]

        for i, (cx, cy) in enumerate(chain_positions):
            is_intact = i < chains_remaining

            if is_intact:
                # Draw intact chain link
                pygame.draw.circle(surface, chain_color, (int(cx), int(cy)), 8, 3)
                pygame.draw.circle(surface, (140, 130, 120), (int(cx), int(cy)), 5, 2)
                # Draw chain line to dragon
                pygame.draw.line(surface, chain_color, (int(cx), int(cy)),
                               (center_x, center_y), 2)
            else:
                # Draw broken chain (faded, broken link)
                broken_surf = pygame.Surface((20, 20), pygame.SRCALPHA)
                pygame.draw.arc(broken_surf, (80, 70, 60, 120), (2, 2, 16, 16),
                              0.5, 2.5, 2)
                surface.blit(broken_surf, (int(cx) - 10, int(cy) - 10))

        # Status text
        if chains_remaining > 0:
            # Chains remaining indicator
            status_text = f"{chains_remaining} chains remain"
            status_color = PALETTE['gold'] if chains_remaining <= 2 else PALETTE['gray_light']

            # Pulsing effect when low on chains
            if chains_remaining <= 2:
                pulse = (math.sin(pygame.time.get_ticks() / 200) + 1) / 2
                status_color = (
                    int(255 * (0.7 + 0.3 * pulse)),
                    int(100 * (0.7 + 0.3 * pulse)),
                    int(50 * (0.7 + 0.3 * pulse))
                )

            text = self.font_small.render(status_text, True, status_color)
            surface.blit(text, (center_x - text.get_width() // 2, center_y + 55))
        else:
            # Boss is free!
            pulse = (math.sin(pygame.time.get_ticks() / 150) + 1) / 2
            free_color = (int(255 * (0.8 + 0.2 * pulse)), int(50 + 50 * pulse), 50)
            free_text = self.font_medium.render("THE DRAGON AWAKENS!", True, free_color)
            surface.blit(free_text, (center_x - free_text.get_width() // 2, center_y + 55))

    def _get_square_position(self, index: int, bx: int, by: int) -> Tuple[int, int]:
        """Get pixel position for a square index."""
        if index <= 10:
            return (bx + index * self.SQUARE_SIZE, by)
        elif index <= 19:
            return (bx + self.BOARD_SIZE - self.SQUARE_SIZE,
                    by + (index - 10) * self.SQUARE_SIZE)
        elif index <= 30:
            return (bx + self.BOARD_SIZE - (index - 20) * self.SQUARE_SIZE - self.SQUARE_SIZE,
                    by + self.BOARD_SIZE - self.SQUARE_SIZE)
        else:
            return (bx, by + self.BOARD_SIZE - (index - 30) * self.SQUARE_SIZE - self.SQUARE_SIZE)

    def _draw_player_token(self, surface: pygame.Surface, board_x: int, board_y: int, player_pos: int) -> None:
        """Draw an animated, eye-catching player token with smooth movement."""
        if player_pos is None:
            return

        # Get animated position from movement state
        pm = self.player_movement
        if pm.path and pm.path_index < len(pm.path):
            current_square = pm.path[pm.path_index]
            # Get position of current square
            x1, y1 = self._get_square_position(current_square, board_x, board_y)

            # If still moving, interpolate to next square
            if pm.path_index < len(pm.path) - 1:
                next_square = pm.path[pm.path_index + 1]
                x2, y2 = self._get_square_position(next_square, board_x, board_y)
                # Linear interpolation
                x = x1 + (x2 - x1) * pm.progress
                y = y1 + (y2 - y1) * pm.progress
                # Apply hop height
                hop_offset = -pm.hop_height
            else:
                x, y = x1, y1
                hop_offset = 0
        else:
            # Fall back to actual position
            x, y = self._get_square_position(player_pos, board_x, board_y)
            hop_offset = 0

        cx = x + self.SQUARE_SIZE // 2 - 1
        cy = y + self.SQUARE_SIZE // 2 - 1 + hop_offset

        # Get current time for animations
        t = pygame.time.get_ticks()

        # Pulsing glow effect
        pulse = (math.sin(t / 200) + 1) / 2
        glow_size = int(28 + 6 * pulse)

        # Outer glow (cyan/gold gradient based on pulse)
        glow_surf = pygame.Surface((glow_size * 2 + 10, glow_size * 2 + 10), pygame.SRCALPHA)
        for i in range(4):
            alpha = int((80 - i * 18) * (0.7 + 0.3 * pulse))
            glow_color = (
                int(100 + 155 * pulse),  # R: gold when pulsing
                int(200 - 50 * pulse),    # G
                int(255 - 155 * pulse),   # B: cyan base
                alpha
            )
            pygame.draw.circle(glow_surf, glow_color,
                             (glow_size + 5, glow_size + 5), glow_size - i * 3)
        surface.blit(glow_surf, (int(cx - glow_size - 5), int(cy - glow_size - 5)))

        # Bobbing animation (reduced when hopping)
        is_moving = pm.path and pm.path_index < len(pm.path) - 1
        bob = 0 if is_moving else math.sin(t / 300) * 3

        # Character portrait
        player = self.game.get_player_data()
        char_id = player.character_id if player else "warrior"
        portrait_size = 32

        # Get character portrait
        portrait = sprites.create_character_portrait(char_id, portrait_size)

        # Draw portrait with slight bob
        portrait_x = int(cx - portrait_size // 2)
        portrait_y = int(cy - portrait_size // 2 + bob)

        # Add shadow under portrait (stretched when high, smaller when close to ground)
        shadow_scale = 1.0 - (abs(hop_offset) / 20.0) * 0.3
        shadow_w = int((portrait_size + 4) * shadow_scale)
        shadow_h = int(8 * shadow_scale)
        shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
        shadow_alpha = int(60 * shadow_scale)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), (0, 0, shadow_w, shadow_h))
        # Shadow stays on ground (doesn't move with hop)
        ground_y = y + self.SQUARE_SIZE // 2 + portrait_size // 2 + 2
        surface.blit(shadow_surf, (int(cx - shadow_w // 2), int(ground_y)))

        # Draw the portrait
        surface.blit(portrait, (portrait_x, portrait_y))

        # Sparkle effects around player (only when not moving)
        if not is_moving:
            sparkle_phase = (t // 100) % 8
            sparkle_positions = [
                (cx - 18, cy - 10), (cx + 18, cy - 5),
                (cx - 15, cy + 12), (cx + 15, cy + 15),
                (cx - 5, cy - 20), (cx + 8, cy - 18),
                (cx - 20, cy + 3), (cx + 20, cy - 2),
            ]
            for i, (sx, sy) in enumerate(sparkle_positions):
                if (i + sparkle_phase) % 4 == 0:
                    sparkle_size = 2 + (i % 2)
                    sparkle_alpha = int(150 + 100 * math.sin(t / 100 + i))
                    sparkle_color = (255, 255, 200, sparkle_alpha)
                    sparkle_surf = pygame.Surface((sparkle_size * 2, sparkle_size * 2), pygame.SRCALPHA)
                    pygame.draw.circle(sparkle_surf, sparkle_color, (sparkle_size, sparkle_size), sparkle_size)
                    surface.blit(sparkle_surf, (int(sx - sparkle_size), int(sy - sparkle_size + bob)))

    def _parse_dice_formula(self, formula: str) -> List[str]:
        """Parse a dice formula like '2d6' or '1d6+1d8' into list of die types."""
        import re
        die_types = []
        # Match patterns like "2d6", "1d8", "3d4"
        parts = re.findall(r'(\d*)d(\d+)', formula)
        for count_str, sides in parts:
            count = int(count_str) if count_str else 1
            for _ in range(count):
                die_types.append(f"d{sides}")
        return die_types if die_types else ["d6", "d6"]

    def _draw_dice_result(self, surface: pygame.Surface) -> None:
        """Draw dice animation/result with enhanced visuals."""
        if not self.last_turn_result:
            return

        rolls = self.last_turn_result.move_result.rolls
        dice_size = 52
        gap = 6
        total_width = len(rolls) * dice_size + (len(rolls) - 1) * gap
        start_x = 280 - total_width // 2
        base_y = 560  # Below the board entirely

        # Get die type from character's dice formula
        player = self.game.get_player_data()
        char = get_character(player.character_id) if player else None
        die_types = self._parse_dice_formula(char.dice_formula if char else "2d6")

        # Draw dice tray background
        tray_padding = 15
        tray_x = start_x - tray_padding
        tray_y = base_y - tray_padding
        tray_w = total_width + tray_padding * 2
        tray_h = dice_size + tray_padding * 2 + 35  # Extra space for total

        # Tray with felt texture
        tray_surf = pygame.Surface((tray_w, tray_h), pygame.SRCALPHA)
        pygame.draw.rect(tray_surf, (40, 25, 20), (0, 0, tray_w, tray_h), border_radius=10)
        pygame.draw.rect(tray_surf, (60, 35, 25), (3, 3, tray_w - 6, tray_h - 6), border_radius=8)
        # Felt interior
        pygame.draw.rect(tray_surf, (30, 60, 30), (6, 6, tray_w - 12, tray_h - 12), border_radius=6)
        pygame.draw.rect(tray_surf, (25, 50, 25), (8, 8, tray_w - 16, tray_h - 16), border_radius=5)
        surface.blit(tray_surf, (tray_x, tray_y))

        # Draw each die
        for i, value in enumerate(rolls):
            x = start_x + i * (dice_size + gap)
            y = base_y

            # Get the die type for this specific die
            die_type = die_types[i] if i < len(die_types) else "d6"
            die_max = int(die_type[1:]) if die_type.startswith("d") else 6

            # Get animation offset
            offset_x, offset_y = 0.0, 0.0
            is_settled = True
            if self.dice_anim.active and self.dice_anim.die_offsets:
                offset_x, offset_y = self.dice_anim.die_offsets[i]
                is_settled = self.dice_anim.die_settled[i] if self.dice_anim.die_settled else False

            # Determine display value
            if self.dice_anim.active and not is_settled:
                display_val = random.randint(1, die_max)
                rolling = True
            else:
                display_val = value
                rolling = False

            # Create dice sprite with correct die type
            dice = sprites.create_dice(dice_size, display_val, die_type, rolling=rolling)

            # Apply offset
            draw_x = int(x + offset_x)
            draw_y = int(y + offset_y)

            # Add glow for settled dice
            if is_settled and not rolling:
                glow_surf = pygame.Surface((dice_size + 8, dice_size + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (255, 200, 50, 60),
                               (0, 0, dice_size + 8, dice_size + 8), border_radius=10)
                surface.blit(glow_surf, (draw_x - 4, draw_y - 4))

            surface.blit(dice, (draw_x, draw_y))

        # Show total with animation
        show_total = (not self.dice_anim.active) or (self.dice_anim.show_total if self.dice_anim.active else False)
        if show_total:
            total = self.last_turn_result.move_result.total
            scale = self.dice_anim.total_scale if self.dice_anim.active else 1.0

            # Create scaled total text
            base_font_size = 42
            scaled_size = int(base_font_size * (0.5 + 0.5 * scale))
            total_font = pygame.font.Font(None, scaled_size)

            # Pulsing glow effect
            pulse = (math.sin(pygame.time.get_ticks() / 150) + 1) / 2
            glow_color = (255, int(180 + 40 * pulse), int(50 + 30 * pulse))

            total_text = total_font.render(f"= {total}", True, glow_color)
            total_x = start_x + total_width // 2 - total_text.get_width() // 2
            total_y = base_y + dice_size + 8

            # Shadow
            shadow = total_font.render(f"= {total}", True, (0, 0, 0))
            surface.blit(shadow, (total_x + 2, total_y + 2))
            surface.blit(total_text, (total_x, total_y))

    def _draw_player_panel(self, surface: pygame.Surface) -> None:
        """Draw player stats panel with polished graphics."""
        x, y, w, h = 560, 30, 430, 130

        # Draw panel
        panel = sprites.create_panel(w, h, "gold")
        surface.blit(panel, (x, y))

        stats = self.game.get_player_stats()
        player = self.game.get_player_data()
        if not stats or not player:
            return

        char = get_character(player.character_id)

        # Character portrait
        portrait = sprites.create_character_portrait(player.character_id, 50)
        surface.blit(portrait, (x + 10, y + 10))

        # Character name and round
        name_text = self.font_large.render(char.name, True, PALETTE['gold'])
        surface.blit(name_text, (x + 70, y + 8))

        round_text = self.font_medium.render(f"Round {player.current_round}", True, PALETTE['cream'])
        surface.blit(round_text, (x + 70, y + 35))

        # HP bar
        hp_bar = sprites.create_health_bar(160, 16, stats.hp_percent)
        surface.blit(hp_bar, (x + 200, y + 12))

        hp_text = self.font_small.render(f"{stats.current_hp}/{stats.max_hp}", True, PALETTE['white'])
        surface.blit(hp_text, (x + 255, y + 13))

        # Shield indicator
        if player.temp_shield > 0:
            shield_text = self.font_small.render(f"+{player.temp_shield}", True, PALETTE['cyan'])
            surface.blit(shield_text, (x + 365, y + 13))

        # Potion button
        pot_color = PALETTE['green'] if player.potion_count > 0 else PALETTE['red_dark']
        pot_btn = sprites.create_button(70, 24, False, "default")
        surface.blit(pot_btn, (x + 345, y + 35))
        pot_text = self.font_small.render("[P] POT" if player.potion_count else "[P] ---", True, pot_color)
        surface.blit(pot_text, (x + 352, y + 40))

        # Gold and kills
        gold_text = self.font_medium.render(f"Gold: {player.gold}", True, PALETTE['gold'])
        surface.blit(gold_text, (x + 200, y + 38))

        kills_text = self.font_small.render(f"Kills: {player.monsters_killed}", True, PALETTE['cream'])
        surface.blit(kills_text, (x + 200, y + 58))

        # Character-specific info
        special = ""
        if char.dice_special == "momentum" and player.momentum > 0:
            special = f"Momentum +{player.momentum}"
        elif char.death_stacks and player.death_stacks > 0:
            die_sizes = ["d6", "d8", "d10", "d12", "d20"]
            special = f"Death Die: {die_sizes[min(player.death_stacks, 4)]}"
        elif char.combo_master and player.combo_stacks > 0:
            special = f"Combo x{player.combo_stacks}"
        if special:
            special_text = self.font_small.render(special, True, PALETTE['cyan'])
            surface.blit(special_text, (x + 300, y + 58))

        # Stats rows
        s1 = f"ATK:{stats.base_damage:.0f}  SPD:{stats.attack_speed:.2f}  DEF:{stats.defense}"
        s1_text = self.font_small.render(s1, True, PALETTE['gray_light'])
        surface.blit(s1_text, (x + 15, y + 85))

        s2 = f"CRIT:{stats.crit_chance*100:.0f}%  LS:{stats.life_steal*100:.0f}%  DODGE:{stats.dodge_chance*100:.0f}%"
        s2_text = self.font_small.render(s2, True, PALETTE['gray_light'])
        surface.blit(s2_text, (x + 15, y + 102))

        # Controls hint
        ctrl_text = self.font_tiny.render("[SPACE] Roll  [ESC] Settings", True, PALETTE['gray'])
        surface.blit(ctrl_text, (x + 280, y + 108))

    def _draw_equipment_slots(self, surface: pygame.Surface) -> None:
        """Draw equipment slots with polished item icons."""
        x, y = 560, 170
        slot_size = 70
        gap = 10

        equipment = self.game.get_player_equipment()
        if not equipment:
            return

        # Panel background
        panel = sprites.create_panel(3 * slot_size + 2 * gap + 20, slot_size + 35, "default")
        surface.blit(panel, (x - 10, y - 10))

        slots = [
            ("weapon", "WPN", equipment.weapon),
            ("armor", "ARM", equipment.armor),
            ("ring", "RING", equipment.ring),
        ]

        for i, (slot_type, label, item_id) in enumerate(slots):
            sx = x + i * (slot_size + gap)
            sy = y

            item = self.game.get_item(item_id) if item_id else None
            rarity = item.rarity if item else Rarity.COMMON
            colors = RARITY_SCHEMES.get(rarity, RARITY_SCHEMES[Rarity.COMMON])

            # Slot background
            pygame.draw.rect(surface, PALETTE['black'], (sx, sy, slot_size, slot_size))
            pygame.draw.rect(surface, PALETTE['panel_bg'], (sx + 2, sy + 2, slot_size - 4, slot_size - 4))

            # Rarity border (animated glow for rare+)
            border_color = colors[0]
            if item and rarity.value >= Rarity.RARE.value:
                # Pulsing glow
                pulse = (math.sin(pygame.time.get_ticks() / 200) + 1) / 2
                glow_alpha = int(50 + pulse * 50)
                glow_surf = pygame.Surface((slot_size + 8, slot_size + 8), pygame.SRCALPHA)
                pygame.draw.rect(glow_surf, (*border_color, glow_alpha),
                               (0, 0, slot_size + 8, slot_size + 8), border_radius=6)
                surface.blit(glow_surf, (sx - 4, sy - 4))

            pygame.draw.rect(surface, border_color, (sx, sy, slot_size, slot_size), 3, border_radius=4)

            # Slot label
            label_text = self.font_tiny.render(label, True, PALETTE['gray'])
            surface.blit(label_text, (sx + 3, sy + 3))

            if item:
                # Draw item icon
                item_type = item.item_type
                icon = sprites.create_item_icon(item_type, rarity, item.level, 40)
                surface.blit(icon, (sx + 15, sy + 8))

                # Tier text (bottom-left to avoid frame overlap)
                tier_text = self.font_medium.render(f"T{item.level}", True, colors[2])
                surface.blit(tier_text, (sx + 5, sy + slot_size - 20))
            else:
                # Empty slot indicator
                empty_text = self.font_medium.render("---", True, PALETTE['gray'])
                surface.blit(empty_text, (sx + slot_size // 2 - 12, sy + slot_size // 2 - 8))

            # Register slot for hover
            slot_rect = pygame.Rect(sx, sy, slot_size, slot_size)
            self.item_slots.append(ItemSlot(slot_rect, item_id, slot_type))

        # Label
        equip_label = self.font_medium.render("EQUIPMENT", True, PALETTE['cyan'])
        surface.blit(equip_label, (x, y + slot_size + 5))

    def _draw_item_tooltip(self, slot: ItemSlot) -> None:
        """Draw polished tooltip for hovered item."""
        item = self.game.get_item(slot.item_id)
        if not item:
            return

        colors = RARITY_SCHEMES.get(item.rarity, RARITY_SCHEMES[Rarity.COMMON])

        lines = [
            item.display_name,
            f"Rarity: {item.rarity.name}",
            "",
        ]

        # Stats
        stat_lines = []
        if item.damage_bonus != 0:
            stat_lines.append(f"  Damage: +{item.damage_bonus:.0f}")
        if item.hp_bonus != 0:
            stat_lines.append(f"  HP: +{item.hp_bonus}")
        if item.defense_bonus != 0:
            stat_lines.append(f"  Defense: +{item.defense_bonus}")
        if item.attack_speed_bonus != 0:
            stat_lines.append(f"  Speed: +{item.attack_speed_bonus:.2f}")
        if item.crit_chance_bonus != 0:
            stat_lines.append(f"  Crit: +{item.crit_chance_bonus*100:.0f}%")
        if item.life_steal_bonus != 0:
            stat_lines.append(f"  Life Steal: +{item.life_steal_bonus*100:.0f}%")
        if item.crit_multiplier_bonus != 0:
            stat_lines.append(f"  Crit Dmg: +{item.crit_multiplier_bonus:.1f}x")
        if item.dodge_bonus != 0:
            stat_lines.append(f"  Dodge: +{item.dodge_bonus*100:.0f}%")

        if not stat_lines:
            stat_lines.append("  (no bonuses)")

        lines.extend(stat_lines)
        lines.append("")
        lines.append(f"Sell: {item.sell_value}g")

        # Calculate size
        padding = 10
        line_height = 18
        tooltip_w = 200
        tooltip_h = len(lines) * line_height + padding * 2

        # Position
        tx = min(self.mouse_pos[0] + 15, self.WINDOW_WIDTH - tooltip_w - 10)
        ty = min(self.mouse_pos[1] + 15, self.WINDOW_HEIGHT - tooltip_h - 10)

        # Draw tooltip
        tooltip_surf = pygame.Surface((tooltip_w, tooltip_h), pygame.SRCALPHA)

        # Background
        pygame.draw.rect(tooltip_surf, (15, 15, 20, 240), (0, 0, tooltip_w, tooltip_h), border_radius=6)
        pygame.draw.rect(tooltip_surf, colors[0], (0, 0, tooltip_w, tooltip_h), 2, border_radius=6)

        # Text
        for i, line in enumerate(lines):
            if i == 0:
                color = colors[0]  # Rarity color for name
            elif line.startswith("  ") and "+" in line:
                color = PALETTE['green']
            elif "Sell:" in line:
                color = PALETTE['gold']
            else:
                color = PALETTE['cream']

            text = self.font_small.render(line, True, color)
            tooltip_surf.blit(text, (padding, padding + i * line_height))

        self.screen.blit(tooltip_surf, (tx, ty))

    def _draw_blessings_panel(self, surface: pygame.Surface) -> None:
        """Draw active blessings panel."""
        x, y, w, h = 560, 260, 240, 80

        panel = sprites.create_panel(w, h, "purple")
        surface.blit(panel, (x, y))

        title = self.font_medium.render("BLESSINGS", True, PALETTE['purple_light'])
        surface.blit(title, (x + 10, y + 5))

        player = self.game.get_player_data()
        if not player or not player.active_blessings:
            none_text = self.font_small.render("(none)", True, PALETTE['gray'])
            surface.blit(none_text, (x + 15, y + 28))
            return

        for i, blessing in enumerate(player.active_blessings[:3]):
            dur = "PERM" if blessing.is_permanent else f"({blessing.duration})"
            color = PALETTE['gold'] if blessing.is_permanent else PALETTE['cream']
            text = self.font_small.render(f"{blessing.name} {dur}", True, color)
            surface.blit(text, (x + 15, y + 28 + i * 16))

    def _draw_message_log(self, surface: pygame.Surface) -> None:
        """Draw message log panel."""
        x, y, w, h = 560, 350, 430, 130

        panel = sprites.create_panel(w, h, "default")
        surface.blit(panel, (x, y))

        title = self.font_medium.render("Messages", True, PALETTE['gold'])
        surface.blit(title, (x + 10, y + 5))

        for i, msg in enumerate(self.message_log[-6:]):
            text = self.font_small.render(msg[:55], True, PALETTE['cream'])
            surface.blit(text, (x + 15, y + 28 + i * 17))

    def _draw_combat_log(self, surface: pygame.Surface) -> None:
        """Draw combat log panel."""
        x, y, w, h = 560, 490, 430, 260

        panel = sprites.create_panel(w, h, "red")
        surface.blit(panel, (x, y))

        title = self.font_medium.render("Combat", True, PALETTE['red'])
        surface.blit(title, (x + 10, y + 5))

        for i, msg in enumerate(self.combat_log[-12:]):
            if len(msg) > 55:
                msg = msg[:52] + "..."
            text = self.font_small.render(msg, True, PALETTE['cream'])
            surface.blit(text, (x + 15, y + 28 + i * 18))

    def _draw_particles(self) -> None:
        """Draw particle effects."""
        for p in self.particle_effects:
            alpha = int(255 * (p['life'] / 1.0))
            color = (*p['color'][:3], min(255, alpha))
            size = max(1, int(p['size'] * p['life']))

            surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (size, size), size)
            self.screen.blit(surf, (int(p['x']) - size, int(p['y']) - size))

    def _draw_item_choice(self) -> None:
        """Draw item choice panel in bottom-left corner (non-intrusive)."""
        if not self.pending_item_id:
            return
        item = self.game.get_item(self.pending_item_id)
        if not item:
            return

        # Panel in bottom-left corner (below the board)
        w, h = 520, 220
        x, y = 20, self.WINDOW_HEIGHT - h - 10

        colors = RARITY_SCHEMES.get(item.rarity, RARITY_SCHEMES[Rarity.COMMON])

        # Panel background
        panel = sprites.create_panel(w, h, "gold")
        self.screen.blit(panel, (x, y))

        # Rarity glow border
        pygame.draw.rect(self.screen, colors[0], (x, y, w, h), 3, border_radius=6)

        # Title bar
        title = self.font_medium.render("ITEM FOUND!", True, PALETTE['gold'])
        self.screen.blit(title, (x + 10, y + 8))

        # Item icon with rarity glow
        icon_size = 56
        icon = sprites.create_item_icon(item.item_type, item.rarity, item.level, icon_size)
        icon_x, icon_y = x + 15, y + 38
        self.screen.blit(icon, (icon_x, icon_y))

        # New item info (right of icon)
        info_x = icon_x + icon_size + 15
        name_text = self.font_medium.render(item.display_name, True, colors[0])
        self.screen.blit(name_text, (info_x, y + 38))

        # Stats on one line
        stats_text = self.font_small.render(item.stat_summary[:50], True, PALETTE['cream'])
        self.screen.blit(stats_text, (info_x, y + 58))

        sell_text = self.font_small.render(f"Value: {item.sell_value}g", True, PALETTE['gold'])
        self.screen.blit(sell_text, (info_x, y + 76))

        # Divider line
        pygame.draw.line(self.screen, PALETTE['panel_border'], (x + 10, y + 100), (x + w - 10, y + 100), 1)

        # Current equipment comparison
        equipment = self.game.get_player_equipment()
        current_id = None
        if equipment:
            if item.item_type == ItemType.WEAPON:
                current_id = equipment.weapon
            elif item.item_type == ItemType.ARMOR:
                current_id = equipment.armor
            else:
                current_id = equipment.ring

        compare_y = y + 108
        if current_id:
            current = self.game.get_item(current_id)
            if current:
                # Current item icon (smaller)
                curr_icon = sprites.create_item_icon(current.item_type, current.rarity, current.level, 32)
                self.screen.blit(curr_icon, (x + 15, compare_y))

                curr_colors = RARITY_SCHEMES.get(current.rarity, RARITY_SCHEMES[Rarity.COMMON])
                curr_text = self.font_small.render(f"Current: {current.display_name}", True, curr_colors[0])
                self.screen.blit(curr_text, (x + 55, compare_y + 2))

                # Show stat comparison with colored deltas
                stat_changes = self._get_stat_comparison(item, current)
                stat_x = x + 55
                for stat_text, stat_color in stat_changes:
                    rendered = self.font_small.render(stat_text, True, stat_color)
                    self.screen.blit(rendered, (stat_x, compare_y + 18))
                    stat_x += rendered.get_width() + 10  # spacing between stats
        else:
            empty_text = self.font_small.render("Slot: Empty (equip for free!)", True, PALETTE['green'])
            self.screen.blit(empty_text, (x + 15, compare_y + 8))

        # Action buttons at bottom
        btn_y = y + h - 45
        btn_w = 120

        # Equip button
        equip_btn = sprites.create_button(btn_w, 32, False, "gold")
        self.screen.blit(equip_btn, (x + 80, btn_y))
        equip_text = self.font_medium.render("[E] Equip", True, PALETTE['black'])
        self.screen.blit(equip_text, (x + 105, btn_y + 7))

        # Sell button
        sell_btn = sprites.create_button(btn_w + 30, 32, False, "default")
        self.screen.blit(sell_btn, (x + 220, btn_y))
        sell_txt = self.font_medium.render(f"[S] Sell +{item.sell_value}g", True, PALETTE['gold'])
        self.screen.blit(sell_txt, (x + 235, btn_y + 7))

        # Quick hint
        hint = self.font_tiny.render("Pick up loot without interrupting gameplay!", True, PALETTE['gray'])
        self.screen.blit(hint, (x + w - 220, y + 8))

    def _get_stat_comparison(self, new_item, current_item) -> list:
        """Generate stat comparison as list of (text, color) tuples."""
        changes = []

        diff_dmg = new_item.damage_bonus - current_item.damage_bonus
        diff_def = new_item.defense_bonus - current_item.defense_bonus
        diff_hp = new_item.hp_bonus - current_item.hp_bonus
        diff_spd = new_item.attack_speed_bonus - current_item.attack_speed_bonus
        diff_crit = new_item.crit_chance_bonus - current_item.crit_chance_bonus
        diff_ls = new_item.life_steal_bonus - current_item.life_steal_bonus

        def get_color(val):
            if val > 0:
                return PALETTE['green']
            elif val < 0:
                return PALETTE['red']
            return PALETTE['gray']

        if diff_dmg != 0:
            sign = "+" if diff_dmg > 0 else ""
            changes.append((f"DMG:{sign}{diff_dmg:.0f}", get_color(diff_dmg)))
        if diff_def != 0:
            sign = "+" if diff_def > 0 else ""
            changes.append((f"DEF:{sign}{diff_def}", get_color(diff_def)))
        if diff_hp != 0:
            sign = "+" if diff_hp > 0 else ""
            changes.append((f"HP:{sign}{diff_hp}", get_color(diff_hp)))
        if abs(diff_spd) > 0.01:
            sign = "+" if diff_spd > 0 else ""
            changes.append((f"SPD:{sign}{diff_spd:.2f}", get_color(diff_spd)))
        if abs(diff_crit) > 0.001:
            sign = "+" if diff_crit > 0 else ""
            changes.append((f"CRIT:{sign}{diff_crit*100:.0f}%", get_color(diff_crit)))
        if abs(diff_ls) > 0.001:
            sign = "+" if diff_ls > 0 else ""
            changes.append((f"LS:{sign}{diff_ls*100:.0f}%", get_color(diff_ls)))

        if not changes:
            return [("No stat change", PALETTE['gray'])]

        return changes[:5]  # Limit to 5 stats

    def _draw_merchant(self) -> None:
        """Draw merchant shop overlay."""
        merchant = self.game.merchant_inventory
        if not merchant:
            return

        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        w, h = 500, 450
        x = (self.WINDOW_WIDTH - w) // 2
        y = (self.WINDOW_HEIGHT - h) // 2

        panel = sprites.create_panel(w, h, "gold")
        self.screen.blit(panel, (x, y))

        # Title
        title = self.font_large.render("MERCHANT", True, PALETTE['gold'])
        self.screen.blit(title, (x + w // 2 - 65, y + 15))

        player = self.game.get_player_data()
        gold_text = self.font_medium.render(f"Your Gold: {player.gold if player else 0}", True, PALETTE['gold'])
        self.screen.blit(gold_text, (x + 30, y + 55))

        # Items section
        items_label = self.font_medium.render("ITEMS FOR SALE:", True, PALETTE['cream'])
        self.screen.blit(items_label, (x + 30, y + 90))

        for i, item_id in enumerate(merchant.items[:5]):
            item = self.game.get_item(item_id)
            if item:
                price = merchant.item_prices.get(item_id, 0)
                colors = RARITY_SCHEMES.get(item.rarity, RARITY_SCHEMES[Rarity.COMMON])

                # Small item icon
                icon = sprites.create_item_icon(item.item_type, item.rarity, item.level, 24)
                self.screen.blit(icon, (x + 40, y + 115 + i * 28))

                text = self.font_small.render(f"[{i+1}] {item.display_name} - {price}g", True, colors[0])
                self.screen.blit(text, (x + 70, y + 118 + i * 28))

        # Blessings section
        bless_label = self.font_medium.render("BLESSINGS:", True, PALETTE['purple_light'])
        self.screen.blit(bless_label, (x + 30, y + 265))

        for i, blessing in enumerate(merchant.blessings[:2]):
            key = "[B]" if i == 0 else "[N]"
            text = self.font_small.render(f"{key} {blessing.name} - {blessing.shop_price}g", True, PALETTE['purple'])
            self.screen.blit(text, (x + 40, y + 290 + i * 22))

        # Potion section
        pot_label = self.font_medium.render("POTION:", True, PALETTE['green'])
        self.screen.blit(pot_label, (x + 30, y + 350))

        if merchant.has_potion:
            pot_text = self.font_small.render(f"[P] Health Potion - {merchant.potion_price}g", True, PALETTE['green'])
        else:
            pot_text = self.font_small.render("Sold out", True, PALETTE['gray'])
        self.screen.blit(pot_text, (x + 40, y + 375))

        # Exit
        exit_text = self.font_medium.render("[ESC] Leave Shop", True, PALETTE['gray'])
        self.screen.blit(exit_text, (x + w // 2 - 65, y + h - 40))

    def _draw_game_over(self) -> None:
        """Draw game over / upgrade screen."""
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 230))
        self.screen.blit(overlay, (0, 0))

        # Title
        title = self.font_large.render("GAME OVER", True, PALETTE['red'])
        self.screen.blit(title, (self.WINDOW_WIDTH // 2 - 75, 25))

        player = self.game.get_player_data()
        if player:
            stats_text = f"Round {player.current_round} | Kills: {player.monsters_killed} | Gold: {player.gold}"
            stats = self.font_medium.render(stats_text, True, PALETTE['cream'])
            self.screen.blit(stats, (self.WINDOW_WIDTH // 2 - 140, 60))

        p = self.game.persistent
        bank = self.font_large.render(f"Bank: {p.current_gold}g", True, PALETTE['gold'])
        self.screen.blit(bank, (self.WINDOW_WIDTH // 2 - 80, 90))

        # Upgrades panel
        upg_panel = sprites.create_panel(400, 200, "default")
        self.screen.blit(upg_panel, (50, 130))

        upg_title = self.font_medium.render("PERMANENT UPGRADES", True, PALETTE['cyan'])
        self.screen.blit(upg_title, (70, 140))

        for i, (uid, upg) in enumerate(UPGRADES.items()):
            lvl = p.get_upgrade_level(uid)
            eff = p.get_upgrade_effect(uid)
            cost = upg.get_cost(lvl) if lvl < upg.max_level else 0
            eff_str = f"+{eff*100:.0f}%" if uid in ["precision", "swiftness", "vampirism"] else f"+{eff:.0f}"
            can = cost > 0 and p.current_gold >= cost
            col = PALETTE['green'] if can else PALETTE['cream'] if cost > 0 else PALETTE['gray']
            txt = f"[{i+1}] {upg.name} Lv{lvl}/{upg.max_level} ({eff_str}) "
            txt += f"Next: {cost}g" if cost > 0 else "MAX"
            text = self.font_small.render(txt, True, col)
            self.screen.blit(text, (70, 165 + i * 22))

        # Characters panel
        char_panel = sprites.create_panel(400, 230, "purple")
        self.screen.blit(char_panel, (50, 345))

        char_title = self.font_medium.render("UNLOCK CHARACTERS", True, PALETTE['purple_light'])
        self.screen.blit(char_title, (70, 355))

        char_binds = [("Q", "rogue"), ("W", "berserker"), ("E", "paladin"), ("T", "gambler"),
                      ("Y", "mage"), ("U", "monk"), ("I", "vampire"), ("O", "necromancer"),
                      ("J", "jester"), ("K", "avatar")]

        for i, (key, cid) in enumerate(char_binds):
            if cid not in CHARACTERS:
                continue
            ch = CHARACTERS[cid]
            unlocked = p.is_character_unlocked(cid)

            # Portrait
            portrait = sprites.create_character_portrait(cid, 20)
            col = i % 2
            row = i // 2
            px = 70 + col * 190
            py = 378 + row * 22

            self.screen.blit(portrait, (px, py - 2))

            if unlocked:
                txt = f"[{key}] {ch.name}"
                color = PALETTE['green']
            else:
                can = p.current_gold >= ch.cost
                color = PALETTE['gold'] if can else PALETTE['gray']
                txt = f"[{key}] {ch.name} ({ch.cost}g)"

            text = self.font_small.render(txt, True, color)
            self.screen.blit(text, (px + 25, py))

        # Stats panel
        stats_panel = sprites.create_panel(200, 150, "default")
        self.screen.blit(stats_panel, (500, 130))

        stats_title = self.font_medium.render("LIFETIME STATS", True, PALETTE['gold'])
        self.screen.blit(stats_title, (520, 140))

        stat_lines = [
            f"Total Runs: {p.total_runs}",
            f"Best Round: {p.best_round}",
            f"Total Kills: {p.total_kills}",
            f"Boss Victories: {p.total_boss_victories}",
            f"Lifetime Gold: {p.lifetime_gold}",
        ]
        for i, line in enumerate(stat_lines):
            text = self.font_small.render(line, True, PALETTE['cream'])
            self.screen.blit(text, (520, 165 + i * 20))

        # New run button
        btn = sprites.create_button(200, 50, False, "gold")
        self.screen.blit(btn, (self.WINDOW_WIDTH // 2 - 100, 600))
        btn_text = self.font_large.render("[R] New Run", True, PALETTE['black'])
        self.screen.blit(btn_text, (self.WINDOW_WIDTH // 2 - 70, 612))

    def _draw_victory(self) -> None:
        """Draw victory screen."""
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        cy = self.WINDOW_HEIGHT // 2

        # Animated title
        pulse = (math.sin(pygame.time.get_ticks() / 200) + 1) / 2
        title_color = tuple(int(c * (0.8 + 0.2 * pulse)) for c in PALETTE['gold'])

        title = self.font_large.render("VICTORY!", True, title_color)
        self.screen.blit(title, (self.WINDOW_WIDTH // 2 - 60, cy - 100))

        sub = self.font_medium.render("You defeated the Ancient Dragon!", True, PALETTE['cream'])
        self.screen.blit(sub, (self.WINDOW_WIDTH // 2 - 130, cy - 50))

        # Options
        cont_btn = sprites.create_button(220, 45, False, "default")
        self.screen.blit(cont_btn, (self.WINDOW_WIDTH // 2 - 110, cy + 30))
        cont_text = self.font_medium.render("[C] Continue (for fun)", True, PALETTE['cyan'])
        self.screen.blit(cont_text, (self.WINDOW_WIDTH // 2 - 85, cy + 42))

        end_btn = sprites.create_button(250, 45, False, "gold")
        self.screen.blit(end_btn, (self.WINDOW_WIDTH // 2 - 125, cy + 90))
        end_text = self.font_medium.render("[E] End & Collect Rewards", True, PALETTE['black'])
        self.screen.blit(end_text, (self.WINDOW_WIDTH // 2 - 105, cy + 102))

    def _draw_settings(self) -> None:
        """Draw settings overlay."""
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        w, h = 350, 280
        x = (self.WINDOW_WIDTH - w) // 2
        y = (self.WINDOW_HEIGHT - h) // 2

        panel = sprites.create_panel(w, h, "default")
        self.screen.blit(panel, (x, y))

        # Title
        title = self.font_large.render("SETTINGS", True, PALETTE['gold'])
        self.screen.blit(title, (x + w // 2 - 60, y + 15))

        # Battle Speed section
        speed_label = self.font_medium.render("Battle Animation Speed:", True, PALETTE['cream'])
        self.screen.blit(speed_label, (x + 25, y + 60))

        speeds = [
            (BattleSpeed.NORMAL, "1x Normal", "1"),
            (BattleSpeed.FAST, "2x Fast", "2"),
            (BattleSpeed.FASTER, "4x Faster", "3"),
            (BattleSpeed.INSTANT, "Instant", "4"),
        ]

        current_speed = self.battle_scene.speed_mode
        for i, (speed, label, key) in enumerate(speeds):
            btn_y = y + 95 + i * 38
            is_selected = current_speed == speed

            # Radio button style
            btn_color = "gold" if is_selected else "default"
            btn = sprites.create_button(280, 30, is_selected, btn_color)
            self.screen.blit(btn, (x + 35, btn_y))

            # Radio circle
            circle_color = PALETTE['gold'] if is_selected else PALETTE['gray']
            pygame.draw.circle(self.screen, circle_color, (x + 55, btn_y + 15), 8, 2)
            if is_selected:
                pygame.draw.circle(self.screen, PALETTE['gold'], (x + 55, btn_y + 15), 4)

            # Label
            text_color = PALETTE['black'] if is_selected else PALETTE['cream']
            text = self.font_medium.render(f"[{key}] {label}", True, text_color)
            self.screen.blit(text, (x + 75, btn_y + 5))

        # Close hint
        close_text = self.font_medium.render("[ESC] Close", True, PALETTE['gray'])
        self.screen.blit(close_text, (x + w // 2 - 45, y + h - 40))

    def _draw_character_select(self) -> None:
        """Draw character selection screen with portraits."""
        self._draw_background()

        # Title
        title = self.font_large.render("SELECT YOUR CHARACTER", True, PALETTE['gold'])
        self.screen.blit(title, (self.WINDOW_WIDTH // 2 - 150, 25))

        gold_text = self.font_medium.render(f"Gold: {self.game.persistent.current_gold}", True, PALETTE['gold'])
        self.screen.blit(gold_text, (self.WINDOW_WIDTH // 2 - 45, 60))

        char_ids = list(CHARACTERS.keys())
        col_w = 480

        for i, cid in enumerate(char_ids):
            ch = CHARACTERS[cid]
            col = i % 2
            row = i // 2
            x = 30 + col * col_w
            y = 95 + row * 62

            is_sel = i == self.selected_character_index
            is_unlocked = self.game.persistent.is_character_unlocked(cid)

            # Selection panel
            if is_sel:
                sel_panel = sprites.create_panel(col_w - 15, 58, "gold")
                self.screen.blit(sel_panel, (x - 5, y - 3))
            else:
                bg_panel = sprites.create_panel(col_w - 15, 58, "default")
                self.screen.blit(bg_panel, (x - 5, y - 3))

            # Portrait
            portrait = sprites.create_character_portrait(cid, 48)
            if not is_unlocked:
                # Darken locked characters
                dark_overlay = pygame.Surface((48, 48), pygame.SRCALPHA)
                dark_overlay.fill((0, 0, 0, 150))
                portrait.blit(dark_overlay, (0, 0))
            self.screen.blit(portrait, (x + 5, y + 2))

            # Name
            name_col = PALETTE['gold'] if is_sel else PALETTE['cream'] if is_unlocked else PALETTE['gray']
            name_txt = ch.name
            if not is_unlocked:
                name_txt += f" [{ch.cost}g]"
            name_text = self.font_medium.render(name_txt, True, name_col)
            self.screen.blit(name_text, (x + 60, y + 2))

            # Dice info
            dice_text = self.font_small.render(ch.dice_description, True, PALETTE['cyan'])
            self.screen.blit(dice_text, (x + 60, y + 22))

            # Pros/cons
            pros_text = self.font_tiny.render(f"+ {ch.pros}", True, PALETTE['green'])
            self.screen.blit(pros_text, (x + 60, y + 38))

            cons_text = self.font_tiny.render(f"- {ch.cons}", True, PALETTE['red'])
            self.screen.blit(cons_text, (x + 250, y + 38))

        # Controls
        ctrl_text = self.font_medium.render(
            "[ARROWS] Select  [ENTER] Confirm  [ESC] Quick Start", True, PALETTE['cream'])
        self.screen.blit(ctrl_text, (self.WINDOW_WIDTH // 2 - 220, self.WINDOW_HEIGHT - 40))
