"""Procedural pixel art sprite generation for RogueDice."""

import pygame
import math
from typing import Dict, Tuple, Optional, List
from ..models.enums import Rarity, ItemType, SquareType


# Enhanced color palette
PALETTE = {
    # Base colors
    'black': (10, 10, 15),
    'white': (255, 255, 255),
    'cream': (255, 245, 230),

    # Grays
    'gray_dark': (40, 42, 48),
    'gray': (80, 85, 95),
    'gray_light': (140, 145, 155),

    # UI colors
    'panel_bg': (25, 28, 35),
    'panel_border': (60, 65, 75),
    'panel_highlight': (90, 95, 105),

    # Game colors
    'gold': (255, 200, 50),
    'gold_dark': (180, 130, 20),
    'gold_light': (255, 230, 120),

    'red': (220, 60, 60),
    'red_dark': (150, 30, 30),
    'red_light': (255, 120, 120),

    'green': (60, 200, 80),
    'green_dark': (30, 130, 50),
    'green_light': (120, 255, 140),

    'blue': (60, 120, 220),
    'blue_dark': (30, 70, 150),
    'blue_light': (120, 180, 255),

    'purple': (160, 80, 200),
    'purple_dark': (100, 40, 140),
    'purple_light': (200, 140, 255),

    'cyan': (60, 200, 220),
    'orange': (255, 150, 50),
    'pink': (255, 100, 150),

    # Board colors
    'grass': (60, 120, 60),
    'grass_dark': (40, 90, 40),
    'wood': (120, 80, 50),
    'wood_dark': (80, 50, 30),
    'stone': (100, 100, 110),
    'stone_dark': (70, 70, 80),
}

# Rarity color schemes (main, dark, light, glow)
RARITY_SCHEMES = {
    Rarity.COMMON: ((180, 180, 180), (120, 120, 120), (220, 220, 220), None),
    Rarity.UNCOMMON: ((80, 200, 80), (40, 140, 40), (140, 255, 140), (80, 200, 80)),
    Rarity.RARE: ((80, 140, 255), (40, 80, 180), (140, 180, 255), (80, 140, 255)),
    Rarity.EPIC: ((180, 80, 255), (120, 40, 180), (220, 140, 255), (180, 80, 255)),
    Rarity.LEGENDARY: ((255, 180, 50), (180, 120, 20), (255, 220, 120), (255, 180, 50)),
    Rarity.MYTHICAL: ((255, 80, 80), (180, 40, 40), (255, 140, 140), (255, 80, 80)),
}


