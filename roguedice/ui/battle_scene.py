"""Pokemon-style battle scene with animations."""

import pygame
import math
import random
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, field
from enum import Enum

from .sprites import sprites, PALETTE
from ..systems.combat_system import CombatResult


class BattleSpeed(Enum):
    """Battle animation speed modes."""
    NORMAL = 1.0
    FAST = 2.0
    FASTER = 4.0
    INSTANT = 0.0  # No animation


@dataclass
class DamagePopup:
    """Floating damage number."""
    value: int
    x: float
    y: float
    timer: float = 0.0
    is_crit: bool = False
    is_heal: bool = False
    is_player: bool = True  # True = player did damage, False = monster did damage


@dataclass
class BattleAction:
    """A single action in the battle sequence."""
    action_type: str  # "player_attack", "monster_attack", "player_heal", "player_dodge", "monster_dodge"
    damage: int = 0
    is_crit: bool = False
    attacker_name: str = ""
    target_name: str = ""
    special_move: str = ""  # Boss special move name (e.g., "Fire Breath")
    special_anim: str = ""  # Animation type (e.g., "fire", "swipe", "roar")


class QTEDifficulty(Enum):
    """QTE difficulty settings."""
    OFF = 0
    EASY = 1
    NORMAL = 2
    HARD = 3


@dataclass
class QTEState:
    """Quick-Time Event state during combat."""
    active: bool = False
    qte_type: str = ""  # "block", "crit", "dodge"
    timer: float = 0.0
    duration: float = 1.5  # Time window to react
    bar_position: float = 0.0  # For timing bar (0-1)
    bar_direction: int = 1  # 1 = right, -1 = left
    bar_speed: float = 2.0  # Speed of timing bar
    sweet_spot_start: float = 0.4
    sweet_spot_end: float = 0.6
    required_key: str = ""  # Key to press for dodge
    result: Optional[str] = None  # "success", "fail", None
    damage_reduction: float = 0.0  # Damage reduction on success
    pending_damage: int = 0  # Damage to modify if QTE succeeds


@dataclass
class BattleState:
    """Current state of battle animation."""
    active: bool = False
    actions: List[BattleAction] = field(default_factory=list)
    current_action_index: int = 0
    action_timer: float = 0.0
    action_duration: float = 0.8

    # Monster entrance animation (for boss fights)
    monster_entrance: bool = False
    entrance_timer: float = 0.0
    entrance_duration: float = 1.5
    monster_entrance_x: float = -100  # Start off-screen left

    # Sprite shake states
    player_shake: float = 0.0
    monster_shake: float = 0.0

    # HP display (animated)
    displayed_player_hp: float = 0.0
    displayed_monster_hp: float = 0.0
    target_player_hp: float = 0.0
    target_monster_hp: float = 0.0

    # Flash effects
    player_flash: float = 0.0
    monster_flash: float = 0.0
    player_flash_color: tuple = (255, 100, 100)  # Default red, changes with special moves

    # Attack animation
    player_attack_anim: float = 0.0
    monster_attack_anim: float = 0.0

    # Popups
    damage_popups: List[DamagePopup] = field(default_factory=list)

    # Final result
    result: Optional[CombatResult] = None
    player_won: bool = False

    # Speed
    speed: BattleSpeed = BattleSpeed.NORMAL

    # QTE state
    qte: QTEState = field(default_factory=QTEState)
    qte_enabled: bool = True
    qte_difficulty: QTEDifficulty = QTEDifficulty.NORMAL

    def is_complete(self) -> bool:
        """Check if all actions have played."""
        return self.current_action_index >= len(self.actions) and self.action_timer <= 0


