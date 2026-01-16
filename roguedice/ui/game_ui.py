"""Pygame-based pixel art game UI with polished graphics and battle animations."""

import pygame
import sys
import math
import random
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field

from ..services.game_service import GameService, TurnResult
from ..components.board_square import BoardSquareComponent
from ..components.item import ItemComponent
from ..models.enums import SquareType, Rarity, ItemType, ItemTheme, Element
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


@dataclass
class TimingMinigame:
    """Timing bar minigame state - HARD MODE."""
    active: bool = False
    bar_position: float = 0.0  # 0.0 to 1.0, position of the moving indicator
    bar_speed: float = 3.0  # FASTER - was 1.5
    bar_direction: int = 1  # 1 = right, -1 = left
    sweet_spot_start: float = 0.42  # Smaller sweet spot
    sweet_spot_end: float = 0.52  # Only 10% of bar (was 20%)
    grace_period: float = 1.5  # Time before bar starts moving
    result: Optional[str] = None  # "win", "lose", None
    result_timer: float = 0.0  # Time to show result
    reward_item_id: Optional[int] = None


@dataclass
class RouletteMinigame:
    """Roulette wheel minigame state."""
    active: bool = False
    wheel_angle: float = 0.0  # Current rotation in radians
    wheel_speed: float = 12.0  # Angular velocity
    is_spinning: bool = False
    stopped: bool = False
    grace_period: float = 1.5  # Time before player can spin
    result: Optional[str] = None  # "win", "lose", None
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None
    selected_segment: int = -1
    reward_type: str = ""  # What reward was won


@dataclass
class ClawMinigame:
    """Claw machine minigame state."""
    active: bool = False
    claw_x: float = 225.0  # Horizontal position
    claw_y: float = 60.0  # Vertical position (top)
    claw_state: str = "moving"  # "moving", "dropping", "grabbing", "rising", "done"
    attempts_left: int = 2
    held_item: Optional[str] = None  # What item claw grabbed
    held_item_tier: int = 0  # Prize tier: 1=common, 2=rare, 3=epic
    items: List = field(default_factory=list)  # [x, y, type, is_rock, tier]
    grace_period: float = 1.5  # Time before player can move claw
    result: Optional[str] = None
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None
    # Conveyor belt - items move sideways
    conveyor_speed: float = 30.0  # Pixels per second
    conveyor_direction: int = 1  # 1 = right, -1 = left
    # Claw sway while dropping
    claw_sway: float = 0.0  # Current sway offset
    sway_speed: float = 8.0  # How fast it sways
    sway_amplitude: float = 25.0  # Max sway distance
    drop_time: float = 0.0  # Time since drop started


@dataclass
class FlappyMinigame:
    """Flappy bird style minigame state."""
    active: bool = False
    bird_y: float = 175.0  # Bird vertical position
    bird_velocity: float = 0.0
    obstacles: List = field(default_factory=list)  # (x, gap_y, gap_height)
    coins: List = field(default_factory=list)  # (x, y, collected)
    coins_collected: int = 0
    coins_needed: int = 5
    game_timer: float = 0.0
    time_limit: float = 10.0
    grace_period: float = 1.0  # 1 second before bird starts falling
    result: Optional[str] = None
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None


@dataclass
class ArcheryMinigame:
    """Archery target shooting minigame state."""
    active: bool = False
    # Bow and aim
    bow_y: float = 175.0  # Vertical position of bow (center of panel)
    aim_angle: float = 0.0  # Angle in degrees (-30 to +30)
    # Power meter
    power: float = 0.0  # 0.0 to 1.0
    charging: bool = False  # Is player holding space
    # Arrow state
    arrow_flying: bool = False
    arrow_x: float = 0.0
    arrow_y: float = 0.0
    arrow_vx: float = 0.0
    arrow_vy: float = 0.0
    # Target
    target_x: float = 380.0  # Fixed X position
    target_y: float = 175.0  # Vertical position (can move)
    target_moving: bool = False
    target_direction: int = 1  # 1 = down, -1 = up
    target_speed: float = 60.0
    # Wind
    wind_strength: float = 0.0  # Negative = left, positive = right (affects Y in this case)
    # Scoring
    shots_taken: int = 0
    shots_allowed: int = 5
    bullseyes: int = 0
    bullseyes_needed: int = 2
    score: int = 0  # Total points
    # Timing
    grace_period: float = 1.5  # Time before game starts
    last_hit_text: str = ""  # "BULLSEYE!", "GOOD!", "MISS!"
    last_hit_timer: float = 0.0
    # Result
    result: Optional[str] = None
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None


@dataclass
class BlacksmithMinigame:
    """Blacksmith gamble minigame - risk upgrading an item's rarity."""
    active: bool = False
    # Item being upgraded
    item_id: Optional[int] = None
    current_rarity: int = 0  # 0=Common, 1=Uncommon, 2=Rare, 3=Epic, 4=Legendary
    rarity_names: List[str] = field(default_factory=lambda: ["Common", "Uncommon", "Rare", "Epic", "Legendary"])
    # Upgrade state
    upgrade_level: int = 0  # 0, 1, 2 (number of successful upgrades)
    success_chances: List[float] = field(default_factory=lambda: [0.80, 0.50, 0.10])  # 80%, 50%, 10%
    # Animation state
    is_rolling: bool = False  # Currently showing upgrade animation
    roll_timer: float = 0.0  # Animation timer
    roll_duration: float = 1.5  # How long the suspense animation lasts
    roll_result: Optional[bool] = None  # True=success, False=fail, None=not rolled yet
    sparks_timer: float = 0.0  # For spark animation
    # Player choice
    player_chose: bool = False  # Has player made a choice this round
    item_broken: bool = False  # Item was destroyed
    # Grace period
    grace_period: float = 1.0
    # Result
    result: Optional[str] = None  # "win" (kept item) or "lose" (item broke)
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None


@dataclass
class MonsterMinigame:
    """Monster attack minigame - press arrow sequences to survive!

    Spawns after curse squares. Fail = 30% HP damage, Pass = 10% heal + item chance.
    4 rounds, 10 seconds each. Arrow counts: R1=4, R2=8, R3=16, R4=20
    """
    active: bool = False
    # Round progression
    current_round: int = 1  # 1-4
    max_rounds: int = 4
    arrows_per_round: List[int] = field(default_factory=lambda: [4, 8, 16, 20])
    # Current sequence
    sequence: List[str] = field(default_factory=list)  # ["up", "down", "left", "right"]
    player_index: int = 0  # Current position in sequence player needs to hit
    # Timing
    round_timer: float = 10.0  # 10 seconds per round
    round_time_limit: float = 10.0
    grace_period: float = 2.0  # Brief "GET READY" before input starts
    # Display state (no longer used but kept for compatibility)
    showing_sequence: bool = False  # Always False - no memorization phase
    sequence_show_index: int = 0  # Unused
    sequence_show_timer: float = 0.0  # Unused
    # Feedback
    last_input_correct: Optional[bool] = None  # True/False/None for feedback flash
    input_flash_timer: float = 0.0
    # Monster theming
    monster_name: str = "Shadow Beast"
    attack_name: str = "Dark Pulse"
    # Result
    result: Optional[str] = None  # "win", "lose"
    result_timer: float = 0.0
    reward_item_id: Optional[int] = None