class SpriteGenerator:
    """Generates polished procedural pixel art sprites."""

    def __init__(self):
        self.cache: Dict[str, pygame.Surface] = {}

    def get_or_create(self, key: str, creator_func, *args) -> pygame.Surface:
        """Get cached sprite or create new one."""
        if key not in self.cache:
            self.cache[key] = creator_func(*args)
        return self.cache[key]

    # ========== DICE SPRITES ==========

    def create_dice(self, size: int = 48, value: int = 0,
                    die_type: str = "d6", rolling: bool = False) -> pygame.Surface:
        """Create a polished dice sprite."""
        key = f"dice_{size}_{value}_{die_type}_{rolling}"
        return self.get_or_create(key, self._create_dice_impl, size, value, die_type, rolling)

    def _create_dice_impl(self, size: int, value: int, die_type: str, rolling: bool) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Dice colors
        face_color = (250, 245, 235) if not rolling else (255, 220, 180)
        shadow_color = (180, 170, 160)
        edge_color = (100, 95, 90)
        dot_color = (30, 30, 40)

        margin = size // 8
        dice_size = size - margin * 2

        # Draw 3D dice body
        # Shadow
        pygame.draw.rect(surf, shadow_color,
                        (margin + 3, margin + 3, dice_size, dice_size),
                        border_radius=size // 6)

        # Main face
        pygame.draw.rect(surf, face_color,
                        (margin, margin, dice_size, dice_size),
                        border_radius=size // 6)

        # Top highlight
        pygame.draw.rect(surf, (255, 255, 255),
                        (margin + 2, margin + 2, dice_size - 4, dice_size // 3),
                        border_radius=size // 8)

        # Edge
        pygame.draw.rect(surf, edge_color,
                        (margin, margin, dice_size, dice_size),
                        width=2, border_radius=size // 6)

        # Draw pips based on value (for d6)
        if value > 0 and die_type == "d6":
            self._draw_dice_pips(surf, value, margin, dice_size, dot_color)
        elif value > 0:
            # Draw number for other dice
            font = pygame.font.Font(None, size // 2)
            text = font.render(str(value), True, dot_color)
            text_rect = text.get_rect(center=(size // 2, size // 2))
            surf.blit(text, text_rect)

        # Rolling effect - motion blur lines
        if rolling:
            for i in range(3):
                alpha = 100 - i * 30
                line_surf = pygame.Surface((size, 2), pygame.SRCALPHA)
                line_surf.fill((*PALETTE['gold'][:3], alpha))
                surf.blit(line_surf, (0, size // 4 + i * size // 6))

        return surf

    def _draw_dice_pips(self, surf: pygame.Surface, value: int,
                        margin: int, dice_size: int, color: Tuple[int, int, int]):
        """Draw dice pips for d6."""
        pip_size = dice_size // 6
        cx, cy = margin + dice_size // 2, margin + dice_size // 2
        offset = dice_size // 3

        pip_positions = {
            1: [(cx, cy)],
            2: [(cx - offset, cy - offset), (cx + offset, cy + offset)],
            3: [(cx - offset, cy - offset), (cx, cy), (cx + offset, cy + offset)],
            4: [(cx - offset, cy - offset), (cx + offset, cy - offset),
                (cx - offset, cy + offset), (cx + offset, cy + offset)],
            5: [(cx - offset, cy - offset), (cx + offset, cy - offset),
                (cx, cy),
                (cx - offset, cy + offset), (cx + offset, cy + offset)],
            6: [(cx - offset, cy - offset), (cx + offset, cy - offset),
                (cx - offset, cy), (cx + offset, cy),
                (cx - offset, cy + offset), (cx + offset, cy + offset)],
        }

        for px, py in pip_positions.get(value, []):
            pygame.draw.circle(surf, color, (int(px), int(py)), pip_size)
            # Highlight on pip
            pygame.draw.circle(surf, (60, 60, 70), (int(px) - 1, int(py) - 1), pip_size // 2)

    # ========== ITEM ICONS ==========

    def create_item_icon(self, item_type: ItemType, rarity: Rarity,
                         level: int, size: int = 64) -> pygame.Surface:
        """Create a polished item icon."""
        key = f"item_{item_type.name}_{rarity.name}_{level}_{size}"
        return self.get_or_create(key, self._create_item_impl, item_type, rarity, level, size)

    def _create_item_impl(self, item_type: ItemType, rarity: Rarity,
                          level: int, size: int) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        colors = RARITY_SCHEMES.get(rarity, RARITY_SCHEMES[Rarity.COMMON])
        main_color, dark_color, light_color, glow_color = colors

        # Draw glow for rare+ items
        if glow_color:
            for i in range(3):
                glow_alpha = 30 - i * 10
                glow_surf = pygame.Surface((size, size), pygame.SRCALPHA)
                pygame.draw.circle(glow_surf, (*glow_color, glow_alpha),
                                  (size // 2, size // 2), size // 2 - i * 4)
                surf.blit(glow_surf, (0, 0))

        # Draw item based on type
        if item_type == ItemType.WEAPON:
            self._draw_sword(surf, size, main_color, dark_color, light_color)
        elif item_type == ItemType.ARMOR:
            self._draw_armor(surf, size, main_color, dark_color, light_color)
        elif item_type == ItemType.JEWELRY:
            self._draw_ring(surf, size, main_color, dark_color, light_color)
        else:
            self._draw_potion(surf, size, main_color, dark_color, light_color)

        return surf

    def _draw_sword(self, surf: pygame.Surface, size: int,
                    main: Tuple, dark: Tuple, light: Tuple):
        """Draw a sword icon."""
        cx, cy = size // 2, size // 2

        # Blade
        blade_points = [
            (cx, size // 8),      # Tip
            (cx + size // 6, cy - size // 8),  # Right edge
            (cx + size // 8, cy + size // 6),  # Right base
            (cx - size // 8, cy + size // 6),  # Left base
            (cx - size // 6, cy - size // 8),  # Left edge
        ]
        pygame.draw.polygon(surf, (200, 210, 220), blade_points)
        pygame.draw.polygon(surf, (150, 160, 170), blade_points, 2)

        # Blade highlight
        highlight_points = [
            (cx, size // 8 + 4),
            (cx + size // 10, cy - size // 8),
            (cx, cy),
        ]
        pygame.draw.polygon(surf, (240, 245, 255), highlight_points)

        # Guard
        pygame.draw.rect(surf, main,
                        (cx - size // 4, cy + size // 8, size // 2, size // 10))
        pygame.draw.rect(surf, dark,
                        (cx - size // 4, cy + size // 8, size // 2, size // 10), 1)

        # Handle
        pygame.draw.rect(surf, (80, 60, 40),
                        (cx - size // 12, cy + size // 6, size // 6, size // 3))
        pygame.draw.rect(surf, (60, 45, 30),
                        (cx - size // 12, cy + size // 6, size // 6, size // 3), 1)

        # Pommel
        pygame.draw.circle(surf, main, (cx, size - size // 6), size // 10)
        pygame.draw.circle(surf, light, (cx - 2, size - size // 6 - 2), size // 20)

    def _draw_armor(self, surf: pygame.Surface, size: int,
                    main: Tuple, dark: Tuple, light: Tuple):
        """Draw an armor/chestplate icon."""
        cx, cy = size // 2, size // 2

        # Body
        body_points = [
            (cx - size // 3, size // 6),       # Left shoulder
            (cx + size // 3, size // 6),       # Right shoulder
            (cx + size // 3, cy),              # Right arm
            (cx + size // 4, size - size // 5),  # Right bottom
            (cx, size - size // 6),            # Bottom center
            (cx - size // 4, size - size // 5),  # Left bottom
            (cx - size // 3, cy),              # Left arm
        ]
        pygame.draw.polygon(surf, main, body_points)
        pygame.draw.polygon(surf, dark, body_points, 2)

        # Highlight
        pygame.draw.arc(surf, light,
                       (cx - size // 4, size // 5, size // 2, size // 3),
                       0.5, 2.6, 3)

        # Neck opening
        pygame.draw.ellipse(surf, PALETTE['panel_bg'],
                           (cx - size // 6, size // 8, size // 3, size // 6))

        # Center line detail
        pygame.draw.line(surf, dark, (cx, size // 4), (cx, size - size // 5), 2)

    def _draw_ring(self, surf: pygame.Surface, size: int,
                   main: Tuple, dark: Tuple, light: Tuple):
        """Draw a ring icon."""
        cx, cy = size // 2, size // 2

        # Ring band (3D effect)
        pygame.draw.ellipse(surf, dark,
                           (cx - size // 3, cy - size // 5, size * 2 // 3, size * 2 // 5))
        pygame.draw.ellipse(surf, main,
                           (cx - size // 3 + 2, cy - size // 5 + 2,
                            size * 2 // 3 - 4, size * 2 // 5 - 4))
        pygame.draw.ellipse(surf, PALETTE['panel_bg'],
                           (cx - size // 5, cy - size // 10, size * 2 // 5, size // 5))

        # Gem on top
        gem_y = cy - size // 6
        pygame.draw.circle(surf, light, (cx, gem_y), size // 6)
        pygame.draw.circle(surf, main, (cx, gem_y), size // 7)

        # Gem highlight
        pygame.draw.circle(surf, (255, 255, 255), (cx - 3, gem_y - 3), size // 14)

    def _draw_potion(self, surf: pygame.Surface, size: int,
                     main: Tuple, dark: Tuple, light: Tuple):
        """Draw a potion icon."""
        cx, cy = size // 2, size // 2

        # Bottle body
        pygame.draw.ellipse(surf, main,
                           (cx - size // 4, cy, size // 2, size // 2 - 4))
        pygame.draw.ellipse(surf, dark,
                           (cx - size // 4, cy, size // 2, size // 2 - 4), 2)

        # Neck
        pygame.draw.rect(surf, (180, 180, 190),
                        (cx - size // 10, cy - size // 8, size // 5, size // 4))

        # Cork
        pygame.draw.rect(surf, (120, 80, 50),
                        (cx - size // 8, cy - size // 5, size // 4, size // 8))

        # Liquid highlight
        pygame.draw.ellipse(surf, light,
                           (cx - size // 6, cy + size // 10, size // 4, size // 4))

    # ========== UI ELEMENTS ==========

    def create_panel(self, width: int, height: int,
                     style: str = "default") -> pygame.Surface:
        """Create a polished UI panel."""
        key = f"panel_{width}_{height}_{style}"
        return self.get_or_create(key, self._create_panel_impl, width, height, style)

    def _create_panel_impl(self, width: int, height: int, style: str) -> pygame.Surface:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)

        if style == "gold":
            bg = (30, 28, 25)
            border = PALETTE['gold_dark']
            highlight = PALETTE['gold']
        elif style == "red":
            bg = (35, 25, 25)
            border = PALETTE['red_dark']
            highlight = PALETTE['red']
        elif style == "purple":
            bg = (30, 25, 35)
            border = PALETTE['purple_dark']
            highlight = PALETTE['purple']
        else:
            bg = PALETTE['panel_bg']
            border = PALETTE['panel_border']
            highlight = PALETTE['panel_highlight']

        # Main background with rounded corners
        pygame.draw.rect(surf, bg, (0, 0, width, height), border_radius=6)

        # Inner border
        pygame.draw.rect(surf, border, (2, 2, width - 4, height - 4),
                        width=2, border_radius=5)

        # Top highlight
        pygame.draw.line(surf, (*highlight, 100), (6, 4), (width - 6, 4), 1)

        # Corner accents
        corner_size = 8
        corners = [(4, 4), (width - 4, 4), (4, height - 4), (width - 4, height - 4)]
        for cx, cy in corners:
            pygame.draw.circle(surf, highlight, (cx, cy), 2)

        return surf

    def create_button(self, width: int, height: int,
                      pressed: bool = False, style: str = "default") -> pygame.Surface:
        """Create a polished button."""
        key = f"button_{width}_{height}_{pressed}_{style}"
        return self.get_or_create(key, self._create_button_impl, width, height, pressed, style)

    def _create_button_impl(self, width: int, height: int,
                            pressed: bool, style: str) -> pygame.Surface:
        surf = pygame.Surface((width, height), pygame.SRCALPHA)

        if style == "gold":
            top = PALETTE['gold'] if not pressed else PALETTE['gold_dark']
            bottom = PALETTE['gold_dark'] if not pressed else PALETTE['gold']
        else:
            top = PALETTE['gray_light'] if not pressed else PALETTE['gray']
            bottom = PALETTE['gray'] if not pressed else PALETTE['gray_light']

        offset = 2 if pressed else 0
        btn_height = height - 4 if not pressed else height - 2

        # Shadow
        if not pressed:
            pygame.draw.rect(surf, PALETTE['black'],
                           (2, 4, width - 4, height - 4), border_radius=4)

        # Button body gradient (top to bottom)
        for i in range(btn_height):
            t = i / btn_height
            color = tuple(int(top[j] * (1 - t) + bottom[j] * t) for j in range(3))
            pygame.draw.line(surf, color, (2, offset + i + 2), (width - 3, offset + i + 2))

        # Border
        pygame.draw.rect(surf, PALETTE['black'],
                        (2, offset + 2, width - 4, btn_height),
                        width=1, border_radius=4)

        return surf

    def create_health_bar(self, width: int, height: int,
                          percent: float, style: str = "default") -> pygame.Surface:
        """Create a polished health bar."""
        surf = pygame.Surface((width, height), pygame.SRCALPHA)

        # Background
        pygame.draw.rect(surf, PALETTE['black'], (0, 0, width, height), border_radius=3)
        pygame.draw.rect(surf, PALETTE['gray_dark'], (2, 2, width - 4, height - 4), border_radius=2)

        # Health fill
        fill_width = int((width - 4) * max(0, min(1, percent)))
        if fill_width > 0:
            # Color based on health
            if percent > 0.5:
                color = PALETTE['green']
                light = PALETTE['green_light']
            elif percent > 0.25:
                color = PALETTE['orange']
                light = PALETTE['gold_light']
            else:
                color = PALETTE['red']
                light = PALETTE['red_light']

            pygame.draw.rect(surf, color, (2, 2, fill_width, height - 4), border_radius=2)

            # Highlight
            pygame.draw.rect(surf, light, (2, 2, fill_width, (height - 4) // 3), border_radius=2)

        # Border
        pygame.draw.rect(surf, PALETTE['gray'], (0, 0, width, height), width=1, border_radius=3)

        return surf

    # ========== BOARD TILES ==========

    def create_board_tile(self, size: int, square_type: SquareType,
                          has_monster: bool = False, has_player: bool = False) -> pygame.Surface:
        """Create a polished board tile."""
        key = f"tile_{size}_{square_type.name}_{has_monster}_{has_player}"
        return self.get_or_create(key, self._create_tile_impl, size, square_type, has_monster, has_player)

    def _create_tile_impl(self, size: int, square_type: SquareType,
                          has_monster: bool, has_player: bool) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Base colors by type
        type_colors = {
            SquareType.EMPTY: (PALETTE['grass'], PALETTE['grass_dark']),
            SquareType.MONSTER: (PALETTE['red_dark'], (100, 30, 30)),
            SquareType.ITEM: ((50, 80, 120), (30, 50, 80)),
            SquareType.BLESSING: ((100, 60, 140), (70, 40, 100)),
            SquareType.CORNER_START: (PALETTE['green'], PALETTE['green_dark']),
            SquareType.CORNER_SHOP: (PALETTE['gold_dark'], (120, 90, 20)),
            SquareType.CORNER_REST: (PALETTE['blue'], PALETTE['blue_dark']),
            SquareType.CORNER_BOSS: ((160, 40, 40), (100, 20, 20)),
            SquareType.SPECIAL: (PALETTE['purple'], PALETTE['purple_dark']),
        }

        main_color, dark_color = type_colors.get(square_type, (PALETTE['gray'], PALETTE['gray_dark']))

        # Tile base
        pygame.draw.rect(surf, dark_color, (0, 0, size, size))
        pygame.draw.rect(surf, main_color, (2, 2, size - 4, size - 4))

        # Add texture pattern
        for i in range(0, size, 8):
            for j in range(0, size, 8):
                if (i + j) % 16 == 0:
                    pygame.draw.rect(surf, dark_color, (i, j, 2, 2))

        # Border
        pygame.draw.rect(surf, PALETTE['black'], (0, 0, size, size), 1)

        # Type indicator in center
        cx, cy = size // 2, size // 2
        if square_type == SquareType.MONSTER or has_monster:
            # Skull icon
            pygame.draw.circle(surf, (200, 200, 200), (cx, cy - 2), 8)
            pygame.draw.circle(surf, PALETTE['black'], (cx - 3, cy - 3), 2)
            pygame.draw.circle(surf, PALETTE['black'], (cx + 3, cy - 3), 2)
            pygame.draw.rect(surf, (200, 200, 200), (cx - 4, cy + 3, 8, 4))
        elif square_type == SquareType.ITEM:
            # Chest icon
            pygame.draw.rect(surf, (150, 100, 50), (cx - 7, cy - 4, 14, 10))
            pygame.draw.rect(surf, (100, 70, 35), (cx - 7, cy - 4, 14, 10), 1)
            pygame.draw.rect(surf, PALETTE['gold'], (cx - 2, cy, 4, 3))
        elif square_type == SquareType.BLESSING:
            # Star icon
            self._draw_star(surf, cx, cy, 8, PALETTE['gold'])
        elif square_type == SquareType.CORNER_SHOP:
            # Coin icon
            pygame.draw.circle(surf, PALETTE['gold'], (cx, cy), 10)
            pygame.draw.circle(surf, PALETTE['gold_dark'], (cx, cy), 10, 2)
            pygame.draw.circle(surf, PALETTE['gold_light'], (cx - 2, cy - 2), 3)
        elif square_type == SquareType.CORNER_REST:
            # Heart icon
            self._draw_heart(surf, cx, cy, 10)
        elif square_type == SquareType.CORNER_BOSS:
            # Crown icon
            self._draw_crown(surf, cx, cy - 2, 12)

        # Player token
        if has_player:
            pygame.draw.circle(surf, PALETTE['blue'], (cx, cy), 12)
            pygame.draw.circle(surf, PALETTE['blue_light'], (cx, cy), 12, 2)
            pygame.draw.circle(surf, (255, 255, 255), (cx - 3, cy - 3), 4)

        return surf

    def _draw_star(self, surf: pygame.Surface, cx: int, cy: int,
                   size: int, color: Tuple[int, int, int]):
        """Draw a 5-pointed star."""
        points = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r = size if i % 2 == 0 else size // 2
            points.append((cx + int(r * math.cos(angle)),
                          cy - int(r * math.sin(angle))))
        pygame.draw.polygon(surf, color, points)

    def _draw_heart(self, surf: pygame.Surface, cx: int, cy: int, size: int):
        """Draw a heart shape."""
        pygame.draw.circle(surf, PALETTE['red'], (cx - size // 3, cy - size // 4), size // 2)
        pygame.draw.circle(surf, PALETTE['red'], (cx + size // 3, cy - size // 4), size // 2)
        pygame.draw.polygon(surf, PALETTE['red'], [
            (cx - size, cy),
            (cx + size, cy),
            (cx, cy + size)
        ])

    def _draw_crown(self, surf: pygame.Surface, cx: int, cy: int, size: int):
        """Draw a crown icon."""
        points = [
            (cx - size, cy + size // 2),
            (cx - size, cy - size // 4),
            (cx - size // 2, cy + size // 4),
            (cx, cy - size // 2),
            (cx + size // 2, cy + size // 4),
            (cx + size, cy - size // 4),
            (cx + size, cy + size // 2),
        ]
        pygame.draw.polygon(surf, PALETTE['gold'], points)
        pygame.draw.polygon(surf, PALETTE['gold_dark'], points, 2)

        # Gems on points
        pygame.draw.circle(surf, PALETTE['red'], (cx, cy - size // 2 + 3), 3)

    # ========== CHARACTER PORTRAITS ==========

    def create_character_portrait(self, char_id: str, size: int = 64) -> pygame.Surface:
        """Create a character portrait."""
        key = f"portrait_{char_id}_{size}"
        return self.get_or_create(key, self._create_portrait_impl, char_id, size)

    def _create_portrait_impl(self, char_id: str, size: int) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Character color schemes
        char_colors = {
            'warrior': (PALETTE['gray'], PALETTE['red']),
            'rogue': (PALETTE['purple_dark'], PALETTE['green']),
            'paladin': (PALETTE['gold'], PALETTE['blue']),
            'berserker': (PALETTE['red'], PALETTE['orange']),
            'monk': (PALETTE['orange'], PALETTE['cream']),
            'gambler': (PALETTE['green'], PALETTE['gold']),
            'vampire': (PALETTE['red_dark'], PALETTE['purple']),
            'mage': (PALETTE['blue'], PALETTE['cyan']),
            'necromancer': (PALETTE['purple'], PALETTE['green']),
            'jester': (PALETTE['pink'], PALETTE['gold']),
            'avatar': (PALETTE['gold'], PALETTE['white']),
        }

        main_color, accent = char_colors.get(char_id, (PALETTE['gray'], PALETTE['white']))

        cx, cy = size // 2, size // 2

        # Background circle
        pygame.draw.circle(surf, PALETTE['panel_bg'], (cx, cy), size // 2 - 2)
        pygame.draw.circle(surf, main_color, (cx, cy), size // 2 - 2, 3)

        # Simple face
        # Head
        pygame.draw.circle(surf, (220, 180, 150), (cx, cy - 4), size // 4)

        # Eyes
        eye_y = cy - 6
        pygame.draw.circle(surf, PALETTE['black'], (cx - 6, eye_y), 3)
        pygame.draw.circle(surf, PALETTE['black'], (cx + 6, eye_y), 3)
        pygame.draw.circle(surf, (255, 255, 255), (cx - 5, eye_y - 1), 1)
        pygame.draw.circle(surf, (255, 255, 255), (cx + 7, eye_y - 1), 1)

        # Character-specific features
        if char_id == 'warrior':
            # Helmet
            pygame.draw.arc(surf, PALETTE['gray_light'],
                          (cx - 14, cy - 20, 28, 20), 0, math.pi, 4)
        elif char_id == 'mage':
            # Wizard hat
            pygame.draw.polygon(surf, accent, [
                (cx, cy - 28), (cx - 12, cy - 8), (cx + 12, cy - 8)
            ])
        elif char_id == 'rogue':
            # Hood
            pygame.draw.arc(surf, PALETTE['purple_dark'],
                          (cx - 16, cy - 22, 32, 24), 0, math.pi, 5)
        elif char_id == 'vampire':
            # Fangs
            pygame.draw.polygon(surf, (255, 255, 255), [
                (cx - 4, cy + 4), (cx - 2, cy + 10), (cx, cy + 4)
            ])
            pygame.draw.polygon(surf, (255, 255, 255), [
                (cx, cy + 4), (cx + 2, cy + 10), (cx + 4, cy + 4)
            ])
        elif char_id == 'jester':
            # Jester hat
            pygame.draw.circle(surf, accent, (cx - 12, cy - 18), 6)
            pygame.draw.circle(surf, PALETTE['pink'], (cx + 12, cy - 18), 6)

        # Body hint
        pygame.draw.ellipse(surf, main_color,
                           (cx - 16, cy + 10, 32, 20))

        return surf


# Global sprite generator instance
sprites = SpriteGenerator()
