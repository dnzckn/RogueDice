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

        # Fonts
        self.font_large = pygame.font.Font(None, 28)
        self.font_medium = pygame.font.Font(None, 20)
        self.font_small = pygame.font.Font(None, 16)

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

            # Match enemy dealing damage - format: "[0.2s] Enemy deals 8 damage!"
            elif "enemy deal" in line_lower and "damage" in line_lower:
                damage = 0
                is_crit = "crit" in line_lower or "critical" in line_lower
                match = re.search(r'deals?\s+(\d+)\s+damage', line_lower)
                if match:
                    damage = int(match.group(1))
                if damage > 0:
                    actions.append(BattleAction(
                        action_type="monster_attack",
                        damage=damage,
                        is_crit=is_crit,
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
            self.state.monster_attack_anim = 1.0
            self.state.player_shake = 1.0
            self.state.player_flash = 1.0
            self.state.target_player_hp = max(0, self.state.target_player_hp - action.damage)

            # Add damage popup on player (panel-relative)
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

        # Flash effect (damage taken)
        if self.state.player_flash > 0:
            flash_surf = pygame.Surface(sprite.get_size(), pygame.SRCALPHA)
            flash_surf.fill((255, 100, 100, int(150 * self.state.player_flash)))
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
                text = f"{self.monster_name}: {action.damage} dmg!"
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
                and self._completion_timer >= 1.2)  # 1.2 seconds to see HP at 0

    def dismiss(self) -> None:
        """Dismiss the battle scene."""
        self.state.active = False
        self._completion_timer = 0.0