@dataclass
class BossCinematic:
    """Epic boss introduction cinematic state."""
    active: bool = False
    phase: str = "none"  # "awaken", "speech", "exit", "transition", "entrance"
    timer: float = 0.0
    # Dragon position for exit animation (normalized 0-1, then offscreen)
    dragon_x: float = 0.5  # Center
    dragon_y: float = 0.5
    # Speech bubble
    speech_text: str = ""
    speech_index: int = 0
    # Screen effects
    screen_flash: float = 0.0
    screen_shake: float = 0.0
    # Battle data to pass along
    pending_battle_result: Optional[object] = None
    # Dragon scale for dramatic effect
    dragon_scale: float = 1.0


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
        self.blessing_rects: List[Tuple[pygame.Rect, 'Blessing']] = []  # For tooltip hover
        self.hovered_blessing: Optional['Blessing'] = None

        # Animations
        self.dice_anim = DiceAnimation()
        self.player_movement = PlayerMovement()
        self.particle_effects: List[Dict] = []
        self.floating_texts: List[Dict] = []  # Floating text animations
        self.screen_shake = 0.0
        self.transition_alpha = 0

        # Minigame state
        self.timing_game = TimingMinigame()
        self.roulette_game = RouletteMinigame()
        self.claw_game = ClawMinigame()
        self.flappy_game = FlappyMinigame()
        self.archery_game = ArcheryMinigame()
        self.blacksmith_game = BlacksmithMinigame()
        self.monster_game = MonsterMinigame()  # Arrow sequence survival minigame
        self.minigame_corner: int = 0  # Which corner triggered current minigame
        self.pending_corner_function: bool = False  # Process corner after item choice

        # Dragon speech bubble
        self.dragon_last_chains = 8
        self.dragon_speech: Optional[str] = None
        self.dragon_speech_timer: float = 0.0
        self.dragon_taunt_cooldown: float = 0.0  # Cooldown between idle taunts
        # Chain break quotes - escalate from amused to threatening
        self.DRAGON_QUOTES = [
            "You're... rolling dice? In MY lair? How quaint.",
            "Round and round you go... enjoying yourself?",
            "That's two chains down. Eight more holding me. No pressure.",
            "I can feel it loosening... you should probably leave.",
            "Halfway there, little adventurer. Getting nervous yet?",
            "Four chains left. I can almost taste freedom. And you.",
            "THREE chains. The floor is starting to shake...",
            "TWO chains. I'd start running if I were you.",
            "One chain. ONE. You should see the look on your face right now.",
            "FREEDOM! Finally! NOW it's MY turn to roll... YOUR BONES!",
        ]
        # Random idle taunts while player explores - reference impending fight
        self.DRAGON_IDLE_TAUNTS = [
            "Tick tock. Every roll brings you closer to ME.",
            "That's your build? Against ME? Bold strategy.",
            "I'm literally RIGHT HERE. Counting down the rounds.",
            "Oh no, a goblin! Good practice for what's coming. *chuckle*",
            "Keep grinding. You'll need every stat point. Trust me.",
            "You missed a chest. Might've had something useful for our... date.",
            "I've been watching you fight. Taking notes. Finding weaknesses.",
            "Is this your first roguelike? Cute. I'll go easy. I won't.",
            "Those monsters? Warm-up. I'M the final exam.",
            "Pro tip: maybe don't fight everything? Save your HP for me.",
            "That item? Trash. Won't save you from dragon fire.",
            "You're getting stronger... almost strong enough to make this fun.",
            "Remember, I'm watching your every move. Learning your patterns.",
            "Another lap! Heal up at START while you still can.",
            "Keep walking MY board. Soon I'll walk YOU into the ground.",
            "Your dice hate you. Don't worry, I hate you more.",
            "Keep collecting gold. You won't need it where you're going.",
            "This used to be a peaceful lair. Soon it'll be your grave.",
        ]

        # Boss cinematic for epic final battle intro
        self.boss_cinematic = BossCinematic()
        self.BOSS_ENTRANCE_QUOTES = [
            "FINALLY! Do you have ANY idea how BORING it was watching you?!",
            "10 rounds. 10 ROUNDS of you playing board games in my home!",
            "Oh, you thought this was YOUR game? YOUR rules? ADORABLE.",
            "I memorized every move. Every mistake. Every close call.",
            "*cracks neck* Centuries of isometrics. IN CHAINS. Let's see if it paid off.",
            "You looted my lair, killed my minions, and NOW you face ME.",
            "No more dice. No more lucky rolls. Just you and ME.",
            "GG? No no no. The game STARTS now. GET OVER HERE!",
            "Speed run's over. Tutorial's done. THIS is the real game.",
            "I watched you nearly die to a GOBLIN. A GOBLIN! This'll be quick.",
            "All those laps around START? Should've kept running. OUT THE DOOR.",
            "Hope you saved! Oh wait... roguelike. HAHAHAHA! No saves for you!",
        ]

        # Battle scene
        self.battle_scene = BattleScene(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.pending_turn_result: Optional[TurnResult] = None
        self.square_processing_pending: bool = False  # Defer square changes until after animation

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
        # Block all input during boss cinematic - don't let player skip!
        if self.boss_cinematic.active:
            return

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
        elif self.state == "minigame":
            self._handle_minigame_keys(event)

    def _handle_minigame_keys(self, event: pygame.event.Event) -> None:
        """Handle keys during minigame."""
        # TIMING MINIGAME
        if self.timing_game.active:
            if not self.timing_game.result:
                if self.timing_game.grace_period > 0:
                    # Skip grace period with space
                    if event.key == pygame.K_SPACE:
                        self.timing_game.grace_period = 0
                elif event.key == pygame.K_SPACE:
                    pos = self.timing_game.bar_position
                    if self.timing_game.sweet_spot_start <= pos <= self.timing_game.sweet_spot_end:
                        self.timing_game.result = "win"
                        self._add_particles(self.WINDOW_WIDTH - 245, 300, PALETTE['gold'], 30)
                        self._generate_minigame_reward(self.timing_game)
                    else:
                        self.timing_game.result = "lose"
                        self.screen_shake = 0.3
                    self.timing_game.result_timer = 2.0
            elif self.timing_game.result_timer <= 0:
                self._finish_minigame(self.timing_game)
            return

        # ROULETTE MINIGAME
        if self.roulette_game.active:
            if not self.roulette_game.result:
                if self.roulette_game.grace_period > 0:
                    # Skip grace period with space
                    if event.key == pygame.K_SPACE:
                        self.roulette_game.grace_period = 0
                elif event.key == pygame.K_SPACE and not self.roulette_game.is_spinning:
                    self.roulette_game.is_spinning = True
            elif self.roulette_game.result_timer <= 0:
                self._finish_minigame(self.roulette_game)
            return

        # CLAW MINIGAME
        if self.claw_game.active:
            if not self.claw_game.result:
                if self.claw_game.grace_period > 0:
                    # Skip grace period with space
                    if event.key == pygame.K_SPACE:
                        self.claw_game.grace_period = 0
                elif self.claw_game.claw_state == "moving":
                    if event.key == pygame.K_LEFT:
                        self.claw_game.claw_x = max(70, self.claw_game.claw_x - 20)
                    elif event.key == pygame.K_RIGHT:
                        self.claw_game.claw_x = min(350, self.claw_game.claw_x + 20)
                    elif event.key == pygame.K_SPACE:
                        self.claw_game.claw_state = "dropping"
            elif self.claw_game.result_timer <= 0:
                self._finish_minigame(self.claw_game)
            return

        # FLAPPY MINIGAME
        if self.flappy_game.active:
            if not self.flappy_game.result:
                if event.key == pygame.K_SPACE:
                    # End grace period on first jump
                    self.flappy_game.grace_period = 0
                    self.flappy_game.bird_velocity = -280  # Jump!
            elif self.flappy_game.result_timer <= 0:
                self._finish_minigame(self.flappy_game)
            return

        # ARCHERY MINIGAME
        if self.archery_game.active:
            if not self.archery_game.result:
                if self.archery_game.grace_period <= 0 and not self.archery_game.arrow_flying:
                    # Aim controls
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.archery_game.aim_angle = max(-30, self.archery_game.aim_angle - 5)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.archery_game.aim_angle = min(30, self.archery_game.aim_angle + 5)
                    # Shoot
                    elif event.key == pygame.K_SPACE:
                        self._archery_shoot()
                elif event.key == pygame.K_SPACE and self.archery_game.grace_period > 0:
                    # Skip grace period
                    self.archery_game.grace_period = 0
            elif self.archery_game.result_timer <= 0:
                self._finish_minigame(self.archery_game)
            return

        # BLACKSMITH MINIGAME
        if self.blacksmith_game.active:
            if not self.blacksmith_game.result:
                if self.blacksmith_game.grace_period <= 0 and not self.blacksmith_game.is_rolling:
                    # SPACE or UP = Upgrade (gamble)
                    if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                        self._blacksmith_upgrade()
                    # DOWN or ESCAPE = Keep item and leave
                    elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_ESCAPE):
                        self._blacksmith_keep()
                elif event.key == pygame.K_SPACE and self.blacksmith_game.grace_period > 0:
                    self.blacksmith_game.grace_period = 0
            elif self.blacksmith_game.result_timer <= 0:
                self._finish_minigame(self.blacksmith_game)
            return

        # MONSTER MINIGAME - Arrow sequence survival
        if self.monster_game.active:
            if not self.monster_game.result:
                # Arrow key map for input
                arrow_map = {
                    pygame.K_UP: "up", pygame.K_w: "up",
                    pygame.K_DOWN: "down", pygame.K_s: "down",
                    pygame.K_LEFT: "left", pygame.K_a: "left",
                    pygame.K_RIGHT: "right", pygame.K_d: "right",
                }

                # Skip grace period on any arrow key press and process input immediately
                if self.monster_game.grace_period > 0 and event.key in arrow_map:
                    self.monster_game.grace_period = 0

                if self.monster_game.grace_period <= 0:
                    if event.key in arrow_map:
                        pressed = arrow_map[event.key]
                        expected = self.monster_game.sequence[self.monster_game.player_index]

                        if pressed == expected:
                            # Correct input!
                            self.monster_game.last_input_correct = True
                            self.monster_game.input_flash_timer = 0.15
                            self.monster_game.player_index += 1

                            # Check if round complete
                            if self.monster_game.player_index >= len(self.monster_game.sequence):
                                self._monster_round_complete()
                        else:
                            # Wrong input - reset progress (timer keeps running)
                            self.monster_game.last_input_correct = False
                            self.monster_game.input_flash_timer = 0.3
                            self.monster_game.player_index = 0  # Reset to beginning of sequence
                            self.screen_shake = 0.2
                            self._add_floating_text("Reset!", self.WINDOW_WIDTH - 200, 180, PALETTE['red'], 0.8)
            elif self.monster_game.result_timer <= 0:
                self._finish_monster_minigame()
            return

    def _monster_round_complete(self) -> None:
        """Handle completion of a monster minigame round."""
        game = self.monster_game

        if game.current_round >= game.max_rounds:
            # All rounds complete - WIN!
            game.result = "win"
            game.result_timer = 2.5
            self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['gold'], 40)
            self._add_floating_text("SURVIVED!", self.WINDOW_WIDTH - 200, 250, PALETTE['gold'], 1.5)
        else:
            # Advance to next round
            game.current_round += 1
            game.sequence = self._generate_monster_round_sequence(game.current_round)
            game.player_index = 0
            game.round_timer = game.round_time_limit
            game.showing_sequence = False  # No memorization phase - start input immediately
            game.grace_period = 1.0  # Brief pause between rounds
            self._add_floating_text(f"Round {game.current_round}!", self.WINDOW_WIDTH - 200, 150, PALETTE['cyan'], 1.0)

    def _blacksmith_upgrade(self) -> None:
        """Attempt to upgrade the item in blacksmith minigame."""
        import random
        game = self.blacksmith_game

        if game.is_rolling or game.upgrade_level >= 3:
            return

        # Start the roll animation
        game.is_rolling = True
        game.roll_timer = 0.0

        # Determine success
        chance = game.success_chances[game.upgrade_level]
        game.roll_result = random.random() < chance

    def _blacksmith_keep(self) -> None:
        """Keep the current item and end the minigame."""
        game = self.blacksmith_game

        if game.is_rolling:
            return

        # Player wins with current item
        game.result = "win"
        game.reward_item_id = game.item_id
        game.result_timer = 2.0
        self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['gold'], 20)
        # Update the actual item's rarity
        self._update_blacksmith_item_rarity(game)

    def _update_blacksmith_item_rarity(self, game) -> None:
        """Update the actual item's rarity based on blacksmith upgrades."""
        from ..models.enums import Rarity
        from ..components.item import ItemComponent

        if game.item_id is None:
            return

        # Map current_rarity index to Rarity enum
        rarity_map = {
            0: Rarity.COMMON,
            1: Rarity.UNCOMMON,
            2: Rarity.RARE,
            3: Rarity.EPIC,
            4: Rarity.LEGENDARY,
        }

        new_rarity = rarity_map.get(game.current_rarity, Rarity.COMMON)

        # Update the item component
        item_comp = self.game.world.get_component(game.item_id, ItemComponent)
        if item_comp:
            item_comp.rarity = new_rarity

    def _archery_shoot(self) -> None:
        """Fire an arrow in the archery minigame."""
        import math
        game = self.archery_game
        if game.arrow_flying or game.shots_taken >= game.shots_allowed:
            return

        # Calculate arrow velocity based on power and angle
        power = game.power
        speed = 200 + power * 300  # 200-500 pixels per second
        angle_rad = math.radians(game.aim_angle)

        game.arrow_flying = True
        game.arrow_x = 70.0
        game.arrow_y = game.bow_y
        game.arrow_vx = speed * math.cos(angle_rad)
        game.arrow_vy = speed * math.sin(angle_rad)
        game.shots_taken += 1

    def _generate_minigame_reward(self, minigame) -> None:
        """Generate item reward for winning a minigame with rarity rolling."""
        import random
        from ..models.enums import Rarity
        player = self.game.get_player_data()
        round_num = player.current_round if player else 1

        # Roll for rarity - base is Rare, but can roll higher!
        # 60% Rare, 30% Epic, 10% Legendary
        roll = random.random()
        if roll < 0.10:  # 10% Legendary
            rarity = Rarity.LEGENDARY
            tier_bonus = 8
            self._add_floating_text("LEGENDARY!", self.WINDOW_WIDTH // 2, 150, (255, 215, 0), 2.0)
        elif roll < 0.40:  # 30% Epic
            rarity = Rarity.EPIC
            tier_bonus = 5
            self._add_floating_text("Epic Drop!", self.WINDOW_WIDTH // 2, 150, (200, 100, 255), 1.5)
        else:  # 60% Rare
            rarity = Rarity.RARE
            tier_bonus = 3

        minigame.reward_item_id = self.game.item_factory.create_item(
            round_num + tier_bonus,
            rarity=rarity
        )

    def _generate_roulette_reward(self, minigame) -> None:
        """Generate reward for roulette based on reward_type."""
        from ..models.enums import Rarity
        player = self.game.get_player_data()
        round_num = player.current_round if player else 1

        reward_type = minigame.reward_type
        if reward_type == "epic":
            # Epic item!
            minigame.reward_item_id = self.game.item_factory.create_item(
                round_num + 5,
                rarity=Rarity.EPIC
            )
        elif reward_type == "rare":
            # Rare item
            minigame.reward_item_id = self.game.item_factory.create_item(
                round_num + 3,
                rarity=Rarity.RARE
            )
        elif reward_type == "gold":
            # Gold reward - give player gold instead of item
            if player:
                gold_amount = 50 + round_num * 20
                player.gold += gold_amount
                self._add_floating_text(f"+{gold_amount} Gold!", self.WINDOW_WIDTH - 200, 200, PALETTE['gold'], 1.5)
            minigame.reward_item_id = None
        elif reward_type == "blessing":
            # Blessing - heal player and give small stat buff
            player_stats = self.game.get_player_stats()
            if player_stats:
                heal_amount = int(player_stats.max_hp * 0.25)
                player_stats.heal(heal_amount)
                self._add_floating_text(f"+{heal_amount} HP!", self.WINDOW_WIDTH - 200, 200, PALETTE['green'], 1.5)
            minigame.reward_item_id = None

    def _generate_claw_reward(self, minigame) -> None:
        """Generate reward for claw machine based on prize tier."""
        from ..models.enums import Rarity
        player = self.game.get_player_data()
        round_num = player.current_round if player else 1

        tier = minigame.held_item_tier
        if tier == 3:  # Gold/Epic tier
            minigame.reward_item_id = self.game.item_factory.create_item(
                round_num + 5,
                rarity=Rarity.EPIC
            )
            self._add_floating_text("EPIC PRIZE!", self.WINDOW_WIDTH - 200, 180, PALETTE['gold'], 1.5)
        elif tier == 2:  # Silver/Rare tier
            minigame.reward_item_id = self.game.item_factory.create_item(
                round_num + 3,
                rarity=Rarity.RARE
            )
            self._add_floating_text("Rare Prize!", self.WINDOW_WIDTH - 200, 180, (150, 200, 255), 1.5)
        else:  # Bronze/Common tier
            # Give gold instead of item for common prizes
            if player:
                gold_amount = 25 + round_num * 10
                player.gold += gold_amount
                self._add_floating_text(f"+{gold_amount} Gold", self.WINDOW_WIDTH - 200, 180, PALETTE['cream'], 1.5)
            minigame.reward_item_id = None

    def _finish_minigame(self, minigame) -> None:
        """Finish a minigame and process corner function."""
        won = minigame.result == "win"
        reward_id = minigame.reward_item_id if won else None

        # Reset the minigame
        if isinstance(minigame, TimingMinigame):
            self.timing_game = TimingMinigame()
        elif isinstance(minigame, RouletteMinigame):
            self.roulette_game = RouletteMinigame()
        elif isinstance(minigame, ClawMinigame):
            self.claw_game = ClawMinigame()
        elif isinstance(minigame, FlappyMinigame):
            self.flappy_game = FlappyMinigame()
        elif isinstance(minigame, ArcheryMinigame):
            self.archery_game = ArcheryMinigame()
        elif isinstance(minigame, BlacksmithMinigame):
            self.blacksmith_game = BlacksmithMinigame()

        if won and reward_id:
            # Show item choice first, then process corner
            self.pending_item_id = reward_id
            self.pending_corner_function = True  # Flag to process corner after item choice
            self.state = "item_choice"
        else:
            # No reward, go straight to corner function
            self._process_corner_after_minigame()

    def _process_corner_after_minigame(self) -> None:
        """Process the corner's normal function after minigame."""
        result = self.game.process_corner_function(self.minigame_corner)

        if result['opened_merchant']:
            self.state = "merchant"
        elif result['healed']:
            self.message_log.append("Rested at the Inn! HP restored.")
            self._add_floating_text("FULL HEAL!", 300, 200, PALETTE['green'], 1.5)
            self._add_particles(300, 200, PALETTE['green'], 20)
            self.state = "playing"
        else:
            self.state = "playing"

        self.minigame_corner = 0

    def _finish_monster_minigame(self) -> None:
        """Finish the monster minigame - apply damage or heal rewards."""
        import random
        from ..models.enums import Rarity

        game = self.monster_game
        won = game.result == "win"

        player_stats = self.game.get_player_stats()

        if won:
            # Player survived! 10% heal and chance for item
            heal_amount = int(player_stats.max_hp * 0.10)
            actual_heal = player_stats.heal(heal_amount)
            if actual_heal > 0:
                self.message_log.append(f"Survived the {game.monster_name}! Healed {actual_heal} HP!")
                self._add_floating_text(f"+{actual_heal} HP", self.WINDOW_WIDTH - 200, 280, PALETTE['green'], 1.5)

            # 25% chance for item reward with rarity rolling
            if random.random() < 0.25:
                player = self.game.get_player_data()
                round_num = player.current_round if player else 1

                # Roll for rarity - 10% Mythical, 3% Legendary, 12% Epic, 30% Rare, 45% Uncommon
                rarity_roll = random.random()
                if rarity_roll < 0.10:  # 10% Mythical
                    rarity = Rarity.MYTHICAL
                    tier_bonus = 12
                    self._add_floating_text("MYTHICAL DROP!!!", self.WINDOW_WIDTH - 200, 240, (255, 0, 128), 2.5)
                elif rarity_roll < 0.13:  # 3% Legendary
                    rarity = Rarity.LEGENDARY
                    tier_bonus = 8
                    self._add_floating_text("LEGENDARY DROP!", self.WINDOW_WIDTH - 200, 240, (255, 215, 0), 2.0)
                elif rarity_roll < 0.25:  # 12% Epic
                    rarity = Rarity.EPIC
                    tier_bonus = 5
                    self._add_floating_text("Epic Drop!", self.WINDOW_WIDTH - 200, 240, (200, 100, 255), 1.5)
                elif rarity_roll < 0.55:  # 30% Rare
                    rarity = Rarity.RARE
                    tier_bonus = 3
                    self._add_floating_text("Rare Drop!", self.WINDOW_WIDTH - 200, 240, (100, 150, 255), 1.2)
                else:  # 45% Uncommon
                    rarity = Rarity.UNCOMMON
                    tier_bonus = 1

                item_id = self.game.item_factory.create_item(round_num + tier_bonus, rarity=rarity)
                self.pending_item_id = item_id
                self.state = "item_choice"
                self.message_log.append("The creature dropped something!")
            else:
                self.state = "playing"
        else:
            # Player failed! 30% max HP damage
            damage = int(player_stats.max_hp * 0.30)
            player_stats.take_damage(damage)
            self.message_log.append(f"The {game.monster_name}'s {game.attack_name} hits you for {damage} damage!")
            self._add_floating_text(f"-{damage} HP", self.WINDOW_WIDTH - 200, 280, PALETTE['red'], 1.5)
            self.screen_shake = 0.3

            # Check for death
            if player_stats.current_hp <= 0:
                self.game.is_game_over = True
                self.state = "game_over"
            else:
                self.state = "playing"

        # Reset the minigame
        self.monster_game = MonsterMinigame()

    def start_timing_minigame(self, difficulty: str = "normal") -> None:
        """Start the timing bar minigame with given difficulty - HARD MODE."""
        # Difficulty settings - MUCH HARDER than before
        if difficulty == "easy":
            sweet_size = random.uniform(0.12, 0.18)  # Was 0.25-0.35
            bar_speed = random.uniform(2.0, 2.8)  # Was 1.0-1.3
        elif difficulty == "hard":
            sweet_size = random.uniform(0.06, 0.10)  # Was 0.1-0.15
            bar_speed = random.uniform(3.5, 4.5)  # Was 2.0-2.5
        else:  # normal
            sweet_size = random.uniform(0.08, 0.14)  # Was 0.15-0.25
            bar_speed = random.uniform(2.8, 3.5)  # Was 1.3-1.8

        # Randomize sweet spot position (not at edges)
        sweet_start = random.uniform(0.15, 0.85 - sweet_size)

        self.timing_game = TimingMinigame(
            active=True,
            bar_position=0.0,
            bar_speed=bar_speed,
            bar_direction=1,
            sweet_spot_start=sweet_start,
            sweet_spot_end=sweet_start + sweet_size,
            grace_period=1.5,
            result=None,
            result_timer=0.0,
            reward_item_id=None
        )
        self.state = "minigame"

    def start_roulette_minigame(self, difficulty: str = "normal") -> None:
        """Start the roulette wheel minigame."""
        # Initial spin speed varies by difficulty
        if difficulty == "easy":
            speed = random.uniform(8.0, 12.0)
        elif difficulty == "hard":
            speed = random.uniform(14.0, 20.0)
        else:
            speed = random.uniform(10.0, 15.0)

        self.roulette_game = RouletteMinigame(
            active=True,
            wheel_angle=random.uniform(0, 2 * 3.14159),
            wheel_speed=speed,
            is_spinning=False,
            stopped=False,
            grace_period=0.7,
            result=None,
            result_timer=0.0,
            reward_item_id=None,
            selected_segment=-1,
            reward_type=""
        )
        self.state = "minigame"

    def start_claw_minigame(self, difficulty: str = "normal") -> None:
        """Start the claw machine minigame with moving prizes."""
        # Pit area: x:60-360, items move on conveyor belt
        items = []
        pit_left, pit_right = 60, 360
        pit_bottom = 300

        # Conveyor speed based on difficulty
        if difficulty == "easy":
            conveyor_speed = 20.0
            sway_amp = 15.0
        elif difficulty == "hard":
            conveyor_speed = 50.0
            sway_amp = 35.0
        else:
            conveyor_speed = 35.0
            sway_amp = 25.0

        # Prize tiers: more common items, fewer rare/epic
        # Tier 1 (common/bronze): gold coins - 5 items
        for i in range(5):
            x = pit_left + 30 + i * 60  # Spread evenly
            y = pit_bottom - 10 + random.uniform(-5, 5)
            items.append([x, y, "bronze", False, 1])

        # Tier 2 (rare/silver): potions - 3 items
        for i in range(3):
            x = pit_left + 50 + i * 100
            y = pit_bottom - 15 + random.uniform(-5, 5)
            items.append([x, y, "silver", False, 2])

        # Tier 3 (epic/gold): gems - 1 item (the prize!)
        x = random.uniform(pit_left + 80, pit_right - 80)
        y = pit_bottom - 20
        items.append([x, y, "gold", False, 3])

        # Shuffle item positions a bit
        random.shuffle(items)
        for i, item in enumerate(items):
            item[0] = pit_left + 30 + (i * 35) % (pit_right - pit_left - 60)

        self.claw_game = ClawMinigame(
            active=True,
            claw_x=225.0,
            claw_y=60.0,
            claw_state="moving",
            attempts_left=2,  # Always 2 attempts
            held_item=None,
            held_item_tier=0,
            items=items,
            grace_period=1.5,
            result=None,
            result_timer=0.0,
            reward_item_id=None,
            conveyor_speed=conveyor_speed,
            conveyor_direction=1,
            claw_sway=0.0,
            sway_speed=8.0,
            sway_amplitude=sway_amp,
            drop_time=0.0,
        )
        self.state = "minigame"

    def start_flappy_minigame(self, difficulty: str = "normal") -> None:
        """Start the flappy bird minigame."""
        # Difficulty settings (increased time limits for longer gameplay)
        if difficulty == "easy":
            gap_height = 120
            time_limit = 15.0
            coins_needed = 4
            scroll_speed = 120
        elif difficulty == "hard":
            gap_height = 70
            time_limit = 11.0
            coins_needed = 6
            scroll_speed = 180
        else:
            gap_height = 90
            time_limit = 13.0
            coins_needed = 5
            scroll_speed = 150

        # Generate initial obstacles and coins (start further away for grace period)
        obstacles = []
        coins = []
        for i in range(6):
            x = 550 + i * 150  # Start obstacles further away
            gap_y = random.uniform(100, 250)
            obstacles.append([x, gap_y, gap_height])
            coins.append([x + 20, gap_y, False])

        self.flappy_game = FlappyMinigame(
            active=True,
            bird_y=175.0,
            bird_velocity=0.0,
            obstacles=obstacles,
            coins=coins,
            coins_collected=0,
            coins_needed=coins_needed,
            game_timer=0.0,
            time_limit=time_limit,
            grace_period=1.0,  # 1 second before bird starts falling
            result=None,
            result_timer=0.0,
            reward_item_id=None
        )
        self.flappy_game.scroll_speed = scroll_speed  # Store for update
        self.state = "minigame"

    def start_archery_minigame(self, difficulty: str = "normal") -> None:
        """Start the archery target shooting minigame."""
        import random

        # Difficulty settings
        if difficulty == "easy":
            shots_allowed = 6
            bullseyes_needed = 2
            target_moving = False
            target_speed = 0.0
            wind_strength = 0.0
        elif difficulty == "hard":
            shots_allowed = 4
            bullseyes_needed = 3
            target_moving = True
            target_speed = 80.0
            wind_strength = random.uniform(-40, 40)
        else:  # normal
            shots_allowed = 5
            bullseyes_needed = 2
            target_moving = True
            target_speed = 50.0
            wind_strength = random.uniform(-25, 25)

        self.archery_game = ArcheryMinigame(
            active=True,
            bow_y=175.0,
            aim_angle=0.0,
            power=0.0,
            charging=False,
            arrow_flying=False,
            arrow_x=60.0,
            arrow_y=175.0,
            arrow_vx=0.0,
            arrow_vy=0.0,
            target_x=380.0,
            target_y=175.0,
            target_moving=target_moving,
            target_direction=1,
            target_speed=target_speed,
            wind_strength=wind_strength,
            shots_taken=0,
            shots_allowed=shots_allowed,
            bullseyes=0,
            bullseyes_needed=bullseyes_needed,
            score=0,
            grace_period=1.5,
            last_hit_text="",
            last_hit_timer=0.0,
            result=None,
            result_timer=0.0,
            reward_item_id=None
        )
        self.state = "minigame"

    def start_blacksmith_minigame(self, difficulty: str = "normal") -> None:
        """Start the blacksmith gamble minigame."""
        import random
        from ..models.enums import Rarity
        player = self.game.get_player_data()
        round_num = player.current_round if player else 1

        # Roll for starting rarity: 47.5% Common, 47.5% Uncommon, 5% Rare
        roll = random.random()
        if roll < 0.475:
            start_rarity = 0  # Common
            item_rarity = Rarity.COMMON
        elif roll < 0.95:
            start_rarity = 1  # Uncommon
            item_rarity = Rarity.UNCOMMON
        else:
            start_rarity = 2  # Rare
            item_rarity = Rarity.RARE

        # Create item with the rolled rarity
        item_id = self.game.item_factory.create_item(round_num, rarity=item_rarity)

        self.blacksmith_game = BlacksmithMinigame(
            active=True,
            item_id=item_id,
            current_rarity=start_rarity,
            upgrade_level=0,
            is_rolling=False,
            roll_timer=0.0,
            roll_result=None,
            sparks_timer=0.0,
            player_chose=False,
            item_broken=False,
            grace_period=1.0,
            result=None,
            result_timer=0.0,
            reward_item_id=None
        )
        self.state = "minigame"

    def start_monster_minigame(self) -> None:
        """Start the monster attack minigame - survive 5 rounds of arrow sequences!

        Triggered by curse squares. Fail = 30% HP damage, Pass = 10% heal + item chance.
        """
        import random

        # Monster names for variety
        monster_names = [
            ("Shadow Beast", "Dark Pulse"),
            ("Cursed Specter", "Soul Drain"),
            ("Nightmare Fiend", "Terror Wave"),
            ("Void Walker", "Abyss Strike"),
            ("Demon Spawn", "Hellfire Burst"),
        ]
        monster_name, attack_name = random.choice(monster_names)

        # Generate first round sequence
        arrows = ["up", "down", "left", "right"]
        first_sequence = [random.choice(arrows) for _ in range(4)]  # Round 1 = 4 arrows

        self.monster_game = MonsterMinigame(
            active=True,
            current_round=1,
            max_rounds=4,
            arrows_per_round=[4, 8, 16, 20],
            sequence=first_sequence,
            player_index=0,
            round_timer=10.0,
            round_time_limit=10.0,
            grace_period=2.0,  # Brief "GET READY" before starting
            showing_sequence=False,  # No memorization - show all arrows immediately
            sequence_show_index=0,
            sequence_show_timer=0.0,
            last_input_correct=None,
            input_flash_timer=0.0,
            monster_name=monster_name,
            attack_name=attack_name,
            result=None,
            result_timer=0.0,
            reward_item_id=None
        )
        self.state = "minigame"

    def _generate_monster_round_sequence(self, round_num: int) -> List[str]:
        """Generate arrow sequence for a monster minigame round."""
        import random
        arrows = ["up", "down", "left", "right"]
        count = self.monster_game.arrows_per_round[round_num - 1]
        return [random.choice(arrows) for _ in range(count)]

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

        # Reset all minigame states
        self.timing_game = TimingMinigame()
        self.roulette_game = RouletteMinigame()
        self.claw_game = ClawMinigame()
        self.flappy_game = FlappyMinigame()
        self.archery_game = ArcheryMinigame()
        self.blacksmith_game = BlacksmithMinigame()
        self.monster_game = MonsterMinigame()
        self.minigame_corner = 0
        self.pending_corner_function = False

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
            # Check if we need to process corner function after minigame win
            if self.pending_corner_function:
                self.pending_corner_function = False
                self._process_corner_after_minigame()
            else:
                self.state = "playing"
        elif event.key in (pygame.K_s, pygame.K_ESCAPE):
            gold = self.game.sell_item(self.pending_item_id)
            self.message_log.append(f"Sold for {gold}g!")
            self._add_particles(self.WINDOW_WIDTH // 2, self.WINDOW_HEIGHT // 2, PALETTE['gold'], 15)
            self.pending_item_id = None
            # Check if we need to process corner function after minigame win
            if self.pending_corner_function:
                self.pending_corner_function = False
                self._process_corner_after_minigame()
            else:
                self.state = "playing"
        self.message_log = self.message_log[-8:]

    def _handle_merchant_keys(self, event: pygame.event.Event) -> None:
        """Handle keys at merchant."""
        merchant = self.game.merchant_inventory
        if not merchant:
            self.state = "playing"
            return

        if event.key == pygame.K_ESCAPE:
            # Close merchant and make them travel to a new square
            new_idx = self.game.close_merchant_and_travel()
            self.message_log.append(f"Merchant travels to square {new_idx}!")
            self.state = "playing"
        elif event.key == pygame.K_r:
            # Reroll merchant inventory
            cost = merchant.reroll_cost
            if self.game.reroll_merchant_inventory():
                self.message_log.append(f"Rerolled! (-{cost}g)")
                self._add_particles(self.WINDOW_WIDTH // 2, 300, PALETTE['gold'], 15)
            else:
                self.message_log.append(f"Need {cost}g to reroll!")
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

        # Defer square processing until movement animation completes
        result = self.game.take_turn(defer_square_processing=True)
        self.last_turn_result = result
        self.square_processing_pending = True  # Will process after animation

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

        # Store result to process after movement animation completes
        self.pending_turn_result = result

        # Check for combat - start battle scene (will process after battle)
        if result.combat_result:
            self._start_battle(result)

    def _start_boss_cinematic(self, result: TurnResult) -> None:
        """Start the epic boss introduction cinematic."""
        import random
        self.boss_cinematic = BossCinematic(
            active=True,
            phase="awaken",
            timer=0.0,
            dragon_x=0.5,  # Start at center
            dragon_y=0.5,
            speech_text="",
            speech_index=0,
            screen_flash=1.0,  # Start with flash
            screen_shake=0.5,
            pending_battle_result=result,
            dragon_scale=1.0,
        )
        # Play dramatic sound effect placeholder
        self.message_log.append("The Ancient Dragon breaks free!")

    def _start_battle(self, result: TurnResult) -> None:
        """Start the Pokemon-style battle scene."""
        player = self.game.get_player_data()
        stats = self.game.get_player_stats()

        if not player or not stats or not result.combat_result:
            return

        is_boss = result.is_boss_fight

        # For boss fights, start the epic cinematic first
        if is_boss and not self.boss_cinematic.active:
            self._start_boss_cinematic(result)
            return

        # Get monster info from combat result
        monster_name = result.combat_result.monster_name or "Monster"
        monster_type = result.combat_result.monster_sprite or "goblin"

        # Use actual monster HP from combat result
        monster_max_hp = result.combat_result.monster_max_hp
        if monster_max_hp <= 0:
            # Fallback if not set (shouldn't happen)
            monster_max_hp = 50 + player.current_round * 10

        if is_boss:
            monster_type = "dragon"
            monster_name = "Ancient Dragon"

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
        """Finish battle and show combat results (further processing waits for movement)."""
        self.battle_scene.dismiss()

        if self.pending_turn_result:
            result = self.pending_turn_result
            # Don't clear pending_turn_result - let _update() process it after movement completes

            # Add combat results to log immediately
            self.combat_log = result.combat_result.log[-10:] if result.combat_result else []
            self.screen_shake = 0.3

            if result.combat_result:
                if result.combat_result.victory:
                    msg = f"Victory! +{result.gold_earned}g"
                    if result.is_boss_fight:
                        msg = "BOSS DEFEATED! " + msg
                        self._add_particles(300, 300, PALETTE['gold'], 30)
                    else:
                        # Dragon might comment on the battle
                        self._maybe_dragon_taunt()
                    self.message_log.append(msg)
                else:
                    self.message_log.append("Defeated!")

    def _process_turn_result(self, result: TurnResult) -> None:
        """Process non-combat turn results."""
        if result.blessing_received:
            self.message_log.append(f"Blessing: {result.blessing_received.name}")
            self._add_particles(300, 200, PALETTE['purple'], 15)
        if result.healed:
            if result.heal_amount > 0:
                self.message_log.append(f"Passed START! +{result.heal_amount} HP!")
                # Show floating heal text near player/start area
                self._add_floating_text(f"+{result.heal_amount} HP", 120, 430, PALETTE['green'], 2.0)
            else:
                self.message_log.append("Rested! HP restored.")
                self._add_floating_text("FULL HEAL!", 300, 200, PALETTE['green'], 1.5)
            self._add_particles(300, 200, PALETTE['green'], 15)
        if result.monsters_spawned:
            # Curse triggered!
            num = len(result.monsters_spawned)
            self.message_log.append(f"CURSED! {num} monsters spawned!")
            self._add_particles(300, 200, (150, 50, 180), 20)  # Purple particles
            self.screen_shake = 0.4
        if result.trigger_monster_minigame:
            # Monster attack minigame from curse!
            self.message_log.append("A dark creature attacks!")
            self._add_particles(300, 200, PALETTE['red'], 25)
            self.screen_shake = 0.3
            self.start_monster_minigame()
            return  # Don't process other results until minigame is done
        if result.trigger_minigame:
            # Store which corner triggered this minigame
            self.minigame_corner = result.minigame_corner

            # Determine difficulty based on round
            player = self.game.get_player_data()
            round_num = player.current_round if player else 1
            if round_num <= 5:
                difficulty = "easy"
            elif round_num <= 15:
                difficulty = "normal"
            else:
                difficulty = "hard"

            # Start the appropriate minigame
            if result.trigger_minigame == "timing":
                self.message_log.append("MINIGAME: Timing Challenge!")
                self._add_particles(300, 200, PALETTE['gold'], 15)
                self.start_timing_minigame(difficulty)
            elif result.trigger_minigame == "roulette":
                self.message_log.append("MINIGAME: Wheel of Fortune!")
                self._add_particles(300, 200, PALETTE['purple'], 15)
                self.start_roulette_minigame(difficulty)
            elif result.trigger_minigame == "claw":
                self.message_log.append("MINIGAME: Claw Machine!")
                self._add_particles(300, 200, (100, 200, 255), 15)
                self.start_claw_minigame(difficulty)
            elif result.trigger_minigame == "flappy":
                self.message_log.append("MINIGAME: Flappy Challenge!")
                self._add_particles(300, 200, PALETTE['green'], 15)
                self.start_flappy_minigame(difficulty)
            elif result.trigger_minigame == "archery":
                self.message_log.append("MINIGAME: Archery Challenge!")
                self._add_particles(300, 200, (139, 90, 43), 15)
                self.start_archery_minigame(difficulty)
            elif result.trigger_minigame == "blacksmith":
                self.message_log.append("MINIGAME: Blacksmith's Gamble!")
                self._add_particles(300, 200, (255, 150, 50), 15)
                self.start_blacksmith_minigame(difficulty)
            return  # Don't process other results until minigame is done
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

        # Maybe trigger a dragon taunt after player action
        if self.state == "playing":
            self._maybe_dragon_taunt()

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

    def _add_floating_text(self, text: str, x: int, y: int, color: Tuple, duration: float = 1.5):
        """Add floating text that rises and fades."""
        self.floating_texts.append({
            'text': text,
            'x': x,
            'y': y,
            'vy': -60,  # Rise speed
            'life': duration,
            'max_life': duration,
            'color': color,
        })

    def _update_minigames(self, dt: float) -> None:
        """Update minigame state when a minigame is active."""
        # Update timing minigame
        if self.timing_game.active:
            if self.timing_game.result:
                self.timing_game.result_timer -= dt
                if self.timing_game.result_timer <= 0:
                    self._finish_minigame(self.timing_game)
            else:
                if self.timing_game.grace_period > 0:
                    self.timing_game.grace_period -= dt
                else:
                    self.timing_game.bar_position += self.timing_game.bar_speed * self.timing_game.bar_direction * dt
                    if self.timing_game.bar_position >= 1.0:
                        self.timing_game.bar_position = 1.0
                        self.timing_game.bar_direction = -1
                    elif self.timing_game.bar_position <= 0.0:
                        self.timing_game.bar_position = 0.0
                        self.timing_game.bar_direction = 1

        # Update roulette minigame
        if self.roulette_game.active:
            if self.roulette_game.result:
                self.roulette_game.result_timer -= dt
                if self.roulette_game.result_timer <= 0:
                    self._finish_minigame(self.roulette_game)
            else:
                if self.roulette_game.grace_period > 0:
                    self.roulette_game.grace_period -= dt
                elif self.roulette_game.is_spinning and not self.roulette_game.stopped:
                    self.roulette_game.wheel_angle += self.roulette_game.wheel_speed * dt
                    self.roulette_game.wheel_speed -= 6.0 * dt
                    if self.roulette_game.wheel_speed <= 0:
                        self.roulette_game.wheel_speed = 0
                        self.roulette_game.stopped = True
                        segment_angle = (2 * 3.14159) / 8
                        # Pointer is at TOP (angle -π/2 = 3π/2 in pygame coords)
                        # Find which segment the pointer is actually pointing at
                        pointer_angle = 3 * 3.14159 / 2  # 3π/2 = top of wheel
                        effective_angle = (pointer_angle - self.roulette_game.wheel_angle) % (2 * 3.14159)
                        self.roulette_game.selected_segment = int(effective_angle / segment_angle) % 8
                        if self.roulette_game.selected_segment in [0, 2, 4, 6]:
                            self.roulette_game.result = "win"
                            self.roulette_game.reward_type = ["epic", "gold", "rare", "blessing"][self.roulette_game.selected_segment // 2]
                            self._add_particles(self.WINDOW_WIDTH - 245, 280, PALETTE['gold'], 30)
                            self._generate_roulette_reward(self.roulette_game)
                        else:
                            self.roulette_game.result = "lose"
                            self.screen_shake = 0.2
                        self.roulette_game.result_timer = 1.2

        # Update claw minigame
        if self.claw_game.active:
            game = self.claw_game
            pit_left, pit_right = 60, 360

            # Always move conveyor belt (items slide left/right)
            if not game.result:
                for item in game.items:
                    item[0] += game.conveyor_speed * game.conveyor_direction * dt
                    # Bounce off walls
                    if item[0] <= pit_left + 15:
                        item[0] = pit_left + 15
                        game.conveyor_direction = 1
                    elif item[0] >= pit_right - 15:
                        item[0] = pit_right - 15
                        game.conveyor_direction = -1

            if game.result:
                game.result_timer -= dt
                if game.result_timer <= 0:
                    self._finish_minigame(game)
            else:
                if game.grace_period > 0:
                    game.grace_period -= dt
                elif game.claw_state == "dropping":
                    # Track drop time for sway calculation
                    game.drop_time += dt
                    # Claw sways while dropping (sine wave)
                    game.claw_sway = math.sin(game.drop_time * game.sway_speed) * game.sway_amplitude

                    game.claw_y += 200 * dt
                    if game.claw_y >= 300:
                        game.claw_y = 300
                        game.claw_state = "grabbing"
                        # Actual grab position includes sway
                        grab_x = game.claw_x + game.claw_sway
                        # Find closest item within grab range
                        grabbed = None
                        best_dist = 40  # Grab radius
                        for item in game.items:
                            x, y, item_type, is_rock, tier = item
                            dx = x - grab_x
                            dy = y - game.claw_y
                            dist = (dx * dx + dy * dy) ** 0.5
                            if dist < best_dist:
                                best_dist = dist
                                grabbed = item
                        if grabbed:
                            game.held_item = grabbed[2]
                            game.held_item_tier = grabbed[4]
                            game.items.remove(grabbed)
                            # Visual feedback based on tier
                            tier_colors = {1: PALETTE['gray_light'], 2: (150, 200, 255), 3: PALETTE['gold']}
                            tier_names = {1: "Bronze!", 2: "Silver!", 3: "GOLD!"}
                            color = tier_colors.get(grabbed[4], PALETTE['green'])
                            text = tier_names.get(grabbed[4], "Got it!")
                            self._add_floating_text(text, self.WINDOW_WIDTH - 200, 280, color, 0.8)
                        else:
                            self._add_floating_text("Miss!", self.WINDOW_WIDTH - 200, 280, PALETTE['red'], 0.8)
                        game.claw_state = "rising"
                        game.claw_sway = 0  # Reset sway for rising
                elif game.claw_state == "rising":
                    game.claw_y -= 150 * dt
                    # No dropping! Claw always keeps the item
                    if game.claw_y <= 60:
                        game.claw_y = 60
                        game.attempts_left -= 1
                        if game.held_item:
                            game.result = "win"
                            # Particles based on tier
                            tier_colors = {1: PALETTE['gray_light'], 2: (150, 200, 255), 3: PALETTE['gold']}
                            self._add_particles(self.WINDOW_WIDTH - 245, 150, tier_colors.get(game.held_item_tier, PALETTE['gold']), 30)
                            self._generate_claw_reward(game)
                            game.result_timer = 2.0
                        elif game.attempts_left <= 0:
                            game.result = "lose"
                            game.result_timer = 2.0
                        else:
                            game.claw_state = "moving"
                            game.held_item = None
                            game.drop_time = 0

        # Update flappy minigame
        if self.flappy_game.active:
            if self.flappy_game.result:
                self.flappy_game.result_timer -= dt
                if self.flappy_game.result_timer <= 0:
                    self._finish_minigame(self.flappy_game)
            else:
                if self.flappy_game.grace_period > 0:
                    self.flappy_game.grace_period -= dt
                else:
                    self.flappy_game.bird_velocity += 800 * dt
                    self.flappy_game.bird_y += self.flappy_game.bird_velocity * dt

                scroll_speed = getattr(self.flappy_game, 'scroll_speed', 150)
                for i, obs in enumerate(self.flappy_game.obstacles):
                    self.flappy_game.obstacles[i] = [obs[0] - scroll_speed * dt, obs[1], obs[2]]
                for i, coin in enumerate(self.flappy_game.coins):
                    self.flappy_game.coins[i] = [coin[0] - scroll_speed * dt, coin[1], coin[2]]

                if self.flappy_game.obstacles and self.flappy_game.obstacles[0][0] < -50:
                    self.flappy_game.obstacles.pop(0)
                    if self.flappy_game.coins and not self.flappy_game.coins[0][2]:
                        self.flappy_game.coins.pop(0)
                    last_x = self.flappy_game.obstacles[-1][0] if self.flappy_game.obstacles else 400
                    new_x = last_x + random.uniform(140, 180)
                    gap_y = random.uniform(100, 250)
                    gap_h = self.flappy_game.obstacles[0][2] if self.flappy_game.obstacles else 90
                    self.flappy_game.obstacles.append([new_x, gap_y, gap_h])
                    self.flappy_game.coins.append([new_x + 20, gap_y, False])

                bird_x = 80
                for i, coin in enumerate(self.flappy_game.coins):
                    if not coin[2] and abs(coin[0] - bird_x) < 25 and abs(coin[1] - self.flappy_game.bird_y) < 25:
                        self.flappy_game.coins[i][2] = True
                        self.flappy_game.coins_collected += 1
                        self._add_particles(self.WINDOW_WIDTH - 245 + int(coin[0]) // 5, 170 + int(coin[1]) // 3, PALETTE['gold'], 5)

                for obs in self.flappy_game.obstacles:
                    if abs(obs[0] - bird_x) < 25:
                        gap_top = obs[1] - obs[2] / 2
                        gap_bottom = obs[1] + obs[2] / 2
                        if self.flappy_game.bird_y < gap_top or self.flappy_game.bird_y > gap_bottom:
                            self.flappy_game.result = "lose"
                            self.screen_shake = 0.3
                            self.flappy_game.result_timer = 2.0
                            break

                if self.flappy_game.bird_y < 20 or self.flappy_game.bird_y > 330:
                    self.flappy_game.result = "lose"
                    self.screen_shake = 0.3
                    self.flappy_game.result_timer = 2.0

                self.flappy_game.game_timer += dt
                if self.flappy_game.coins_collected >= self.flappy_game.coins_needed:
                    self.flappy_game.result = "win"
                    self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['gold'], 30)
                    self._generate_minigame_reward(self.flappy_game)
                    self.flappy_game.result_timer = 2.0
                elif self.flappy_game.game_timer >= self.flappy_game.time_limit:
                    self.flappy_game.result = "lose"
                    self.flappy_game.result_timer = 2.0

        # Update archery minigame
        if self.archery_game.active:
            game = self.archery_game
            if game.result:
                game.result_timer -= dt
                if game.result_timer <= 0:
                    self._finish_minigame(self.archery_game)
            else:
                if game.grace_period > 0:
                    game.grace_period -= dt
                else:
                    if not game.arrow_flying:
                        game.power += dt * 1.5 * (1 if game.charging else 1)
                        if game.power >= 1.0:
                            game.power = 1.0
                            game.charging = False
                        elif game.power <= 0.0:
                            game.power = 0.0
                            game.charging = True
                        if not hasattr(game, '_power_dir'):
                            game._power_dir = 1
                        game.power += dt * 2.0 * game._power_dir
                        if game.power >= 1.0:
                            game.power = 1.0
                            game._power_dir = -1
                        elif game.power <= 0.0:
                            game.power = 0.0
                            game._power_dir = 1

                    if game.target_moving:
                        game.target_y += game.target_speed * game.target_direction * dt
                        if game.target_y > 280:
                            game.target_y = 280
                            game.target_direction = -1
                        elif game.target_y < 70:
                            game.target_y = 70
                            game.target_direction = 1

                    if game.arrow_flying:
                        game.arrow_vy += game.wind_strength * dt
                        game.arrow_vy += 50 * dt
                        game.arrow_x += game.arrow_vx * dt
                        game.arrow_y += game.arrow_vy * dt

                        if game.arrow_x >= game.target_x - 10:
                            dist = abs(game.arrow_y - game.target_y)
                            if dist < 12:
                                game.bullseyes += 1
                                game.score += 100
                                game.last_hit_text = "BULLSEYE!"
                                game.last_hit_timer = 1.0
                                self._add_particles(self.WINDOW_WIDTH - 100, int(200 + game.target_y - 175), PALETTE['gold'], 20)
                            elif dist < 30:
                                game.score += 50
                                game.last_hit_text = "GOOD!"
                                game.last_hit_timer = 1.0
                                self._add_particles(self.WINDOW_WIDTH - 100, int(200 + game.target_y - 175), PALETTE['green'], 10)
                            elif dist < 50:
                                game.score += 25
                                game.last_hit_text = "OK"
                                game.last_hit_timer = 1.0
                            else:
                                game.last_hit_text = "MISS!"
                                game.last_hit_timer = 1.0
                                self.screen_shake = 0.15

                            game.arrow_flying = False
                            if game.bullseyes >= game.bullseyes_needed:
                                game.result = "win"
                                self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['gold'], 30)
                                self._generate_minigame_reward(game)
                                game.result_timer = 2.5
                            elif game.shots_taken >= game.shots_allowed:
                                game.result = "lose"
                                game.result_timer = 2.5

                        elif game.arrow_x > 450 or game.arrow_y < 0 or game.arrow_y > 350:
                            game.arrow_flying = False
                            game.last_hit_text = "MISS!"
                            game.last_hit_timer = 1.0
                            if game.shots_taken >= game.shots_allowed:
                                game.result = "lose"
                                game.result_timer = 2.5

                if game.last_hit_timer > 0:
                    game.last_hit_timer -= dt

        # Update blacksmith minigame
        if self.blacksmith_game.active:
            game = self.blacksmith_game
            if game.result:
                game.result_timer -= dt
                if game.result_timer <= 0:
                    self._finish_minigame(self.blacksmith_game)
            else:
                if game.grace_period > 0:
                    game.grace_period -= dt
                else:
                    game.sparks_timer += dt
                    if game.is_rolling:
                        game.roll_timer += dt
                        if game.roll_timer >= game.roll_duration:
                            game.is_rolling = False
                            if game.roll_result:
                                game.current_rarity += 1
                                game.upgrade_level += 1
                                self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['gold'], 25)
                                self._add_floating_text("UPGRADED!", self.WINDOW_WIDTH - 200, 250, PALETTE['gold'], 1.5)
                                if game.current_rarity >= 4 or game.upgrade_level >= 3:
                                    game.result = "win"
                                    game.reward_item_id = game.item_id
                                    game.result_timer = 2.5
                                    # Update the actual item's rarity
                                    self._update_blacksmith_item_rarity(game)
                            else:
                                game.item_broken = True
                                game.result = "lose"
                                game.result_timer = 2.5
                                self.screen_shake = 0.4
                                self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['red'], 30)

        # Update monster minigame
        if self.monster_game.active:
            game = self.monster_game
            if game.result:
                game.result_timer -= dt
                if game.result_timer <= 0:
                    self._finish_monster_minigame()
            else:
                # Update input flash timer
                if game.input_flash_timer > 0:
                    game.input_flash_timer -= dt

                if game.grace_period > 0:
                    game.grace_period -= dt
                else:
                    # Input phase - countdown timer (no memorization phase)
                    game.round_timer -= dt
                    if game.round_timer <= 0:
                        # Time's up - FAIL!
                        game.result = "lose"
                        game.result_timer = 2.5
                        self.screen_shake = 0.4
                        self._add_particles(self.WINDOW_WIDTH - 245, 200, PALETTE['red'], 30)
                        self._add_floating_text("TIME'S UP!", self.WINDOW_WIDTH - 200, 200, PALETTE['red'], 1.5)

        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= dt

    def _update_boss_cinematic(self, dt: float) -> None:
        """Update the epic boss introduction cinematic."""
        import random
        cine = self.boss_cinematic
        cine.timer += dt

        # Update screen effects
        if cine.screen_flash > 0:
            cine.screen_flash -= dt * 2
        if cine.screen_shake > 0:
            cine.screen_shake -= dt

        if cine.phase == "awaken":
            # Phase 1: Dragon awakens (2 seconds) - dramatic buildup
            if cine.timer < 0.5:
                # Initial flash
                cine.screen_shake = 0.3
            elif cine.timer < 1.5:
                # Dragon scales up dramatically
                cine.dragon_scale = 1.0 + (cine.timer - 0.5) * 0.3
            elif cine.timer >= 2.0:
                # Transition to speech
                cine.phase = "speech"
                cine.timer = 0.0
                cine.speech_text = random.choice(self.BOSS_ENTRANCE_QUOTES)
                cine.screen_flash = 0.5

        elif cine.phase == "speech":
            # Phase 2: Dragon says something funny (3 seconds)
            if cine.timer >= 3.0:
                cine.phase = "exit"
                cine.timer = 0.0

        elif cine.phase == "exit":
            # Phase 3: Dragon moves right off the board (1.5 seconds)
            progress = min(1.0, cine.timer / 1.5)
            # Ease out - fast start, slow end
            eased = 1 - (1 - progress) ** 2
            cine.dragon_x = 0.5 + eased * 1.0  # Move from center (0.5) to off-screen (1.5)

            if cine.timer >= 1.5:
                cine.phase = "transition"
                cine.timer = 0.0
                cine.screen_flash = 0.8

        elif cine.phase == "transition":
            # Phase 4: Brief black screen transition (0.5 seconds)
            if cine.timer >= 0.5:
                # Start the actual battle with entrance animation
                cine.active = False
                if cine.pending_battle_result:
                    # Start battle with entrance flag
                    self._start_battle_with_entrance(cine.pending_battle_result)

    def _start_battle_with_entrance(self, result: TurnResult) -> None:
        """Start battle scene with monster entrance animation."""
        player = self.game.get_player_data()
        stats = self.game.get_player_stats()

        if not player or not stats or not result.combat_result:
            return

        monster_name = "Ancient Dragon"
        monster_type = "dragon"

        # Use actual boss HP from combat result
        monster_max_hp = result.combat_result.monster_max_hp
        if monster_max_hp <= 0:
            # Fallback (shouldn't happen with properly spawned boss)
            monster_max_hp = 12000 + player.current_round * 800

        # Start battle scene with entrance animation enabled
        self.battle_scene.start_battle(
            char_id=player.character_id,
            monster_type=monster_type,
            monster_name=monster_name,
            is_boss=True,
            combat_result=result.combat_result,
            player_max_hp=stats.max_hp,
            monster_max_hp=monster_max_hp,
            player_start_hp=stats.current_hp + result.combat_result.damage_taken,
            monster_start_hp=monster_max_hp,
            monster_entrance=True,  # Enable entrance animation
        )

    def _update(self, dt: float) -> None:
        """Update game state and animations."""
        # Update boss cinematic if active
        if self.boss_cinematic.active:
            self._update_boss_cinematic(dt)
            return

        # Update battle scene if active
        if self.battle_scene.is_active():
            self.battle_scene.update(dt)
            return

        # Check if any minigame is active - skip main game updates if so
        minigame_active = any([
            self.timing_game.active,
            self.roulette_game.active,
            self.claw_game.active,
            self.flappy_game.active,
            self.archery_game.active,
            self.blacksmith_game.active,
            self.monster_game.active
        ])

        if minigame_active:
            # Only update minigames, skip main game updates
            self._update_minigames(dt)
            return

        # Check for hovered item slot
        self.hovered_slot = None
        for slot in self.item_slots:
            if slot.rect.collidepoint(self.mouse_pos):
                self.hovered_slot = slot
                break

        # Check for hovered blessing
        self.hovered_blessing = None
        for rect, blessing in self.blessing_rects:
            if rect.collidepoint(self.mouse_pos):
                self.hovered_blessing = blessing
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

        # Process pending turn result after movement animation completes
        movement_done = not pm.path or pm.path_index >= len(pm.path) - 1
        if movement_done and self.pending_turn_result and not self.battle_scene.is_active():
            # First, process the landing square now that player has arrived
            if getattr(self, 'square_processing_pending', False):
                # This processes combat, items, blessings, etc. AND lap completion (board refill)
                updated_result = self.game.process_landing_square()
                # Merge the updated result (combat, items, etc.) with our pending result
                self.pending_turn_result = updated_result
                self.square_processing_pending = False
                # Invalidate board cache so new spawns are visible
                self._board_surface = None

                # Check if combat was triggered - start battle scene!
                if updated_result.combat_result:
                    self._start_battle(updated_result)
                    return  # Don't process other results until battle is done

            result = self.pending_turn_result
            self.pending_turn_result = None
            self._process_turn_result(result)

        # Update dragon speech bubble timer
        if self.dragon_speech_timer > 0:
            self.dragon_speech_timer -= dt
            if self.dragon_speech_timer <= 0:
                self.dragon_speech = None

        # Update dragon taunt cooldown
        if self.dragon_taunt_cooldown > 0:
            self.dragon_taunt_cooldown -= dt

        # Update particles
        for p in self.particle_effects[:]:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 300 * dt  # Gravity
            p['life'] -= dt
            if p['life'] <= 0:
                self.particle_effects.remove(p)

        # Update floating texts
        for ft in self.floating_texts[:]:
            ft['y'] += ft['vy'] * dt
            ft['life'] -= dt
            if ft['life'] <= 0:
                self.floating_texts.remove(ft)

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

            # Draw boss cinematic (full screen overlay)
            if self.boss_cinematic.active:
                self._draw_boss_cinematic()

            # Draw battle scene or minigame (in corner panel, over game but under overlays)
            elif self.battle_scene.is_active():
                self.battle_scene.draw(self.screen)
            elif self.timing_game.active:
                self._draw_timing_minigame()
            elif self.roulette_game.active:
                self._draw_roulette_minigame()
            elif self.claw_game.active:
                self._draw_claw_minigame()
            elif self.flappy_game.active:
                self._draw_flappy_minigame()
            elif self.archery_game.active:
                self._draw_archery_minigame()
            elif self.blacksmith_game.active:
                self._draw_blacksmith_minigame()
            elif self.monster_game.active:
                self._draw_monster_minigame()

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

            # Draw tooltips last
            if self.hovered_slot and self.hovered_slot.item_id:
                self._draw_item_tooltip(self.hovered_slot)
            elif self.hovered_blessing:
                self._draw_blessing_tooltip(self.hovered_blessing)

        # Draw floating texts and particles on top
        self._draw_floating_texts()
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
                False,  # Never draw player on tile
                square.index  # Pass square index for arcade indicator on corners
            )
            surface.blit(tile, (x, y))

            # Square number
            num_text = self.font_tiny.render(str(square.index), True, (200, 200, 200))
            surface.blit(num_text, (x + 2, y + 2))

        # Draw traveling merchant indicator
        merchant_idx = self.game.get_merchant_square_index()
        if merchant_idx != 10:  # Only show indicator if not at the shop corner
            mx, my = self._get_square_position(merchant_idx, board_x, board_y)
            # Draw a gold coin/bag icon to indicate merchant
            pygame.draw.circle(surface, PALETTE['gold'], (mx + self.SQUARE_SIZE - 8, my + 8), 6)
            pygame.draw.circle(surface, PALETTE['gold_dark'], (mx + self.SQUARE_SIZE - 8, my + 8), 6, 1)
            # $ symbol
            pygame.draw.line(surface, PALETTE['gold_dark'], (mx + self.SQUARE_SIZE - 8, my + 5), (mx + self.SQUARE_SIZE - 8, my + 11), 1)

        # Draw the chained dragon boss in center (AFTER squares)
        self._draw_chained_boss(surface, board_x, board_y)

        # Draw animated player token (AFTER dragon)
        self._draw_player_token(surface, board_x, board_y, player_pos)

    def _draw_chained_boss(self, surface: pygame.Surface, board_x: int, board_y: int) -> None:
        """Draw the chained dragon boss in the board center."""
        # Don't draw dragon in center if boss cinematic is active (dragon is animating elsewhere)
        if self.boss_cinematic.active:
            return

        center_x = board_x + self.BOARD_SIZE // 2
        center_y = board_y + self.BOARD_SIZE // 2

        player = self.game.get_player_data()
        current_round = player.current_round if player else 1
        boss_round = 10  # Boss breaks free at round 10

        # Calculate chains remaining (all 10 chains break by round 10)
        total_chains = 10
        # Linear progression: lose 1 chain per round
        chains_broken = min(total_chains, current_round)
        chains_remaining = total_chains - chains_broken

        # Detect chain break and trigger speech bubble
        if chains_remaining < self.dragon_last_chains:
            # A chain just broke!
            chain_index = total_chains - chains_remaining - 1
            self.dragon_speech = self.DRAGON_QUOTES[chain_index % len(self.DRAGON_QUOTES)]
            self.dragon_speech_timer = 3.0  # Show for 3 seconds
            self.screen_shake = 0.3
        self.dragon_last_chains = chains_remaining

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

        # Draw chains around the dragon (10 chains for 10 rounds)
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
            (center_x, center_y - 80),       # Top-center
            (center_x, center_y + 70),       # Bottom-center
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

        # Draw dragon speech bubble if active
        if self.dragon_speech and self.dragon_speech_timer > 0:
            self._draw_dragon_speech_bubble(surface, center_x, dragon_y - 20)

    def _maybe_dragon_taunt(self, force: bool = False) -> None:
        """Maybe trigger a random dragon idle taunt."""
        import random
        # Don't taunt if already speaking or on cooldown
        if self.dragon_speech_timer > 0:
            return
        if not force and self.dragon_taunt_cooldown > 0:
            return

        # 15% chance to taunt (or 100% if forced)
        if not force and random.random() > 0.15:
            return

        # Don't taunt if dragon is free (boss fight imminent)
        player = self.game.get_player_data()
        if player and player.current_round >= 10:
            return

        self.dragon_speech = random.choice(self.DRAGON_IDLE_TAUNTS)
        self.dragon_speech_timer = 3.5
        self.dragon_taunt_cooldown = 12.0  # At least 12 seconds between taunts

    def _draw_dragon_speech_bubble(self, surface: pygame.Surface, x: int, y: int) -> None:
        """Draw a speech bubble above the dragon."""
        text = self.font_small.render(self.dragon_speech, True, (40, 20, 20))
        text_w, text_h = text.get_width(), text.get_height()

        # Bubble dimensions
        padding = 8
        bubble_w = text_w + padding * 2
        bubble_h = text_h + padding * 2
        bubble_x = x - bubble_w // 2
        bubble_y = y - bubble_h

        # Bobbing animation
        bob = math.sin(pygame.time.get_ticks() / 150) * 3

        # Draw bubble background (white with border)
        bubble_surf = pygame.Surface((bubble_w + 4, bubble_h + 15), pygame.SRCALPHA)

        # Main bubble
        pygame.draw.ellipse(bubble_surf, (255, 255, 240), (2, 2, bubble_w, bubble_h))
        pygame.draw.ellipse(bubble_surf, (80, 60, 40), (2, 2, bubble_w, bubble_h), 2)

        # Speech bubble tail (pointing down)
        tail_points = [
            (bubble_w // 2, bubble_h),
            (bubble_w // 2 - 8, bubble_h - 2),
            (bubble_w // 2 + 5, bubble_h + 12),
        ]
        pygame.draw.polygon(bubble_surf, (255, 255, 240), tail_points)
        pygame.draw.lines(bubble_surf, (80, 60, 40), False, tail_points, 2)

        # Draw text
        bubble_surf.blit(text, (padding + 2, padding + 2))

        # Blit to surface with fade based on timer
        alpha = min(255, int(self.dragon_speech_timer * 100))
        bubble_surf.set_alpha(alpha)
        surface.blit(bubble_surf, (bubble_x, int(bubble_y + bob)))

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
                icon = sprites.create_item_icon(item_type, rarity, item.level, 40, item.theme, item.element)
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
        ]

        # Theme info
        if item.theme and item.theme != ItemTheme.NONE:
            theme_display = item.theme_display
            lines.append(f"Theme: {theme_display}")
            # Add effect description
            effect_desc = item.theme_effect_description
            if effect_desc:
                lines.append(f"  {effect_desc}")

        lines.append("")

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

        # Get theme color for themed items
        theme_color = None
        if item.theme and item.theme != ItemTheme.NONE:
            theme_color = item.theme.color
            if item.theme == ItemTheme.ELEMENTAL and item.element != Element.NONE:
                theme_color = item.element.color

        # Text
        for i, line in enumerate(lines):
            if i == 0:
                color = colors[0]  # Rarity color for name
            elif "Theme:" in line and theme_color:
                color = theme_color
            elif line.startswith("  ") and "+" in line:
                color = PALETTE['green']
            elif line.startswith("  ") and theme_color and i > 0 and "Theme:" in lines[i-1]:
                # Effect description line - use theme color but dimmer
                color = tuple(min(255, c + 50) for c in theme_color)
            elif "Sell:" in line:
                color = PALETTE['gold']
            else:
                color = PALETTE['cream']

            text = self.font_small.render(line, True, color)
            tooltip_surf.blit(text, (padding, padding + i * line_height))

        self.screen.blit(tooltip_surf, (tx, ty))

    def _draw_blessing_tooltip(self, blessing) -> None:
        """Draw tooltip for hovered blessing."""
        from ..models.blessings import BlessingType

        # Build tooltip lines
        lines = []
        lines.append((blessing.name, PALETTE['purple_light']))

        # Effect description based on blessing type
        effect_desc = {
            BlessingType.CRIT_BOOST: f"+{blessing.value*100:.0f}% Critical Chance",
            BlessingType.DAMAGE_BOOST: f"+{blessing.value:.0f} Damage",
            BlessingType.DEFENSE_BOOST: f"+{blessing.value:.0f} Defense",
            BlessingType.ATTACK_SPEED: f"+{blessing.value*100:.0f}% Attack Speed",
            BlessingType.LIFE_STEAL: f"+{blessing.value*100:.0f}% Life Steal",
            BlessingType.DODGE: f"+{blessing.value*100:.0f}% Dodge Chance",
            BlessingType.MAX_HP: f"+{blessing.value:.0f} Max HP",
            BlessingType.GOLD_FIND: f"+{blessing.value*100:.0f}% Gold Find",
        }
        effect = effect_desc.get(blessing.blessing_type, f"Effect: {blessing.value}")
        lines.append((effect, PALETTE['cream']))

        # Duration
        if blessing.is_permanent:
            lines.append(("Permanent", PALETTE['gold']))
        else:
            lines.append((f"Duration: {blessing.duration} rounds", PALETTE['gray_light']))

        # Draw tooltip
        padding = 10
        line_height = 18
        tooltip_w = 180
        tooltip_h = len(lines) * line_height + padding * 2

        tx = min(self.mouse_pos[0] + 15, self.WINDOW_WIDTH - tooltip_w - 10)
        ty = min(self.mouse_pos[1] + 15, self.WINDOW_HEIGHT - tooltip_h - 10)

        tooltip_surf = pygame.Surface((tooltip_w, tooltip_h), pygame.SRCALPHA)
        pygame.draw.rect(tooltip_surf, (25, 15, 35, 240), (0, 0, tooltip_w, tooltip_h), border_radius=6)
        pygame.draw.rect(tooltip_surf, PALETTE['purple'], (0, 0, tooltip_w, tooltip_h), 2, border_radius=6)

        for i, (text, color) in enumerate(lines):
            rendered = self.font_small.render(text, True, color)
            tooltip_surf.blit(rendered, (padding, padding + i * line_height))

        self.screen.blit(tooltip_surf, (tx, ty))

    def _draw_timing_minigame(self) -> None:
        """Draw the timing bar minigame in the battle panel area."""
        # Panel dimensions (same as battle scene)
        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        # Create panel surface
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)

        # Panel background
        pygame.draw.rect(panel, (20, 25, 35, 240), (0, 0, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(panel, PALETTE['gold'], (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Title
        title = self.font_large.render("TIMING CHALLENGE", True, PALETTE['gold'])
        title_rect = title.get_rect(centerx=panel_w // 2, y=15)
        panel.blit(title, title_rect)

        # Instructions
        instr = self.font_small.render("Press SPACE when the bar is in the gold zone!", True, PALETTE['cream'])
        instr_rect = instr.get_rect(centerx=panel_w // 2, y=50)
        panel.blit(instr, instr_rect)

        # Timing bar area
        bar_x = 40
        bar_y = 120
        bar_w = panel_w - 80
        bar_h = 50

        # Draw bar background
        pygame.draw.rect(panel, (30, 35, 45), (bar_x, bar_y, bar_w, bar_h), border_radius=6)

        # Draw sweet spot (gold zone)
        sweet_x = bar_x + int(self.timing_game.sweet_spot_start * bar_w)
        sweet_w = int((self.timing_game.sweet_spot_end - self.timing_game.sweet_spot_start) * bar_w)
        pygame.draw.rect(panel, (60, 50, 20), (sweet_x, bar_y, sweet_w, bar_h), border_radius=6)
        pygame.draw.rect(panel, PALETTE['gold'], (sweet_x, bar_y, sweet_w, bar_h), 2, border_radius=6)

        # Draw bar outline
        pygame.draw.rect(panel, PALETTE['gray_light'], (bar_x, bar_y, bar_w, bar_h), 2, border_radius=6)

        # Draw moving indicator
        if not self.timing_game.result:
            indicator_x = bar_x + int(self.timing_game.bar_position * bar_w)
            indicator_w = 8
            pygame.draw.rect(panel, PALETTE['red'], (indicator_x - indicator_w // 2, bar_y - 5, indicator_w, bar_h + 10), border_radius=3)
            pygame.draw.rect(panel, (255, 200, 200), (indicator_x - indicator_w // 2 + 2, bar_y - 3, indicator_w - 4, bar_h + 6), border_radius=2)

        # Draw difficulty info
        difficulty = "Normal"
        spot_size = self.timing_game.sweet_spot_end - self.timing_game.sweet_spot_start
        if spot_size < 0.15:
            difficulty = "Hard"
        elif spot_size > 0.25:
            difficulty = "Easy"
        diff_text = self.font_small.render(f"Difficulty: {difficulty}", True, PALETTE['gray_light'])
        panel.blit(diff_text, (bar_x, bar_y + bar_h + 15))

        # Speed indicator
        speed_text = self.font_small.render(f"Speed: {self.timing_game.bar_speed:.1f}x", True, PALETTE['gray_light'])
        panel.blit(speed_text, (bar_x + bar_w - 80, bar_y + bar_h + 15))

        # Grace period overlay
        if self.timing_game.grace_period > 0 and not self.timing_game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("GET READY!", True, PALETTE['gold'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 20)))
            hint_text = self.font_small.render("Press SPACE when the bar hits the gold zone!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 20)))

        # Draw result with dark overlay
        elif self.timing_game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if self.timing_game.result == "win":
                result_text = "SUCCESS!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render("You won a rare item!", True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Perfect timing!", True, PALETTE['gold'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                result_text = "MISSED!"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("No reward this time...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Better luck next time!", True, PALETTE['gray_light'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_roulette_minigame(self) -> None:
        """Draw the roulette wheel minigame."""
        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (20, 25, 35, 240), (0, 0, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(panel, PALETTE['purple'], (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Title
        title = self.font_large.render("WHEEL OF FORTUNE", True, PALETTE['purple'])
        panel.blit(title, title.get_rect(centerx=panel_w // 2, y=15))

        # Wheel center
        cx, cy = panel_w // 2, 180
        radius = 100

        # Segment colors and labels
        segments = [
            (PALETTE['gold'], "EPIC"),
            ((80, 80, 90), "MISS"),
            (PALETTE['green'], "GOLD"),
            ((80, 80, 90), "MISS"),
            ((100, 150, 255), "RARE"),
            ((80, 80, 90), "MISS"),
            (PALETTE['purple'], "BLESS"),
            ((80, 80, 90), "MISS"),
        ]

        # Draw wheel segments
        segment_angle = 2 * 3.14159 / 8
        for i, (color, label) in enumerate(segments):
            start = i * segment_angle + self.roulette_game.wheel_angle
            # Draw pie segment
            points = [(cx, cy)]
            for j in range(11):
                angle = start + j * segment_angle / 10
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                points.append((int(x), int(y)))
            points.append((cx, cy))
            pygame.draw.polygon(panel, color, points)
            pygame.draw.polygon(panel, PALETTE['black'], points, 1)

        # Wheel outline
        pygame.draw.circle(panel, PALETTE['gray_light'], (cx, cy), radius, 3)
        pygame.draw.circle(panel, PALETTE['gold'], (cx, cy), 15)

        # Pointer at top
        pygame.draw.polygon(panel, PALETTE['red'], [(cx - 12, 65), (cx + 12, 65), (cx, 90)])

        # Grace period overlay
        if self.roulette_game.grace_period > 0 and not self.roulette_game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("GET READY!", True, PALETTE['purple'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 20)))
            hint_text = self.font_small.render("Press SPACE to spin the wheel!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 20)))

        # Instructions or result
        elif not self.roulette_game.is_spinning and not self.roulette_game.result:
            instr = self.font_medium.render("Press SPACE to spin!", True, PALETTE['cream'])
            panel.blit(instr, instr.get_rect(centerx=panel_w // 2, y=310))
        elif self.roulette_game.result:
            # Dark overlay for result
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if self.roulette_game.result == "win":
                result_text = "YOU WON!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render(f"Prize: {self.roulette_game.reward_type.upper()}!", True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Lucky spin!", True, PALETTE['gold'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                result_text = "MISS!"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("No reward this time...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Better luck next time!", True, PALETTE['gray_light'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_claw_minigame(self) -> None:
        """Draw the claw machine minigame with conveyor belt and tiered prizes."""
        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170
        game = self.claw_game

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (25, 35, 45, 240), (0, 0, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(panel, (100, 200, 255), (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Title
        title = self.font_large.render("PRIZE CATCHER", True, (100, 200, 255))
        panel.blit(title, title.get_rect(centerx=panel_w // 2, y=10))

        # Attempts with visual indicators
        for i in range(2):
            color = PALETTE['gold'] if i < game.attempts_left else (60, 60, 70)
            pygame.draw.circle(panel, color, (30 + i * 25, 50), 8)
        attempts_text = self.font_small.render("Tries", True, PALETTE['cream'])
        panel.blit(attempts_text, (70, 43))

        # Prize legend
        legend_y = 70
        pygame.draw.circle(panel, (205, 127, 50), (panel_w - 100, legend_y), 6)  # Bronze
        panel.blit(self.font_small.render("= Gold", True, PALETTE['cream']), (panel_w - 88, legend_y - 8))
        pygame.draw.circle(panel, (192, 192, 220), (panel_w - 100, legend_y + 18), 6)  # Silver
        panel.blit(self.font_small.render("= Rare", True, (150, 200, 255)), (panel_w - 88, legend_y + 10))
        pygame.draw.circle(panel, PALETTE['gold'], (panel_w - 100, legend_y + 36), 6)  # Gold
        panel.blit(self.font_small.render("= Epic!", True, PALETTE['gold']), (panel_w - 88, legend_y + 28))

        # Pit area with conveyor belt visual
        pit_rect = pygame.Rect(40, 180, panel_w - 80, 140)
        pygame.draw.rect(panel, (35, 40, 50), pit_rect, border_radius=4)

        # Conveyor belt lines (animated)
        belt_offset = int((pygame.time.get_ticks() / 50) * game.conveyor_direction) % 20
        for i in range(-1, 20):
            lx = pit_rect.left + (i * 20 + belt_offset) % (pit_rect.width + 20)
            if pit_rect.left <= lx <= pit_rect.right - 5:
                pygame.draw.line(panel, (50, 55, 65), (lx, pit_rect.bottom - 10), (lx + 10, pit_rect.bottom - 10), 2)

        # Conveyor direction arrows
        arrow_color = (80, 90, 100)
        arrow_x = pit_rect.centerx
        if game.conveyor_direction > 0:
            pygame.draw.polygon(panel, arrow_color, [(arrow_x + 30, pit_rect.bottom - 5), (arrow_x + 45, pit_rect.bottom - 12), (arrow_x + 30, pit_rect.bottom - 19)])
        else:
            pygame.draw.polygon(panel, arrow_color, [(arrow_x - 30, pit_rect.bottom - 5), (arrow_x - 45, pit_rect.bottom - 12), (arrow_x - 30, pit_rect.bottom - 19)])

        pygame.draw.rect(panel, (100, 200, 255), pit_rect, 2, border_radius=4)

        # Items with tier-based colors
        tier_colors = {
            1: (205, 127, 50),    # Bronze
            2: (192, 192, 220),   # Silver
            3: PALETTE['gold'],   # Gold
        }
        for item in game.items:
            x, y, item_type, is_rock, tier = item
            color = tier_colors.get(tier, PALETTE['cream'])
            size = 10 + tier * 2  # Bigger for better prizes
            pygame.draw.circle(panel, color, (int(x), int(y)), size)
            # Shine effect
            pygame.draw.circle(panel, (255, 255, 255, 180), (int(x) - size//3, int(y) - size//3), size//3)
            # Star for gold tier
            if tier == 3:
                pygame.draw.polygon(panel, (255, 255, 200), [
                    (int(x), int(y) - size - 5),
                    (int(x) + 3, int(y) - size + 2),
                    (int(x) - 3, int(y) - size + 2),
                ])

        # Claw - with sway offset when dropping
        cx = int(game.claw_x + game.claw_sway)
        cy = int(game.claw_y)
        # Cable
        pygame.draw.line(panel, (150, 150, 160), (int(game.claw_x), 50), (cx, cy), 2)
        # Claw arms (open wider when dropping, closed when holding)
        arm_spread = 22 if game.claw_state == "dropping" else 15 if game.held_item else 18
        pygame.draw.line(panel, (180, 180, 190), (cx, cy), (cx - arm_spread, cy + 25), 4)
        pygame.draw.line(panel, (180, 180, 190), (cx, cy), (cx + arm_spread, cy + 25), 4)
        # Claw tips
        pygame.draw.circle(panel, (200, 200, 210), (cx - arm_spread, cy + 25), 5)
        pygame.draw.circle(panel, (200, 200, 210), (cx + arm_spread, cy + 25), 5)
        pygame.draw.circle(panel, (200, 200, 210), (cx, cy), 8)

        # Held item
        if game.held_item:
            color = tier_colors.get(game.held_item_tier, PALETTE['cream'])
            pygame.draw.circle(panel, color, (cx, cy + 30), 10 + game.held_item_tier)

        # Grace period overlay
        if game.grace_period > 0 and not game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("GET READY!", True, (100, 200, 255))
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 20)))
            hint_text = self.font_small.render("Prizes move! Time your drop!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 20)))

        # Instructions
        elif not game.result:
            instr = self.font_small.render("< > Move   SPACE Drop   Claw sways!", True, PALETTE['cream'])
            panel.blit(instr, instr.get_rect(centerx=panel_w // 2, y=330))
        else:
            # Dark overlay for result
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if game.result == "win":
                tier_names = {1: "BRONZE!", 2: "SILVER!", 3: "GOLD!!!"}
                tier_msgs = {1: "You got some gold coins!", 2: "You won a rare item!", 3: "EPIC PRIZE!!!"}
                result_text = tier_names.get(game.held_item_tier, "SUCCESS!")
                result_color = tier_colors.get(game.held_item_tier, PALETTE['gold'])
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render(tier_msgs.get(game.held_item_tier, "You grabbed a prize!"), True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Nice grab!", True, result_color)
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                result_text = "NO PRIZE"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("Couldn't grab anything...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("Better luck next time!", True, PALETTE['gray_light'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_flappy_minigame(self) -> None:
        """Draw the flappy bird minigame."""
        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)

        # Sky gradient
        for y in range(panel_h):
            t = y / panel_h
            color = (int(50 + 30 * t), int(80 + 40 * t), int(140 - 40 * t))
            pygame.draw.line(panel, color, (0, y), (panel_w, y))

        pygame.draw.rect(panel, PALETTE['green'], (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Draw obstacles (pipes)
        for obs in self.flappy_game.obstacles:
            x, gap_y, gap_h = obs
            if -50 < x < panel_w + 50:
                pipe_x = int(x)
                gap_top = int(gap_y - gap_h / 2)
                gap_bottom = int(gap_y + gap_h / 2)
                # Top pipe
                pygame.draw.rect(panel, (50, 180, 80), (pipe_x - 25, 0, 50, gap_top))
                pygame.draw.rect(panel, (30, 140, 60), (pipe_x - 30, gap_top - 15, 60, 15))
                # Bottom pipe
                pygame.draw.rect(panel, (50, 180, 80), (pipe_x - 25, gap_bottom, 50, panel_h - gap_bottom))
                pygame.draw.rect(panel, (30, 140, 60), (pipe_x - 30, gap_bottom, 60, 15))

        # Draw coins
        for coin in self.flappy_game.coins:
            x, y, collected = coin
            if not collected and -20 < x < panel_w + 20:
                pygame.draw.circle(panel, PALETTE['gold'], (int(x), int(y)), 10)
                pygame.draw.circle(panel, (255, 230, 100), (int(x) - 2, int(y) - 2), 4)

        # Draw bird
        bird_x = 80
        bird_y = int(self.flappy_game.bird_y)
        # Body
        pygame.draw.circle(panel, PALETTE['gold'], (bird_x, bird_y), 16)
        pygame.draw.circle(panel, (255, 230, 100), (bird_x, bird_y), 16, 2)
        # Eye
        pygame.draw.circle(panel, (255, 255, 255), (bird_x + 6, bird_y - 4), 6)
        pygame.draw.circle(panel, (0, 0, 0), (bird_x + 7, bird_y - 4), 3)
        # Beak
        pygame.draw.polygon(panel, (255, 150, 50), [(bird_x + 14, bird_y), (bird_x + 26, bird_y + 2), (bird_x + 14, bird_y + 6)])
        # Wing
        wing_offset = int(math.sin(self.flappy_game.game_timer * 15) * 4)
        pygame.draw.ellipse(panel, (200, 160, 50), (bird_x - 12, bird_y - 2 + wing_offset, 16, 10))

        # UI
        timer_text = f"Time: {max(0, self.flappy_game.time_limit - self.flappy_game.game_timer):.1f}s"
        panel.blit(self.font_medium.render(timer_text, True, (255, 255, 255)), (15, 15))

        coins_text = f"Coins: {self.flappy_game.coins_collected}/{self.flappy_game.coins_needed}"
        panel.blit(self.font_medium.render(coins_text, True, PALETTE['gold']), (panel_w - 110, 15))

        # Grace period, instructions, or result
        if self.flappy_game.grace_period > 0 and not self.flappy_game.result:
            # Show "GET READY!" during grace period
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("GET READY!", True, PALETTE['gold'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 20)))
            hint_text = self.font_small.render("Press SPACE to flap and collect coins!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 20)))
        elif not self.flappy_game.result:
            instr = self.font_small.render("SPACE to flap! Collect coins!", True, (255, 255, 255))
            panel.blit(instr, instr.get_rect(centerx=panel_w // 2, bottom=panel_h - 10))
        else:
            # Dark overlay for results
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if self.flappy_game.result == "win":
                # Victory screen
                result_text = "SUCCESS!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render("You won a rare item!", True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                coins_final = self.font_small.render(f"Coins collected: {self.flappy_game.coins_collected}/{self.flappy_game.coins_needed}", True, PALETTE['gold'])
                panel.blit(coins_final, coins_final.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                # Loss screen
                result_text = "GAME OVER"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("No reward this time...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                coins_final = self.font_small.render(f"Coins collected: {self.flappy_game.coins_collected}/{self.flappy_game.coins_needed}", True, PALETTE['gray_light'])
                panel.blit(coins_final, coins_final.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_archery_minigame(self) -> None:
        """Draw the archery target shooting minigame."""
        import math

        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        game = self.archery_game

        # Background - outdoor range
        for y in range(panel_h):
            t = y / panel_h
            if t < 0.6:  # Sky
                color = (int(100 + 50 * t), int(150 + 30 * t), int(200 - 20 * t))
            else:  # Ground
                color = (int(80 + 20 * (t - 0.6)), int(120 + 30 * (t - 0.6)), int(60))
            pygame.draw.line(panel, color, (0, y), (panel_w, y))

        pygame.draw.rect(panel, (139, 90, 43), (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Draw target
        target_x = int(game.target_x)
        target_y = int(game.target_y)

        # Target stand
        pygame.draw.rect(panel, (100, 70, 40), (target_x - 5, target_y + 50, 10, 60))

        # Target rings (from outside in)
        for i, (radius, color) in enumerate([
            (50, (255, 255, 255)),   # White outer
            (40, (50, 50, 50)),      # Black
            (30, (100, 150, 255)),   # Blue
            (20, (255, 50, 50)),     # Red
            (12, (255, 215, 0)),     # Gold bullseye
        ]):
            pygame.draw.circle(panel, color, (target_x, target_y), radius)

        # Draw wind indicator if there's wind
        if abs(game.wind_strength) > 5:
            wind_text = f"Wind: {'↑' if game.wind_strength < 0 else '↓'} {abs(int(game.wind_strength))}"
            wind_color = (200, 200, 255) if game.wind_strength < 0 else (255, 200, 200)
            panel.blit(self.font_small.render(wind_text, True, wind_color), (panel_w - 100, 40))

        # Draw bow
        bow_x = 50
        bow_y = int(game.bow_y)
        angle_rad = math.radians(game.aim_angle)

        # Bow body (curved arc)
        bow_color = (139, 90, 43)  # Brown wood
        pygame.draw.arc(panel, bow_color, (bow_x - 20, bow_y - 40, 25, 80),
                       math.pi/2 - 0.5, math.pi/2 + 0.5, 4)

        # Bow string
        string_top = (bow_x - 8, bow_y - 35)
        string_bottom = (bow_x - 8, bow_y + 35)
        string_pull = (bow_x - 8 - int(game.power * 15), bow_y)
        pygame.draw.line(panel, (200, 200, 200), string_top, string_pull, 2)
        pygame.draw.line(panel, (200, 200, 200), string_pull, string_bottom, 2)

        # Arrow on bow (if not flying)
        if not game.arrow_flying and game.shots_taken < game.shots_allowed:
            arrow_start_x = bow_x - 5 - int(game.power * 15)
            arrow_start_y = bow_y
            arrow_len = 40
            arrow_end_x = arrow_start_x + int(arrow_len * math.cos(angle_rad))
            arrow_end_y = arrow_start_y + int(arrow_len * math.sin(angle_rad))

            # Arrow shaft
            pygame.draw.line(panel, (139, 90, 43), (arrow_start_x, arrow_start_y),
                           (arrow_end_x, arrow_end_y), 3)
            # Arrow head
            head_x = arrow_end_x + int(8 * math.cos(angle_rad))
            head_y = arrow_end_y + int(8 * math.sin(angle_rad))
            pygame.draw.polygon(panel, (150, 150, 150), [
                (arrow_end_x, arrow_end_y),
                (head_x, head_y),
                (arrow_end_x + int(5 * math.cos(angle_rad + 2.5)), arrow_end_y + int(5 * math.sin(angle_rad + 2.5))),
            ])

        # Draw flying arrow
        if game.arrow_flying:
            ax, ay = int(game.arrow_x), int(game.arrow_y)
            # Calculate arrow angle from velocity
            flight_angle = math.atan2(game.arrow_vy, game.arrow_vx)
            arrow_len = 35
            tail_x = ax - int(arrow_len * math.cos(flight_angle))
            tail_y = ay - int(arrow_len * math.sin(flight_angle))

            # Arrow shaft
            pygame.draw.line(panel, (139, 90, 43), (tail_x, tail_y), (ax, ay), 3)
            # Arrow head
            head_x = ax + int(8 * math.cos(flight_angle))
            head_y = ay + int(8 * math.sin(flight_angle))
            pygame.draw.polygon(panel, (150, 150, 150), [
                (ax, ay),
                (head_x, head_y),
                (ax + int(5 * math.cos(flight_angle + 2.5)), ay + int(5 * math.sin(flight_angle + 2.5))),
            ])
            # Fletching
            pygame.draw.line(panel, (200, 50, 50),
                           (tail_x, tail_y),
                           (tail_x - int(8 * math.cos(flight_angle - 0.5)), tail_y - int(8 * math.sin(flight_angle - 0.5))), 2)
            pygame.draw.line(panel, (200, 50, 50),
                           (tail_x, tail_y),
                           (tail_x - int(8 * math.cos(flight_angle + 0.5)), tail_y - int(8 * math.sin(flight_angle + 0.5))), 2)

        # Power meter
        meter_x, meter_y = 15, 80
        meter_w, meter_h = 15, 180
        pygame.draw.rect(panel, (50, 50, 50), (meter_x, meter_y, meter_w, meter_h), border_radius=4)
        pygame.draw.rect(panel, (100, 100, 100), (meter_x, meter_y, meter_w, meter_h), 2, border_radius=4)

        # Power fill
        fill_h = int(meter_h * game.power)
        fill_color = (100, 255, 100) if game.power < 0.7 else (255, 200, 50) if game.power < 0.9 else (255, 100, 100)
        if fill_h > 0:
            pygame.draw.rect(panel, fill_color, (meter_x + 2, meter_y + meter_h - fill_h, meter_w - 4, fill_h), border_radius=2)

        power_label = self.font_tiny.render("PWR", True, (200, 200, 200))
        panel.blit(power_label, (meter_x - 2, meter_y + meter_h + 5))

        # UI - Shots and bullseyes
        shots_text = f"Shots: {game.shots_allowed - game.shots_taken}"
        panel.blit(self.font_medium.render(shots_text, True, (255, 255, 255)), (15, 15))

        bullseye_text = f"Bullseyes: {game.bullseyes}/{game.bullseyes_needed}"
        bullseye_color = PALETTE['gold'] if game.bullseyes >= game.bullseyes_needed else (255, 255, 255)
        panel.blit(self.font_medium.render(bullseye_text, True, bullseye_color), (panel_w - 140, 15))

        score_text = f"Score: {game.score}"
        panel.blit(self.font_small.render(score_text, True, PALETTE['gold']), (panel_w // 2 - 30, 15))

        # Last hit feedback
        if game.last_hit_timer > 0 and game.last_hit_text:
            alpha = min(255, int(game.last_hit_timer * 255))
            hit_color = PALETTE['gold'] if "BULLSEYE" in game.last_hit_text else PALETTE['green'] if "GOOD" in game.last_hit_text else PALETTE['red'] if "MISS" in game.last_hit_text else (200, 200, 200)
            hit_surf = self.font_large.render(game.last_hit_text, True, hit_color)
            hit_surf.set_alpha(alpha)
            panel.blit(hit_surf, hit_surf.get_rect(centerx=panel_w // 2, y=panel_h // 2 - 60))

        # Grace period, instructions, or result
        if game.grace_period > 0 and not game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("GET READY!", True, PALETTE['gold'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 20)))
            hint_text = self.font_small.render("UP/DOWN to aim, SPACE to shoot!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 20)))
        elif not game.result:
            instr = self.font_small.render("UP/DOWN to aim, SPACE to shoot!", True, (255, 255, 255))
            panel.blit(instr, instr.get_rect(centerx=panel_w // 2, bottom=panel_h - 10))
        else:
            # Result overlay
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if game.result == "win":
                result_text = "VICTORY!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render("You won a rare item!", True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                score_final = self.font_small.render(f"Final Score: {game.score} | Bullseyes: {game.bullseyes}", True, PALETTE['gold'])
                panel.blit(score_final, score_final.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                result_text = "OUT OF ARROWS"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("No reward this time...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                score_final = self.font_small.render(f"Score: {game.score} | Bullseyes: {game.bullseyes}/{game.bullseyes_needed}", True, PALETTE['gray_light'])
                panel.blit(score_final, score_final.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_blacksmith_minigame(self) -> None:
        """Draw the blacksmith gamble minigame."""
        import math

        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        game = self.blacksmith_game

        # Background - forge/workshop
        for y in range(panel_h):
            t = y / panel_h
            color = (int(40 + 20 * t), int(30 + 15 * t), int(25 + 10 * t))
            pygame.draw.line(panel, color, (0, y), (panel_w, y))

        pygame.draw.rect(panel, (100, 60, 30), (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Draw anvil
        anvil_x, anvil_y = panel_w // 2, 220
        pygame.draw.rect(panel, (60, 60, 70), (anvil_x - 50, anvil_y, 100, 30), border_radius=3)  # Top
        pygame.draw.rect(panel, (50, 50, 60), (anvil_x - 35, anvil_y + 30, 70, 40))  # Base
        pygame.draw.rect(panel, (70, 70, 80), (anvil_x - 55, anvil_y - 5, 110, 10), border_radius=2)  # Rim

        # Draw hammer (animated during rolling)
        hammer_x = anvil_x + 80
        hammer_y = anvil_y - 40
        if game.is_rolling:
            # Hammer animation
            swing = math.sin(game.roll_timer * 15) * 30
            hammer_y += int(abs(swing))
            if abs(swing) < 5:  # Hitting sound moment
                # Add sparks
                if random.random() < 0.3:
                    self._add_particles(panel_x + anvil_x, panel_y + anvil_y - 10, (255, 200, 100), 3)

        # Hammer handle
        pygame.draw.line(panel, (100, 70, 40), (hammer_x, hammer_y + 40), (hammer_x, hammer_y), 6)
        # Hammer head
        pygame.draw.rect(panel, (80, 80, 90), (hammer_x - 15, hammer_y - 10, 30, 20), border_radius=3)

        # Draw sparks animation on anvil
        if game.is_rolling or (game.sparks_timer % 2 < 0.1):
            spark_count = 5 if game.is_rolling else 2
            for _ in range(spark_count):
                sx = anvil_x + random.randint(-30, 30)
                sy = anvil_y - 10 + random.randint(-20, 0)
                pygame.draw.circle(panel, (255, 200 + random.randint(0, 55), 50), (sx, sy), random.randint(1, 3))

        # Draw item being forged (centered above anvil)
        item_y = anvil_y - 50
        rarity_colors = [
            (180, 180, 180),  # Common - gray
            (100, 200, 100),  # Uncommon - green
            (100, 150, 255),  # Rare - blue
            (200, 100, 255),  # Epic - purple
            (255, 200, 50),   # Legendary - gold
        ]
        item_color = rarity_colors[min(game.current_rarity, 4)]
        rarity_name = game.rarity_names[min(game.current_rarity, 4)]

        # Item glow
        glow_size = 35 + int(math.sin(game.sparks_timer * 3) * 5)
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*item_color, 50), (glow_size, glow_size), glow_size)
        panel.blit(glow_surf, (anvil_x - glow_size, item_y - glow_size))

        # Item (sword shape)
        pygame.draw.rect(panel, item_color, (anvil_x - 5, item_y - 40, 10, 60), border_radius=2)  # Blade
        pygame.draw.rect(panel, (100, 70, 40), (anvil_x - 15, item_y + 15, 30, 8), border_radius=2)  # Guard
        pygame.draw.rect(panel, (80, 60, 40), (anvil_x - 4, item_y + 23, 8, 15))  # Handle

        # Rarity label
        rarity_text = self.font_medium.render(rarity_name, True, item_color)
        panel.blit(rarity_text, rarity_text.get_rect(centerx=panel_w // 2, y=item_y + 45))

        # Title
        title = self.font_large.render("BLACKSMITH'S GAMBLE", True, (255, 200, 100))
        panel.blit(title, title.get_rect(centerx=panel_w // 2, y=10))

        # Upgrade chances display
        chances_y = 300
        for i in range(3):
            chance = int(game.success_chances[i] * 100)
            if i < game.upgrade_level:
                # Already passed
                color = PALETTE['green']
                status = "DONE"
            elif i == game.upgrade_level:
                # Current attempt
                color = PALETTE['gold']
                status = f"{chance}%"
            else:
                # Future
                color = PALETTE['gray_light']
                status = f"{chance}%"

            x_pos = 80 + i * 130
            pygame.draw.rect(panel, color, (x_pos - 30, chances_y, 80, 25), border_radius=4)
            chance_text = self.font_small.render(status, True, (0, 0, 0))
            panel.blit(chance_text, chance_text.get_rect(centerx=x_pos + 10, centery=chances_y + 12))

        # Rolling animation overlay
        if game.is_rolling:
            # Pulsing overlay
            pulse = int(abs(math.sin(game.roll_timer * 8)) * 50)
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((255, 200, 100, pulse))
            panel.blit(overlay, (0, 0))

            forging_text = self.font_large.render("FORGING...", True, (255, 200, 100))
            panel.blit(forging_text, forging_text.get_rect(centerx=panel_w // 2, y=130))

        # Grace period, instructions, or result
        if game.grace_period > 0 and not game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("BLACKSMITH'S GAMBLE", True, PALETTE['gold'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 30)))
            hint1 = self.font_small.render("SPACE/UP = Upgrade (risk breaking)", True, (255, 255, 255))
            panel.blit(hint1, hint1.get_rect(center=(panel_w // 2, panel_h // 2 + 10)))
            hint2 = self.font_small.render("DOWN/ESC = Keep current item", True, (200, 200, 200))
            panel.blit(hint2, hint2.get_rect(center=(panel_w // 2, panel_h // 2 + 35)))
        elif not game.result and not game.is_rolling:
            instr1 = self.font_small.render("SPACE = Upgrade | DOWN = Keep", True, (200, 200, 200))
            panel.blit(instr1, instr1.get_rect(centerx=panel_w // 2, bottom=panel_h - 10))
        elif game.result:
            # Result overlay
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if game.result == "win":
                result_text = "FORGING COMPLETE!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                final_rarity = game.rarity_names[min(game.current_rarity, 4)]
                reward_text = self.font_medium.render(f"You forged a {final_rarity} item!", True, item_color)
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                upgrades_text = self.font_small.render(f"Upgrades completed: {game.upgrade_level}", True, PALETTE['gold'])
                panel.blit(upgrades_text, upgrades_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))
            else:
                result_text = "ITEM SHATTERED!"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render("The forge was too hot...", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                hint_text = self.font_small.render("No reward this time.", True, PALETTE['gray_light'])
                panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 30)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_boss_cinematic(self) -> None:
        """Draw the epic boss introduction cinematic."""
        import math
        cine = self.boss_cinematic

        # Create full screen overlay
        overlay = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)

        # Dark cinematic bars at top and bottom
        bar_height = 60
        pygame.draw.rect(overlay, (0, 0, 0, 255), (0, 0, self.WINDOW_WIDTH, bar_height))
        pygame.draw.rect(overlay, (0, 0, 0, 255), (0, self.WINDOW_HEIGHT - bar_height, self.WINDOW_WIDTH, bar_height))

        # Semi-transparent dark overlay on game area
        if cine.phase == "transition":
            # Full black during transition
            alpha = min(255, int(255 * (cine.timer / 0.5)))
            overlay.fill((0, 0, 0, alpha))
        else:
            pygame.draw.rect(overlay, (0, 0, 0, 100),
                           (0, bar_height, self.WINDOW_WIDTH, self.WINDOW_HEIGHT - bar_height * 2))

        # Screen flash effect
        if cine.screen_flash > 0:
            flash_alpha = int(200 * cine.screen_flash)
            flash = pygame.Surface((self.WINDOW_WIDTH, self.WINDOW_HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 255, 200, flash_alpha))
            overlay.blit(flash, (0, 0))

        # Calculate dragon position on screen
        # Board area is roughly left side of screen
        board_center_x = 30 + self.BOARD_SIZE // 2
        board_center_y = 150 + self.BOARD_SIZE // 2

        # Dragon position based on cinematic phase
        dragon_size = int(150 * cine.dragon_scale)
        dragon_x = int(board_center_x + (cine.dragon_x - 0.5) * self.BOARD_SIZE * 2) - dragon_size // 2
        dragon_y = board_center_y - dragon_size // 2

        # Only draw dragon if not in transition phase and on screen
        if cine.phase != "transition" and dragon_x < self.WINDOW_WIDTH + 100:
            # Get dragon sprite
            dragon_sprite = sprites.create_monster_sprite("dragon", dragon_size, is_boss=True)

            # Add screen shake to dragon position
            shake_x = int(random.uniform(-5, 5) * cine.screen_shake * 10) if cine.screen_shake > 0 else 0
            shake_y = int(random.uniform(-5, 5) * cine.screen_shake * 10) if cine.screen_shake > 0 else 0

            # Breathing/hovering animation
            hover_offset = int(math.sin(cine.timer * 3) * 8)

            overlay.blit(dragon_sprite, (dragon_x + shake_x, dragon_y + shake_y + hover_offset))

            # Draw fire particles during awaken phase
            if cine.phase == "awaken" and cine.timer > 0.5:
                for _ in range(3):
                    px = dragon_x + dragon_size // 2 + random.randint(-30, 30)
                    py = dragon_y + dragon_size // 2 + random.randint(-20, 20)
                    size = random.randint(3, 8)
                    color = random.choice([PALETTE['red'], PALETTE['gold'], (255, 150, 50)])
                    pygame.draw.circle(overlay, color, (px + shake_x, py + shake_y), size)

        # Draw speech bubble during speech phase
        if cine.phase == "speech" and cine.speech_text:
            bubble_w = 400
            bubble_h = 80
            bubble_x = self.WINDOW_WIDTH // 2 - bubble_w // 2
            bubble_y = self.WINDOW_HEIGHT - bar_height - bubble_h - 40

            # Speech bubble background
            pygame.draw.rect(overlay, (30, 30, 40, 240), (bubble_x, bubble_y, bubble_w, bubble_h), border_radius=10)
            pygame.draw.rect(overlay, PALETTE['gold'], (bubble_x, bubble_y, bubble_w, bubble_h), 3, border_radius=10)

            # Dragon name
            name_text = self.font_medium.render("Ancient Dragon", True, PALETTE['red'])
            overlay.blit(name_text, (bubble_x + 15, bubble_y + 10))

            # Speech text (typewriter effect)
            chars_shown = min(len(cine.speech_text), int(cine.timer * 30))
            displayed_text = cine.speech_text[:chars_shown]
            speech_surf = self.font_medium.render(displayed_text, True, (255, 255, 255))
            overlay.blit(speech_surf, (bubble_x + 15, bubble_y + 40))

        # Phase indicator text
        if cine.phase == "awaken":
            phase_text = "THE DRAGON AWAKENS!"
            text_color = PALETTE['red']
        elif cine.phase == "exit":
            phase_text = "PREPARE FOR BATTLE!"
            text_color = PALETTE['gold']
        else:
            phase_text = ""
            text_color = PALETTE['cream']

        if phase_text:
            # Pulsing text effect
            pulse = 1.0 + math.sin(cine.timer * 5) * 0.1
            text_surf = self.font_large.render(phase_text, True, text_color)
            text_rect = text_surf.get_rect(center=(self.WINDOW_WIDTH // 2, bar_height + 40))
            overlay.blit(text_surf, text_rect)

        self.screen.blit(overlay, (0, 0))

    def _draw_monster_minigame(self) -> None:
        """Draw the monster attack minigame - arrow sequence survival."""
        import math

        panel_w, panel_h = 450, 350
        panel_x = self.WINDOW_WIDTH - panel_w - 20
        panel_y = 170

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        game = self.monster_game

        # Ominous dark background
        for y in range(panel_h):
            t = y / panel_h
            color = (int(30 + 10 * t), int(15 + 10 * t), int(40 + 15 * t))
            pygame.draw.line(panel, color, (0, y), (panel_w, y))

        pygame.draw.rect(panel, PALETTE['red'], (0, 0, panel_w, panel_h), 3, border_radius=8)

        # Monster name title
        title = self.font_large.render(game.monster_name.upper(), True, PALETTE['red'])
        panel.blit(title, title.get_rect(centerx=panel_w // 2, y=10))

        # Round indicator
        round_text = f"Round {game.current_round} / {game.max_rounds}"
        round_surf = self.font_medium.render(round_text, True, PALETTE['gold'])
        panel.blit(round_surf, round_surf.get_rect(centerx=panel_w // 2, y=45))

        # Arrow display area
        arrow_area_y = 90
        arrow_size = 40
        arrow_colors = {
            "up": PALETTE['cyan'],
            "down": PALETTE['green'],
            "left": PALETTE['gold'],
            "right": PALETTE['purple'],
        }
        arrow_symbols = {"up": "^", "down": "v", "left": "<", "right": ">"}

        if game.grace_period > 0 and not game.result:
            # Grace period - GET READY
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            panel.blit(overlay, (0, 0))
            ready_text = self.font_large.render("INCOMING ATTACK!", True, PALETTE['red'])
            panel.blit(ready_text, ready_text.get_rect(center=(panel_w // 2, panel_h // 2 - 30)))
            attack_text = self.font_medium.render(f"{game.attack_name}!", True, PALETTE['gold'])
            panel.blit(attack_text, attack_text.get_rect(center=(panel_w // 2, panel_h // 2 + 10)))
            hint_text = self.font_small.render("Match the arrow sequence to survive!", True, (255, 255, 255))
            panel.blit(hint_text, hint_text.get_rect(center=(panel_w // 2, panel_h // 2 + 45)))

        elif not game.result:
            # Input phase - show sequence and player progress
            # Timer bar
            timer_w = panel_w - 80
            timer_h = 12
            timer_x = 40
            timer_y = arrow_area_y

            timer_pct = max(0, game.round_timer / game.round_time_limit)
            timer_color = PALETTE['green'] if timer_pct > 0.5 else PALETTE['gold'] if timer_pct > 0.25 else PALETTE['red']

            pygame.draw.rect(panel, (40, 40, 50), (timer_x, timer_y, timer_w, timer_h), border_radius=4)
            if timer_pct > 0:
                pygame.draw.rect(panel, timer_color, (timer_x, timer_y, int(timer_w * timer_pct), timer_h), border_radius=4)
            pygame.draw.rect(panel, PALETTE['gray_light'], (timer_x, timer_y, timer_w, timer_h), 1, border_radius=4)

            time_text = f"{game.round_timer:.1f}s"
            time_surf = self.font_small.render(time_text, True, timer_color)
            panel.blit(time_surf, time_surf.get_rect(right=timer_x + timer_w, y=timer_y - 18))

            # Draw sequence with player progress highlighted
            seq_label = self.font_medium.render("INPUT:", True, PALETTE['cyan'])
            panel.blit(seq_label, seq_label.get_rect(centerx=panel_w // 2, y=timer_y + 25))

            max_per_row = 10
            rows = (len(game.sequence) + max_per_row - 1) // max_per_row

            for row in range(rows):
                start_idx = row * max_per_row
                end_idx = min(start_idx + max_per_row, len(game.sequence))
                row_arrows = game.sequence[start_idx:end_idx]
                row_width = len(row_arrows) * (arrow_size + 5)
                start_x = (panel_w - row_width) // 2
                row_y = timer_y + 55 + row * (arrow_size + 10)

                for i, arrow in enumerate(row_arrows):
                    idx = start_idx + i
                    x = start_x + i * (arrow_size + 5)

                    # Color based on status
                    if idx < game.player_index:
                        # Completed
                        color = PALETTE['green']
                        alpha = 200
                    elif idx == game.player_index:
                        # Current - highlight
                        color = arrow_colors.get(arrow, PALETTE['gray'])
                        alpha = 255
                        # Pulsing border
                        pulse = 150 + int(abs(math.sin(game.round_timer * 8)) * 105)
                        pygame.draw.rect(panel, (pulse, pulse, pulse), (x - 2, row_y - 2, arrow_size + 4, arrow_size + 4), 2, border_radius=4)
                    else:
                        # Future
                        color = (50, 50, 60)
                        alpha = 120

                    # Flash on input
                    if idx == game.player_index and game.input_flash_timer > 0:
                        if game.last_input_correct:
                            color = (100, 255, 100)
                        else:
                            color = (255, 100, 100)

                    arrow_surf = pygame.Surface((arrow_size, arrow_size), pygame.SRCALPHA)
                    pygame.draw.rect(arrow_surf, (*color[:3], alpha), (0, 0, arrow_size, arrow_size), border_radius=4)
                    symbol = arrow_symbols.get(arrow, "?")
                    sym_surf = self.font_large.render(symbol, True, (255, 255, 255))
                    arrow_surf.blit(sym_surf, sym_surf.get_rect(center=(arrow_size // 2, arrow_size // 2)))
                    panel.blit(arrow_surf, (x, row_y))

            # Progress text
            progress_text = f"{game.player_index} / {len(game.sequence)}"
            prog_surf = self.font_medium.render(progress_text, True, PALETTE['gold'])
            panel.blit(prog_surf, prog_surf.get_rect(centerx=panel_w // 2, y=panel_h - 50))

            # Controls hint
            hint = self.font_small.render("Arrow keys or WASD to input!", True, PALETTE['gray_light'])
            panel.blit(hint, hint.get_rect(centerx=panel_w // 2, y=panel_h - 25))

        # Result overlay
        if game.result:
            overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            panel.blit(overlay, (0, 0))

            if game.result == "win":
                result_text = "SURVIVED!"
                result_color = PALETTE['gold']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                reward_text = self.font_medium.render("The creature retreats!", True, (255, 255, 255))
                panel.blit(reward_text, reward_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                heal_text = self.font_small.render("+10% HP healed! Item chance!", True, PALETTE['green'])
                panel.blit(heal_text, heal_text.get_rect(center=(panel_w // 2, panel_h // 2 + 35)))
            else:
                result_text = "OVERWHELMED!"
                result_color = PALETTE['red']
                result_surf = self.font_large.render(result_text, True, result_color)
                panel.blit(result_surf, result_surf.get_rect(center=(panel_w // 2, panel_h // 2 - 40)))

                fail_text = self.font_medium.render(f"{game.attack_name} hits you!", True, PALETTE['gray_light'])
                panel.blit(fail_text, fail_text.get_rect(center=(panel_w // 2, panel_h // 2)))

                damage_text = self.font_small.render("-30% Max HP damage!", True, PALETTE['red'])
                panel.blit(damage_text, damage_text.get_rect(center=(panel_w // 2, panel_h // 2 + 35)))

        self.screen.blit(panel, (panel_x, panel_y))

    def _draw_blessings_panel(self, surface: pygame.Surface) -> None:
        """Draw active blessings panel."""
        x, y, w, h = 560, 260, 240, 80

        panel = sprites.create_panel(w, h, "purple")
        surface.blit(panel, (x, y))

        title = self.font_medium.render("BLESSINGS", True, PALETTE['purple_light'])
        surface.blit(title, (x + 10, y + 5))

        # Clear blessing rects for hover detection
        self.blessing_rects.clear()

        player = self.game.get_player_data()
        if not player or not player.active_blessings:
            none_text = self.font_small.render("(none)", True, PALETTE['gray'])
            surface.blit(none_text, (x + 15, y + 28))
            return

        for i, blessing in enumerate(player.active_blessings[:3]):
            dur = "PERM" if blessing.is_permanent else f"({blessing.duration})"
            color = PALETTE['gold'] if blessing.is_permanent else PALETTE['cream']
            text = self.font_small.render(f"{blessing.name} {dur}", True, color)
            text_x, text_y = x + 15, y + 28 + i * 16
            surface.blit(text, (text_x, text_y))

            # Store rect for hover detection
            rect = pygame.Rect(text_x, text_y, w - 30, 16)
            self.blessing_rects.append((rect, blessing))

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

    def _draw_floating_texts(self) -> None:
        """Draw floating text effects."""
        for ft in self.floating_texts:
            alpha = int(255 * (ft['life'] / ft['max_life']))
            color = (*ft['color'][:3],)

            # Scale text based on remaining life (pop effect)
            scale = 1.0 + (1.0 - ft['life'] / ft['max_life']) * 0.3

            text_surf = self.font_large.render(ft['text'], True, color)
            if scale != 1.0:
                new_size = (int(text_surf.get_width() * scale), int(text_surf.get_height() * scale))
                text_surf = pygame.transform.smoothscale(text_surf, new_size)

            # Apply alpha
            text_surf.set_alpha(alpha)

            x = int(ft['x']) - text_surf.get_width() // 2
            y = int(ft['y']) - text_surf.get_height() // 2
            self.screen.blit(text_surf, (x, y))

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
        icon = sprites.create_item_icon(item.item_type, item.rarity, item.level, icon_size, item.theme, item.element)
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
                curr_icon = sprites.create_item_icon(current.item_type, current.rarity, current.level, 32, current.theme, current.element)
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
        diff_crit_mult = new_item.crit_multiplier_bonus - current_item.crit_multiplier_bonus
        diff_ls = new_item.life_steal_bonus - current_item.life_steal_bonus
        diff_dodge = new_item.dodge_bonus - current_item.dodge_bonus

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
        if abs(diff_crit_mult) > 0.01:
            sign = "+" if diff_crit_mult > 0 else ""
            changes.append((f"CDMG:{sign}{diff_crit_mult:.1f}x", get_color(diff_crit_mult)))
        if abs(diff_ls) > 0.001:
            sign = "+" if diff_ls > 0 else ""
            changes.append((f"LS:{sign}{diff_ls*100:.0f}%", get_color(diff_ls)))
        if abs(diff_dodge) > 0.001:
            sign = "+" if diff_dodge > 0 else ""
            changes.append((f"DOD:{sign}{diff_dodge*100:.0f}%", get_color(diff_dodge)))

        if not changes:
            return [("No stat change", PALETTE['gray'])]

        return changes[:6]  # Limit to 6 stats

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
                icon = sprites.create_item_icon(item.item_type, item.rarity, item.level, 24, item.theme, item.element)
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
        self.screen.blit(pot_label, (x + 30, y + 340))

        if merchant.has_potion:
            pot_text = self.font_small.render(f"[P] Health Potion - {merchant.potion_price}g", True, PALETTE['green'])
        else:
            pot_text = self.font_small.render("Sold out", True, PALETTE['gray'])
        self.screen.blit(pot_text, (x + 40, y + 365))

        # Reroll section
        reroll_color = PALETTE['gold'] if player and player.gold >= merchant.reroll_cost else PALETTE['gray']
        reroll_text = self.font_small.render(f"[R] Reroll Inventory - {merchant.reroll_cost}g", True, reroll_color)
        self.screen.blit(reroll_text, (x + 40, y + 395))

        # Exit - merchant travels when you leave
        exit_text = self.font_medium.render("[ESC] Leave (Merchant will travel)", True, PALETTE['gray'])
        self.screen.blit(exit_text, (x + w // 2 - 120, y + h - 40))

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