class BattleScene:
    """Manages Pokemon-style battle rendering and animation in a corner panel."""

    # Battle panel dimensions (rendered in top-right corner)
    PANEL_WIDTH = 450
    PANEL_HEIGHT = 350

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Panel position (top-right, below player stats)
        self.panel_x = screen_width - self.PANEL_WIDTH - 20
        self.panel_y = 170

        # Fonts (increased by 4px for readability)
        self.font_large = pygame.font.Font(None, 32)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 20)

        # Battle state
        self.state = BattleState()

        # Cached sprites
        self._player_sprite: Optional[pygame.Surface] = None
        self._monster_sprite: Optional[pygame.Surface] = None

        # Info
        self.player_char_id: str = "warrior"
        self.monster_type: str = "goblin"
        self.monster_name: str = "Goblin"
        self.is_boss: bool = False

        self.player_max_hp: int = 100
        self.monster_max_hp: int = 50

        # Speed mode
        self.speed_mode = BattleSpeed.NORMAL

        # Completion delay timer
        self._completion_timer: float = 0.0

        # QTE settings
        self.qte_difficulty = QTEDifficulty.NORMAL
        self.qte_enabled = True

    def start_battle(self, char_id: str, monster_type: str, monster_name: str,
                     is_boss: bool, combat_result: CombatResult,
                     player_max_hp: int, monster_max_hp: int,
                     player_start_hp: int, monster_start_hp: int,
                     monster_entrance: bool = False) -> None:
        """Start a new battle animation sequence."""
        self.player_char_id = char_id
        self.monster_type = monster_type
        self.monster_name = monster_name
        self.is_boss = is_boss
        self.player_max_hp = player_max_hp
        self.monster_max_hp = monster_max_hp

        # Reset completion timer
        self._completion_timer = 0.0

        # Generate sprites (smaller for panel view)
        self._player_sprite = sprites.create_battle_character(char_id, 80)
        self._monster_sprite = sprites.create_monster_sprite(monster_type, 80, is_boss)

        # Parse combat log into actions
        actions = self._parse_combat_log(combat_result.log)

        self.state = BattleState(
            active=True,
            actions=actions,
            current_action_index=0,
            action_timer=0.0,
            monster_entrance=monster_entrance,
            entrance_timer=0.0,
            entrance_duration=1.5 if monster_entrance else 0.0,
            monster_entrance_x=-100 if monster_entrance else 0,
            displayed_player_hp=player_start_hp,
            displayed_monster_hp=monster_start_hp,
            target_player_hp=player_start_hp,
            target_monster_hp=monster_start_hp,
            result=combat_result,
            player_won=combat_result.victory,
            speed=self.speed_mode,
        )

    def _parse_combat_log(self, log: List[str]) -> List[BattleAction]:
        """Parse combat log strings into battle actions."""
        import re
        actions = []

        for line in log:
            line_lower = line.lower()

            # Match player dealing damage - format: "[0.1s] You deal 15 damage!"
            if "you deal" in line_lower and "damage" in line_lower:
                damage = 0
                is_crit = "crit" in line_lower or "critical" in line_lower
                match = re.search(r'deals?\s+(\d+)\s+damage', line_lower)
                if match:
                    damage = int(match.group(1))
                if damage > 0:
                    actions.append(BattleAction(
                        action_type="player_attack",
                        damage=damage,
                        is_crit=is_crit,
                    ))

            # Match enemy dealing damage - format: "[0.2s] Enemy deals 8 damage!" or "[0.2s] Enemy uses Fire Breath! 50 damage!"
            elif ("enemy deal" in line_lower or "enemy uses" in line_lower) and "damage" in line_lower:
                damage = 0
                is_crit = "crit" in line_lower or "critical" in line_lower
                special_move = ""
                special_anim = ""

                # Extract special move name from "Enemy uses X!" format (use original case)
                move_match = re.search(r'[Ee]nemy uses ([^!]+)!', line)
                if move_match:
                    special_move = move_match.group(1).strip()
                    # Determine animation type based on move name
                    move_lower = special_move.lower()
                    if "fire" in move_lower or "breath" in move_lower:
                        special_anim = "fire"
                    elif "tail" in move_lower or "swipe" in move_lower or "slash" in move_lower or "claw" in move_lower:
                        special_anim = "slash"
                    elif "roar" in move_lower:
                        special_anim = "roar"
                    elif "wind" in move_lower or "gust" in move_lower or "wing" in move_lower:
                        special_anim = "wind"
                    else:
                        special_anim = "attack"

                # Try multiple patterns for damage extraction
                match = re.search(r'deals?\s+(\d+)\s+damage', line_lower)
                if not match:
                    # Boss special move format: "Enemy uses Fire Breath! 50 damage!"
                    match = re.search(r'!\s*(\d+)\s+damage', line_lower)
                if not match:
                    # Fallback: find any number followed by "damage"
                    match = re.search(r'(\d+)\s+damage', line_lower)
                if match:
                    damage = int(match.group(1))
                # Always add monster attacks, even if 0 damage (dodge/block)
                actions.append(BattleAction(
                    action_type="monster_attack",
                    damage=damage,
                    is_crit=is_crit,
                    special_move=special_move,
                    special_anim=special_anim,
                ))

            # Match bonus player damage - burn, steam burst, mana burst, gust, cleave
            # Format: "[Burn] Enemy takes X fire damage!" or "+X damage!" or "for X damage!"
            elif any(keyword in line_lower for keyword in ["[burn]", "[steampunk]", "[mana burst]", "[wind]", "[cleave]"]):
                # These are all player damage to enemy
                damage = 0
                # Try multiple patterns
                match = re.search(r'takes\s+(\d+)', line_lower)
                if not match:
                    match = re.search(r'\+(\d+)\s+damage', line_lower)
                if not match:
                    match = re.search(r'for\s+(\d+)\s+damage', line_lower)
                if not match:
                    match = re.search(r'\+(\d+)', line_lower)
                if match:
                    damage = int(match.group(1))
                if damage > 0:
                    actions.append(BattleAction(
                        action_type="player_attack",
                        damage=damage,
                        is_crit=False,
                    ))

            # Life steal healing
            elif "life steal" in line_lower:
                match = re.search(r'\+(\d+)\s*hp', line_lower)
                if match:
                    heal_amount = int(match.group(1))
                    actions.append(BattleAction(
                        action_type="player_heal",
                        damage=heal_amount,
                    ))

            # Other healing
            elif "heals" in line_lower or "restored" in line_lower:
                numbers = re.findall(r'\d+', line)
                if numbers:
                    damage = int(numbers[-1])
                    actions.append(BattleAction(
                        action_type="player_heal",
                        damage=damage,
                    ))

            # Dodge/miss (damage = 0 in combat means dodge)
            elif "dodges" in line_lower or "misses" in line_lower or "deal 0 damage" in line_lower:
                if "you" in line_lower:
                    actions.append(BattleAction(action_type="monster_dodge"))  # Monster attack missed
                else:
                    actions.append(BattleAction(action_type="player_dodge"))  # Player attack missed

            # Monster CC'd (paralyzed/flinched) - shows monster tried to attack
            elif "[paralyzed]" in line_lower or "[flinched]" in line_lower:
                if "enemy" in line_lower:
                    actions.append(BattleAction(
                        action_type="monster_attack",
                        damage=0,
                        is_crit=False,
                    ))

        return actions

    def update(self, dt: float) -> None:
        """Update battle animation state."""
        if not self.state.active:
            return

        # Speed multiplier
        speed_mult = self.state.speed.value if self.state.speed != BattleSpeed.INSTANT else 100.0

        # Handle monster entrance animation first
        if self.state.monster_entrance:
            self.state.entrance_timer += dt
            progress = min(1.0, self.state.entrance_timer / self.state.entrance_duration)
            # Ease out cubic for smooth deceleration
            eased = 1 - (1 - progress) ** 3
            # Move from -100 to final position (0)
            self.state.monster_entrance_x = -100 + eased * 100

            if progress >= 1.0:
                self.state.monster_entrance = False
                self.state.monster_entrance_x = 0
            return  # Don't process combat during entrance

        # Update QTE if active (pauses combat action processing)
        if self.state.qte.active:
            self._update_qte(dt)
            return

        # Update action timer
        self.state.action_timer += dt * speed_mult

        # Process current action
        if self.state.current_action_index < len(self.state.actions):
            action = self.state.actions[self.state.current_action_index]

            # Trigger action effects at start of each action
            if self.state.action_timer < dt * speed_mult * 2:
                self._trigger_action(action)

            # Move to next action when timer exceeds duration
            if self.state.action_timer >= self.state.action_duration:
                self.state.action_timer = 0.0
                self.state.current_action_index += 1
        else:
            # All actions complete - ensure final HP matches combat result
            # If player won, monster HP should be 0; if player lost, player HP should be 0
            if self.state.player_won and self.state.target_monster_hp > 0:
                self.state.target_monster_hp = 0
            elif not self.state.player_won and self.state.target_player_hp > 0:
                self.state.target_player_hp = 0

            # Wait for HP bars to finish animating
            hp_still_animating = (
                abs(self.state.displayed_player_hp - self.state.target_player_hp) > 1 or
                abs(self.state.displayed_monster_hp - self.state.target_monster_hp) > 1
            )
            if not hp_still_animating:
                # Snap to exact target values
                self.state.displayed_player_hp = self.state.target_player_hp
                self.state.displayed_monster_hp = self.state.target_monster_hp
                # HP bars done animating, now run completion timer
                self._completion_timer += dt * speed_mult

        # Update shake effects
        self.state.player_shake = max(0, self.state.player_shake - dt * 10)
        self.state.monster_shake = max(0, self.state.monster_shake - dt * 10)

        # Update flash effects
        self.state.player_flash = max(0, self.state.player_flash - dt * 5)
        self.state.monster_flash = max(0, self.state.monster_flash - dt * 5)

        # Update attack animations
        self.state.player_attack_anim = max(0, self.state.player_attack_anim - dt * 8)
        self.state.monster_attack_anim = max(0, self.state.monster_attack_anim - dt * 8)

        # Smoothly animate HP bars (slower so player can see HP drain to 0)
        hp_speed = 50 * speed_mult  # Slower HP drain
        if self.state.displayed_player_hp != self.state.target_player_hp:
            diff = self.state.target_player_hp - self.state.displayed_player_hp
            self.state.displayed_player_hp += min(abs(diff), hp_speed * dt) * (1 if diff > 0 else -1)
        if self.state.displayed_monster_hp != self.state.target_monster_hp:
            diff = self.state.target_monster_hp - self.state.displayed_monster_hp
            self.state.displayed_monster_hp += min(abs(diff), hp_speed * dt) * (1 if diff > 0 else -1)

        # Update damage popups
        for popup in self.state.damage_popups[:]:
            popup.timer += dt * speed_mult
            popup.y -= 30 * dt * speed_mult
            if popup.timer > 1.5:
                self.state.damage_popups.remove(popup)

    def _trigger_action(self, action: BattleAction) -> None:
        """Trigger visual effects for an action."""
        # Positions relative to panel
        monster_x = self.PANEL_WIDTH - 100
        monster_y = 80
        player_x = 80
        player_y = 200

        if action.action_type == "player_attack":
            self.state.player_attack_anim = 1.0
            self.state.monster_shake = 1.0
            self.state.monster_flash = 1.0
            self.state.target_monster_hp = max(0, self.state.target_monster_hp - action.damage)

            # Add damage popup on monster (panel-relative)
            self.state.damage_popups.append(DamagePopup(
                value=action.damage,
                x=monster_x,
                y=monster_y,
                is_crit=action.is_crit,
                is_player=True,
            ))

        elif action.action_type == "monster_attack":
            # Try to trigger QTE for this attack (only for damaging attacks)
            if action.damage > 0 and self._maybe_trigger_qte(action):
                # QTE triggered - pause here and wait for input
                return

            self.state.monster_attack_anim = 1.0
            if action.damage > 0:
                # Shake intensity and flash color based on special move
                if action.special_anim == "fire":
                    self.state.player_shake = 1.5  # Fire breath is intense
                    self.state.player_flash_color = (255, 120, 50)  # Orange/fire
                elif action.special_anim == "wind":
                    self.state.player_shake = 0.8
                    self.state.player_flash_color = (150, 255, 150)  # Green/wind
                elif action.special_anim == "roar":
                    self.state.player_shake = 0.5  # Roar is more stagger
                    self.state.player_flash_color = (200, 150, 255)  # Purple/sonic
                elif action.special_anim == "slash":
                    self.state.player_shake = 1.2
                    self.state.player_flash_color = (255, 100, 100)  # Red/physical
                else:
                    self.state.player_shake = 1.0
                    self.state.player_flash_color = (255, 100, 100)  # Default red
                self.state.player_flash = 1.0
            self.state.target_player_hp = max(0, self.state.target_player_hp - action.damage)

            # Add damage popup on player (panel-relative) - skip for 0 damage (CC'd/dodged)
            if action.damage > 0:
                self.state.damage_popups.append(DamagePopup(
                    value=action.damage,
                    x=player_x,
                    y=player_y,
                    is_crit=action.is_crit,
                    is_player=False,
                ))

        elif action.action_type == "player_heal":
            self.state.target_player_hp = min(self.player_max_hp,
                                              self.state.target_player_hp + action.damage)
            self.state.damage_popups.append(DamagePopup(
                value=action.damage,
                x=player_x,
                y=player_y,
                is_heal=True,
            ))

        elif action.action_type == "player_dodge":
            # Player dodged - no damage
            pass

        elif action.action_type == "monster_dodge":
            # Monster dodged
            pass

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the battle scene in a panel."""
        if not self.state.active:
            return

        # Create panel surface
        panel = pygame.Surface((self.PANEL_WIDTH, self.PANEL_HEIGHT), pygame.SRCALPHA)

        # Battle background on panel
        self._draw_background(panel)

        # Draw combatants on panel
        self._draw_player(panel)
        self._draw_monster(panel)

        # Draw HP bars on panel
        self._draw_hp_bars(panel)

        # Draw damage popups on panel
        self._draw_popups(panel)

        # Draw battle text on panel
        self._draw_battle_text(panel)

        # Draw speed indicator on panel
        self._draw_speed_indicator(panel)

        # Draw QTE if active or showing result
        if self.state.qte.active or self.state.qte.result:
            self._draw_qte(panel)

        # Draw result if battle complete
        if self.is_complete():
            self._draw_result(panel)

        # Draw panel border
        pygame.draw.rect(panel, PALETTE['gold'], (0, 0, self.PANEL_WIDTH, self.PANEL_HEIGHT), 3, border_radius=8)

        # Blit panel to main surface
        surface.blit(panel, (self.panel_x, self.panel_y))

    def _draw_background(self, surface: pygame.Surface) -> None:
        """Draw battle arena background on panel."""
        w, h = self.PANEL_WIDTH, self.PANEL_HEIGHT

        # Gradient sky
        ground_y = int(h * 0.55)
        for y in range(ground_y):
            t = y / ground_y
            r = int(30 + t * 25)
            g = int(40 + t * 30)
            b = int(60 + t * 40)
            pygame.draw.line(surface, (r, g, b), (0, y), (w, y))

        # Ground
        pygame.draw.rect(surface, (50, 70, 50), (0, ground_y, w, h - ground_y))

        # Grid pattern on ground (simplified)
        for x in range(0, w, 30):
            pygame.draw.line(surface, (40, 60, 40), (x, ground_y), (x + 50, h), 1)

        # Platform shadows
        pygame.draw.ellipse(surface, (35, 55, 35), (20, h - 80, 100, 25))
        pygame.draw.ellipse(surface, (35, 55, 35), (w - 140, ground_y + 20, 100, 25))

    def _draw_player(self, surface: pygame.Surface) -> None:
        """Draw player character on panel (bottom-left)."""
        if not self._player_sprite:
            return

        # Base position (panel-relative, bottom-left)
        x, y = 60, self.PANEL_HEIGHT - 100

        # Apply shake
        if self.state.player_shake > 0:
            x += random.randint(-4, 4)
            y += random.randint(-2, 2)

        # Apply attack animation (lunge forward)
        if self.state.player_attack_anim > 0:
            x += int(20 * self.state.player_attack_anim)

        # Draw sprite
        sprite = self._player_sprite.copy()

        # Flash effect (damage taken) - color varies by special move type
        if self.state.player_flash > 0:
            flash_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            r, g, b = self.state.player_flash_color
            flash_surf.fill((r, g, b, int(150 * self.state.player_flash)))
            sprite.blit(flash_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        surface.blit(sprite, (x - 40, y - 60))

    def _draw_monster(self, surface: pygame.Surface) -> None:
        """Draw monster on panel (top-right)."""
        if not self._monster_sprite:
            return

        # Base position (panel-relative, top-right)
        x, y = self.PANEL_WIDTH - 100, 100

        # Apply entrance animation offset (monster enters from left)
        if self.state.monster_entrance:
            x += int(self.state.monster_entrance_x)

        # Apply shake
        if self.state.monster_shake > 0:
            x += random.randint(-4, 4)
            y += random.randint(-2, 2)

        # Apply attack animation (lunge toward player)
        if self.state.monster_attack_anim > 0:
            x -= int(20 * self.state.monster_attack_anim)

        # Draw sprite
        sprite = self._monster_sprite.copy()

        # Flash effect
        if self.state.monster_flash > 0:
            flash_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            flash_surf.fill((255, 100, 100, int(150 * self.state.monster_flash)))
            sprite.blit(flash_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Flip sprite to face player
        sprite = pygame.transform.flip(sprite, True, False)

        surface.blit(sprite, (x - 40, y - 40))

    def _draw_hp_bars(self, surface: pygame.Surface) -> None:
        """Draw HP bars for both combatants on panel."""
        w = self.PANEL_WIDTH

        # Player HP bar (bottom of panel)
        from ..models.characters import get_character
        char = get_character(self.player_char_id)

        hp_pct = max(0, self.state.displayed_player_hp / self.player_max_hp)
        hp_bar = sprites.create_health_bar(120, 12, hp_pct)
        surface.blit(hp_bar, (10, self.PANEL_HEIGHT - 35))

        hp_text = self.font_small.render(f"{char.name}: {int(self.state.displayed_player_hp)}/{self.player_max_hp}",
                                         True, PALETTE['gold'])
        surface.blit(hp_text, (10, self.PANEL_HEIGHT - 50))

        # Monster HP bar (top of panel)
        name_color = PALETTE['red'] if self.is_boss else PALETTE['cream']
        name_prefix = "BOSS: " if self.is_boss else ""
        monster_text = self.font_small.render(f"{name_prefix}{self.monster_name}", True, name_color)
        surface.blit(monster_text, (w - 150, 8))

        monster_hp_pct = max(0, self.state.displayed_monster_hp / self.monster_max_hp)
        monster_bar = sprites.create_health_bar(120, 12, monster_hp_pct)
        surface.blit(monster_bar, (w - 135, 25))

        monster_hp_text = self.font_small.render(
            f"{int(self.state.displayed_monster_hp)}/{self.monster_max_hp}",
            True, PALETTE['white'])
        surface.blit(monster_hp_text, (w - 100, 40))

    def _draw_popups(self, surface: pygame.Surface) -> None:
        """Draw floating damage numbers on panel."""
        for popup in self.state.damage_popups:
            # Calculate alpha and scale
            alpha = max(0, 1.0 - popup.timer / 1.5)
            scale = 1.0 + popup.timer * 0.2

            # Create damage number sprite (smaller for panel)
            size = int(20 * scale) if popup.is_crit else int(16 * scale)
            dmg_sprite = sprites.create_damage_number(popup.value, popup.is_crit, popup.is_heal, size)

            # Apply alpha
            dmg_sprite.set_alpha(int(255 * alpha))

            # Draw (coordinates are panel-relative)
            surface.blit(dmg_sprite, (int(popup.x), int(popup.y)))

    def _draw_battle_text(self, surface: pygame.Surface) -> None:
        """Draw current action text on panel."""
        if self.state.current_action_index < len(self.state.actions):
            action = self.state.actions[self.state.current_action_index]

            text = ""
            if action.action_type == "player_attack":
                text = f"You deal {action.damage} dmg!"
                if action.is_crit:
                    text = f"CRIT! {action.damage} dmg!"
            elif action.action_type == "monster_attack":
                if action.damage > 0:
                    if action.special_move:
                        text = f"{action.special_move}! {action.damage} dmg!"
                    else:
                        text = f"{self.monster_name}: {action.damage} dmg!"
                else:
                    text = f"{self.monster_name} is stunned!"
            elif action.action_type == "player_heal":
                text = f"Heal +{action.damage}!"
            elif action.action_type == "player_dodge":
                text = "Dodged!"
            elif action.action_type == "monster_dodge":
                text = f"{self.monster_name} dodges!"

            if text:
                # Text at bottom of panel
                action_text = self.font_medium.render(text, True, PALETTE['cream'])
                # Center horizontally
                text_x = (self.PANEL_WIDTH - action_text.get_width()) // 2
                surface.blit(action_text, (text_x, self.PANEL_HEIGHT - 18))

    def _draw_speed_indicator(self, surface: pygame.Surface) -> None:
        """Draw speed selection as radio-button style controls on panel."""
        speeds = [
            (BattleSpeed.NORMAL, "1x", "1"),
            (BattleSpeed.FAST, "2x", "2"),
            (BattleSpeed.FASTER, "4x", "3"),
            (BattleSpeed.INSTANT, "Skip", "4"),
        ]

        # Draw speed label
        label = self.font_small.render("Speed:", True, PALETTE['gray'])
        surface.blit(label, (8, 6))

        # Draw radio buttons
        btn_x = 55
        btn_y = 4
        btn_w = 38
        btn_h = 18

        for speed_enum, name, key in speeds:
            is_selected = self.state.speed == speed_enum

            # Button background
            if is_selected:
                pygame.draw.rect(surface, PALETTE['gold'], (btn_x, btn_y, btn_w, btn_h), border_radius=3)
                text_color = PALETTE['black']
            else:
                pygame.draw.rect(surface, (50, 50, 60), (btn_x, btn_y, btn_w, btn_h), border_radius=3)
                pygame.draw.rect(surface, PALETTE['gray'], (btn_x, btn_y, btn_w, btn_h), 1, border_radius=3)
                text_color = PALETTE['cream']

            # Button text
            btn_text = self.font_small.render(name, True, text_color)
            text_x = btn_x + (btn_w - btn_text.get_width()) // 2
            text_y = btn_y + (btn_h - btn_text.get_height()) // 2
            surface.blit(btn_text, (text_x, text_y))

            btn_x += btn_w + 4

        # Key hints below
        hint = self.font_small.render("[1] [2] [3] [4]", True, (80, 80, 90))
        surface.blit(hint, (55, 24))

    def _draw_result(self, surface: pygame.Surface) -> None:
        """Draw battle result overlay on panel."""
        w, h = self.PANEL_WIDTH, self.PANEL_HEIGHT

        # Semi-transparent overlay
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))

        # Result text
        if self.state.player_won:
            result_text = "VICTORY!"
            color = PALETTE['gold']
        else:
            result_text = "DEFEATED"
            color = PALETTE['red']

        text = self.font_large.render(result_text, True, color)
        text_rect = text.get_rect(center=(w // 2, h // 2 - 20))
        surface.blit(text, text_rect)

        # Continue prompt
        continue_text = self.font_small.render("[SPACE] Continue", True, PALETTE['cream'])
        continue_rect = continue_text.get_rect(center=(w // 2, h // 2 + 20))
        surface.blit(continue_text, continue_rect)

    def set_speed(self, speed: BattleSpeed) -> None:
        """Set animation speed."""
        self.speed_mode = speed
        self.state.speed = speed

    def skip_to_end(self) -> None:
        """Skip remaining animations."""
        self.state.current_action_index = len(self.state.actions)
        self.state.action_timer = 0
        self.state.displayed_player_hp = self.state.target_player_hp
        self.state.displayed_monster_hp = self.state.target_monster_hp
        self.state.damage_popups.clear()
        self._completion_timer = 0.5  # Small delay before showing result

    def is_active(self) -> bool:
        """Check if battle scene is active."""
        return self.state.active

    def is_complete(self) -> bool:
        """Check if battle is complete and ready to dismiss."""
        # Battle is complete when all actions done, HP animated, and completion timer elapsed
        hp_done = (
            abs(self.state.displayed_player_hp - self.state.target_player_hp) <= 1 and
            abs(self.state.displayed_monster_hp - self.state.target_monster_hp) <= 1
        )
        return (self.state.current_action_index >= len(self.state.actions)
                and hp_done
                and self._completion_timer >= 1.2  # 1.2 seconds to see HP at 0
                and not self.state.qte.active)  # Wait for QTE to finish

    # =========================================================================
    # QTE (Quick-Time Event) System
    # =========================================================================

    def set_qte_difficulty(self, difficulty: QTEDifficulty) -> None:
        """Set QTE difficulty level."""
        self.qte_difficulty = difficulty
        self.qte_enabled = difficulty != QTEDifficulty.OFF

    def _maybe_trigger_qte(self, action: BattleAction) -> bool:
        """Maybe trigger a QTE for an incoming monster attack."""
        if not self.qte_enabled or self.qte_difficulty == QTEDifficulty.OFF:
            return False

        # Only trigger QTE for monster attacks
        if action.action_type != "monster_attack" or action.damage <= 0:
            return False

        # Random chance based on difficulty
        import random
        trigger_chance = {
            QTEDifficulty.EASY: 0.2,
            QTEDifficulty.NORMAL: 0.35,
            QTEDifficulty.HARD: 0.5,
        }
        if random.random() > trigger_chance.get(self.qte_difficulty, 0.35):
            return False

        # Choose QTE type
        qte_types = ["block", "dodge"]
        qte_type = random.choice(qte_types)

        # Configure QTE based on difficulty
        speed = {
            QTEDifficulty.EASY: 1.5,
            QTEDifficulty.NORMAL: 2.5,
            QTEDifficulty.HARD: 4.0,
        }
        sweet_spot = {
            QTEDifficulty.EASY: (0.35, 0.65),
            QTEDifficulty.NORMAL: (0.4, 0.6),
            QTEDifficulty.HARD: (0.45, 0.55),
        }
        ss = sweet_spot.get(self.qte_difficulty, (0.4, 0.6))

        # Dodge uses arrow keys
        dodge_keys = ["LEFT", "RIGHT", "UP", "DOWN"]
        required_key = random.choice(dodge_keys) if qte_type == "dodge" else "SPACE"

        self.state.qte = QTEState(
            active=True,
            qte_type=qte_type,
            timer=0.0,
            duration=1.5,
            bar_position=0.0,
            bar_direction=1,
            bar_speed=speed.get(self.qte_difficulty, 2.5),
            sweet_spot_start=ss[0],
            sweet_spot_end=ss[1],
            required_key=required_key,
            result=None,
            damage_reduction=0.5 if qte_type == "block" else 1.0,  # Block = 50%, Dodge = 100%
            pending_damage=action.damage,
        )
        return True

    def handle_qte_input(self, key: int) -> Optional[str]:
        """Handle input during QTE. Returns result if QTE ended."""
        if not self.state.qte.active:
            return None

        import pygame
        qte = self.state.qte

        success = False
        if qte.qte_type == "block":
            # Block QTE - press SPACE in sweet spot
            if key == pygame.K_SPACE:
                if qte.sweet_spot_start <= qte.bar_position <= qte.sweet_spot_end:
                    success = True
                qte.result = "success" if success else "fail"
                qte.active = False

        elif qte.qte_type == "dodge":
            # Dodge QTE - press correct arrow key
            key_map = {
                pygame.K_LEFT: "LEFT",
                pygame.K_RIGHT: "RIGHT",
                pygame.K_UP: "UP",
                pygame.K_DOWN: "DOWN",
            }
            pressed_key = key_map.get(key, "")
            if pressed_key:
                if pressed_key == qte.required_key:
                    success = True
                qte.result = "success" if success else "fail"
                qte.active = False

        if qte.result:
            return qte.result
        return None

    def _update_qte(self, dt: float) -> None:
        """Update QTE state."""
        qte = self.state.qte
        if not qte.active:
            return

        qte.timer += dt

        # Update timing bar position
        qte.bar_position += qte.bar_direction * qte.bar_speed * dt
        if qte.bar_position >= 1.0:
            qte.bar_position = 1.0
            qte.bar_direction = -1
        elif qte.bar_position <= 0.0:
            qte.bar_position = 0.0
            qte.bar_direction = 1

        # Timeout - fail the QTE
        if qte.timer >= qte.duration:
            qte.result = "fail"
            qte.active = False

    def _draw_qte(self, surface: pygame.Surface) -> None:
        """Draw QTE overlay on battle panel."""
        qte = self.state.qte
        if not qte.active and not qte.result:
            return

        w, h = self.PANEL_WIDTH, self.PANEL_HEIGHT

        # Semi-transparent overlay
        if qte.active:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 100))
            surface.blit(overlay, (0, 0))

        if qte.active:
            # QTE prompt
            if qte.qte_type == "block":
                title = "BLOCK! Press SPACE!"
                title_color = PALETTE['cyan']
            else:
                title = f"DODGE! Press [{qte.required_key}]!"
                title_color = PALETTE['green']

            title_text = self.font_large.render(title, True, title_color)
            surface.blit(title_text, (w // 2 - title_text.get_width() // 2, 80))

            # Timing bar (for block)
            if qte.qte_type == "block":
                bar_x, bar_y = 50, 130
                bar_w, bar_h = w - 100, 30

                # Bar background
                pygame.draw.rect(surface, (40, 40, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=5)

                # Sweet spot
                ss_x = bar_x + int(qte.sweet_spot_start * bar_w)
                ss_w = int((qte.sweet_spot_end - qte.sweet_spot_start) * bar_w)
                pygame.draw.rect(surface, (60, 180, 60), (ss_x, bar_y, ss_w, bar_h), border_radius=5)

                # Indicator
                ind_x = bar_x + int(qte.bar_position * bar_w)
                pygame.draw.rect(surface, PALETTE['gold'], (ind_x - 3, bar_y - 5, 6, bar_h + 10), border_radius=2)

            # Timer bar
            time_left = max(0, qte.duration - qte.timer)
            timer_w = int((time_left / qte.duration) * (w - 100))
            pygame.draw.rect(surface, (200, 50, 50), (50, 170, timer_w, 8), border_radius=3)

        # Result flash
        elif qte.result:
            result_text = "BLOCKED!" if qte.result == "success" and qte.qte_type == "block" else (
                "DODGED!" if qte.result == "success" else "MISSED!"
            )
            result_color = PALETTE['green'] if qte.result == "success" else PALETTE['red']
            text = self.font_large.render(result_text, True, result_color)
            surface.blit(text, (w // 2 - text.get_width() // 2, 100))

    def get_qte_damage_modifier(self) -> float:
        """Get damage modifier from QTE result (1.0 = full damage, 0.0 = no damage)."""
        qte = self.state.qte
        if qte.result == "success":
            return 1.0 - qte.damage_reduction
        return 1.0

    def clear_qte(self) -> None:
        """Clear QTE state after processing."""
        self.state.qte = QTEState()

    def dismiss(self) -> None:
        """Dismiss the battle scene."""
        self.state.active = False
        self._completion_timer = 0.0
