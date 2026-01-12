"""Procedural pixel art sprite generation for RogueDice with external asset support."""

import os
import sys
import io

# Suppress libpng iCCP warnings BEFORE importing pygame
# Set environment variable to disable libpng warning output
os.environ['SDL_VIDEO_X11_NET_WM_BYPASS_COMPOSITOR'] = '0'

import pygame
import math
import random
import ctypes
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from ..models.enums import Rarity, ItemType, SquareType


class SuppressLibpngWarnings:
    """Context manager to suppress libpng warnings during image loading.

    libpng outputs warnings to C-level stderr, so we need to redirect
    the actual file descriptor, not Python's sys.stderr.
    """
    def __init__(self):
        self._original_stderr_fd = None
        self._devnull_fd = None

    def __enter__(self):
        # Flush Python stderr first
        sys.stderr.flush()
        # Save the original stderr file descriptor
        try:
            self._original_stderr_fd = os.dup(2)
            # Open /dev/null and redirect stderr to it
            self._devnull_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(self._devnull_fd, 2)
        except (OSError, AttributeError):
            # On some systems this may not work
            self._original_stderr_fd = None
            self._devnull_fd = None
        return self

    def __exit__(self, *args):
        # Restore stderr
        sys.stderr.flush()
        try:
            if self._original_stderr_fd is not None:
                os.dup2(self._original_stderr_fd, 2)
                os.close(self._original_stderr_fd)
            if self._devnull_fd is not None:
                os.close(self._devnull_fd)
        except (OSError, AttributeError):
            pass


# Global suppressor for use throughout module
_libpng_suppressor = SuppressLibpngWarnings()


# Asset paths
ASSETS_DIR = Path(__file__).parent.parent / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
TILES_DIR = ASSETS_DIR / "tiles" / "crawl-tiles Oct-5-2010"
MONSTERS_DIR = TILES_DIR / "dc-mon"
ITEMS_DIR = TILES_DIR / "item"
PLAYER_DIR = TILES_DIR / "player"
UI_DIR = ASSETS_DIR / "ui"
WEAPONS_DIR = ASSETS_DIR / "weapons" / "Icons"


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


class AssetLoader:
    """Loads and manages external sprite assets."""

    # Monster sprite mappings - maps game monster types to asset files
    MONSTER_ASSETS = {
        'goblin': [MONSTERS_DIR / 'goblin.png', MONSTERS_DIR / 'hobgoblin.png'],
        'orc': [MONSTERS_DIR / 'orc.png', MONSTERS_DIR / 'orc_warrior.png', MONSTERS_DIR / 'orc_warlord.png'],
        'skeleton': [MONSTERS_DIR / 'undead' / 'skeletons' / 'skeleton_humanoid_small.png',
                     MONSTERS_DIR / 'undead' / 'skeletons' / 'skeleton_humanoid_large.png'],
        'zombie': [MONSTERS_DIR / 'undead' / 'ghoul.png',
                   MONSTERS_DIR / 'undead' / 'necrophage.png',
                   MONSTERS_DIR / 'undead' / 'rotting_hulk.png'],
        'wolf': [MONSTERS_DIR / 'animals' / 'wolf.png'],
        'spider': [MONSTERS_DIR / 'animals' / 'jumping_spider.png',
                   MONSTERS_DIR / 'animals' / 'wolf_spider.png',
                   MONSTERS_DIR / 'animals' / 'trapdoor_spider.png'],
        'slime': [MONSTERS_DIR / 'jelly.png', MONSTERS_DIR / 'ooze.png',
                  MONSTERS_DIR / 'acid_blob.png', MONSTERS_DIR / 'azure_jelly.png'],
        'bat': [MONSTERS_DIR / 'animals' / 'giant_bat.png'],
        'ghost': [MONSTERS_DIR / 'undead' / 'ghost.png', MONSTERS_DIR / 'undead' / 'phantom.png',
                  MONSTERS_DIR / 'undead' / 'flayed_ghost.png'],
        'demon': [MONSTERS_DIR / 'demons' / 'imp.png', MONSTERS_DIR / 'demons' / 'beast.png',
                  MONSTERS_DIR / 'demons' / 'balrug.png', MONSTERS_DIR / 'demons' / 'fiend.png'],
        'dragon': [MONSTERS_DIR / 'dragon.png', MONSTERS_DIR / 'draco'],
        'troll': [MONSTERS_DIR / 'troll.png', MONSTERS_DIR / 'rock_troll.png', MONSTERS_DIR / 'deep_troll.png'],
        'minotaur': [MONSTERS_DIR / 'ettin.png', MONSTERS_DIR / 'cyclops.png'],
        'lich': [MONSTERS_DIR / 'undead' / 'lich.png', MONSTERS_DIR / 'undead' / 'ancient_lich.png'],
        'golem': [MONSTERS_DIR / 'nonliving' / 'stone_golem.png',
                  MONSTERS_DIR / 'nonliving' / 'iron_golem.png',
                  MONSTERS_DIR / 'nonliving' / 'clay_golem.png'],
        'bear': [MONSTERS_DIR / 'animals' / 'bear.png', MONSTERS_DIR / 'animals' / 'black_bear.png',
                 MONSTERS_DIR / 'animals' / 'grizzly_bear.png'],
        'elemental': [MONSTERS_DIR / 'nonliving' / 'fire_elemental.png',
                      MONSTERS_DIR / 'nonliving' / 'water_elemental.png',
                      MONSTERS_DIR / 'nonliving' / 'air_elemental.png'],
        'snake': [MONSTERS_DIR / 'animals' / 'anaconda.png',
                  MONSTERS_DIR / 'animals' / 'black_mamba.png'],
        'rat': [MONSTERS_DIR / 'animals' / 'rat.png', MONSTERS_DIR / 'animals' / 'grey_rat.png'],
        'ogre': [MONSTERS_DIR / 'ogre.png', MONSTERS_DIR / 'two_headed_ogre.png'],
        'giant': [MONSTERS_DIR / 'frost_giant.png', MONSTERS_DIR / 'fire_giant.png',
                  MONSTERS_DIR / 'cyclops.png'],
        'mummy': [MONSTERS_DIR / 'undead' / 'mummy.png',
                  MONSTERS_DIR / 'undead' / 'greater_mummy.png'],
        'wraith': [MONSTERS_DIR / 'undead' / 'freezing_wraith.png',
                   MONSTERS_DIR / 'undead' / 'phantom.png'],
        'angel': [MONSTERS_DIR / 'angel.png', MONSTERS_DIR / 'daeva.png'],
        'eye': [MONSTERS_DIR / 'giant_eyeball.png',
                MONSTERS_DIR / 'eye_of_draining.png'],
    }

    # Item icon mappings - maps item types to asset patterns
    ITEM_ICONS = {
        ItemType.WEAPON: {
            'patterns': ['W_Sword', 'W_Axe', 'W_Dagger', 'W_Hammer', 'W_Spear'],
            'dir': ICONS_DIR,
        },
        ItemType.ARMOR: {
            'patterns': ['A_Armor', 'A_Armour', 'A_Clothing'],
            'dir': ICONS_DIR,
        },
        ItemType.JEWELRY: {
            'patterns': ['Ac_Ring', 'Ac_Necklace'],
            'dir': ICONS_DIR,
        },
    }

    # Player character sprite mappings
    PLAYER_BASES = {
        'warrior': 'human_m.png',
        'rogue': 'elf_m.png',
        'paladin': 'human_f.png',
        'berserker': 'dwarf_m.png',
        'monk': 'human_m.png',
        'gambler': 'elf_f.png',
        'vampire': 'demonspawn_black_m.png',
        'mage': 'deep_elf_m.png',
        'necromancer': 'demonspawn_red_f.png',
        'jester': 'human_f.png',
        'avatar': 'demigod_m.png',
    }

    def __init__(self):
        self.loaded_assets: Dict[str, pygame.Surface] = {}
        self._scanned_icons: Dict[str, List[Path]] = {}
        self._scan_icons()

    def _scan_icons(self):
        """Scan icon directory and organize by type."""
        if not ICONS_DIR.exists():
            return

        for item_type, config in self.ITEM_ICONS.items():
            self._scanned_icons[item_type.name] = []
            for pattern in config['patterns']:
                icons = list(ICONS_DIR.glob(f"{pattern}*.png"))
                self._scanned_icons[item_type.name].extend(icons)

    def load_image(self, path: Path, size: Optional[Tuple[int, int]] = None) -> Optional[pygame.Surface]:
        """Load an image from path with optional scaling."""
        cache_key = f"{path}_{size}"
        if cache_key in self.loaded_assets:
            return self.loaded_assets[cache_key]

        if not path.exists():
            return None

        try:
            # Suppress libpng warnings during image loading
            with SuppressLibpngWarnings():
                img = pygame.image.load(str(path))
            # Try convert_alpha if display is available, otherwise just use the image
            try:
                img = img.convert_alpha()
            except pygame.error:
                # No display yet, use the raw surface
                pass
            if size:
                img = pygame.transform.smoothscale(img, size)
            self.loaded_assets[cache_key] = img
            return img
        except pygame.error:
            return None

    def get_monster_sprite(self, monster_type: str, size: int = 96, is_boss: bool = False) -> Optional[pygame.Surface]:
        """Get a monster sprite from assets."""
        paths = self.MONSTER_ASSETS.get(monster_type.lower(), [])

        for path in paths:
            if path.exists():
                # Load and scale
                target_size = int(size * (1.3 if is_boss else 1.0))
                img = self.load_image(path, (target_size, target_size))
                if img:
                    # Create surface with proper centering
                    surf = pygame.Surface((size, size), pygame.SRCALPHA)
                    offset_x = (size - target_size) // 2
                    offset_y = (size - target_size) // 2
                    surf.blit(img, (offset_x, offset_y))

                    # Add boss aura
                    if is_boss:
                        self._add_boss_aura(surf, size)

                    return surf
            elif path.is_dir():
                # Check for files in directory
                for subfile in path.glob("*.png"):
                    target_size = int(size * (1.3 if is_boss else 1.0))
                    img = self.load_image(subfile, (target_size, target_size))
                    if img:
                        surf = pygame.Surface((size, size), pygame.SRCALPHA)
                        offset_x = (size - target_size) // 2
                        offset_y = (size - target_size) // 2
                        surf.blit(img, (offset_x, offset_y))
                        if is_boss:
                            self._add_boss_aura(surf, size)
                        return surf

        return None

    def _add_boss_aura(self, surf: pygame.Surface, size: int):
        """Add boss aura effect to sprite."""
        cx, cy = size // 2, size // 2
        aura_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(5):
            alpha = 40 - i * 8
            pygame.draw.circle(aura_surf, (255, 60, 60, alpha),
                              (cx, cy), int(size * 0.45) + i * 3)
        surf.blit(aura_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def get_item_icon(self, item_type: ItemType, rarity: Rarity, level: int, size: int = 64) -> Optional[pygame.Surface]:
        """Get an item icon from assets."""
        icons = self._scanned_icons.get(item_type.name, [])
        if not icons:
            return None

        # Select icon based on level (higher level = later icon in sequence)
        icon_idx = min(level - 1, len(icons) - 1)
        icon_idx = max(0, icon_idx)

        if icon_idx < len(icons):
            path = icons[icon_idx]
            img = self.load_image(path, (size - 8, size - 8))
            if img:
                surf = pygame.Surface((size, size), pygame.SRCALPHA)

                # Add rarity glow background
                colors = RARITY_SCHEMES.get(rarity, RARITY_SCHEMES[Rarity.COMMON])
                _, _, _, glow_color = colors
                if glow_color:
                    for i in range(3):
                        glow_alpha = 30 - i * 10
                        pygame.draw.circle(surf, (*glow_color, glow_alpha),
                                          (size // 2, size // 2), size // 2 - i * 4)

                # Center the icon
                surf.blit(img, (4, 4))
                return surf

        return None

    def get_player_sprite(self, char_id: str, size: int = 96) -> Optional[pygame.Surface]:
        """Get a player character sprite from assets."""
        base_file = self.PLAYER_BASES.get(char_id, 'human_m.png')
        base_path = PLAYER_DIR / 'base' / base_file

        if base_path.exists():
            img = self.load_image(base_path, (size, size))
            if img:
                return img

        return None

    def get_floor_tile(self, tile_type: str, size: int = 40, variant: int = 0) -> Optional[pygame.Surface]:
        """Get a floor tile from assets."""
        floor_dir = TILES_DIR / 'dc-dngn' / 'floor'
        grass_dir = floor_dir / 'grass'

        # Map tile types to file patterns
        tile_configs = {
            'empty': (grass_dir, ['grass0.png', 'grass1.png', 'grass2.png']),
            'grass': (grass_dir, ['grass0.png', 'grass1.png', 'grass2.png',
                                  'grass_flowers_blue1.png', 'grass_flowers_yellow1.png']),
            'monster': (floor_dir, ['cobble_blood1.png', 'cobble_blood2.png', 'cobble_blood3.png']),
            'item': (floor_dir, ['rect_gray0.png', 'rect_gray1.png', 'rect_gray2.png']),
            'blessing': (floor_dir, ['crystal_floor0.png', 'crystal_floor1.png', 'crystal_floor2.png']),
            'shop': (floor_dir, ['sandstone_floor0.png', 'sandstone_floor1.png', 'sandstone_floor2.png']),
            'rest': (floor_dir, ['floor_sand_stone0.png', 'floor_sand_stone1.png', 'floor_sand_stone2.png']),
            'boss': (floor_dir, ['cobble_blood5.png', 'cobble_blood6.png', 'cobble_blood7.png']),
            'start': (grass_dir, ['grass_flowers_blue1.png', 'grass_flowers_blue2.png']),
            'special': (floor_dir, ['crystal_floor3.png', 'crystal_floor4.png', 'crystal_floor5.png']),
            'normal': (floor_dir, ['grey_dirt0.png', 'grey_dirt1.png', 'grey_dirt2.png']),
        }

        config = tile_configs.get(tile_type, tile_configs['normal'])
        directory, files = config

        # Select variant
        idx = variant % len(files)
        path = directory / files[idx]

        if path.exists():
            return self.load_image(path, (size, size))

        return None

    def get_potion_sprite(self, size: int = 32) -> Optional[pygame.Surface]:
        """Get a potion sprite from assets."""
        potion_dir = ITEMS_DIR / 'potion'
        if potion_dir.exists():
            # Try to get a heal potion
            for name in ['i-heal.png', 'i-heal-wounds.png', 'emerald.png', 'cyan.png']:
                path = potion_dir / name
                if path.exists():
                    return self.load_image(path, (size, size))
        return None


# Global asset loader instance
asset_loader = AssetLoader()


class SpriteGenerator:
    """Generates polished procedural pixel art sprites with asset fallback."""

    def __init__(self):
        self.cache: Dict[str, pygame.Surface] = {}
        self.asset_loader = asset_loader

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
        # Try to load from external assets first
        asset_icon = self.asset_loader.get_item_icon(item_type, rarity, level, size)
        if asset_icon:
            return asset_icon

        # Fall back to procedural generation
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

        # Map square types to floor tile types
        type_to_floor = {
            SquareType.EMPTY: 'empty',
            SquareType.MONSTER: 'monster',
            SquareType.ITEM: 'item',
            SquareType.BLESSING: 'blessing',
            SquareType.CORNER_START: 'start',
            SquareType.CORNER_SHOP: 'shop',
            SquareType.CORNER_REST: 'rest',
            SquareType.CORNER_BOSS: 'boss',
            SquareType.SPECIAL: 'special',
        }

        # Try to load external floor tile
        floor_type = type_to_floor.get(square_type, 'normal')
        # Use hash of square_type for consistent variant
        variant = hash(square_type.name) % 10
        floor_tile = self.asset_loader.get_floor_tile(floor_type, size, variant)

        if floor_tile:
            surf.blit(floor_tile, (0, 0))
        else:
            # Fall back to procedural generation
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
        # Try to load from external assets first
        asset_sprite = self.asset_loader.get_player_sprite(char_id, size)
        if asset_sprite:
            # Add a portrait frame around the asset
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, PALETTE['panel_bg'], (size // 2, size // 2), size // 2 - 2)
            # Scale and center the sprite
            scaled = pygame.transform.smoothscale(asset_sprite, (size - 8, size - 8))
            surf.blit(scaled, (4, 4))
            pygame.draw.circle(surf, PALETTE['panel_border'], (size // 2, size // 2), size // 2 - 2, 3)
            return surf

        # Fall back to procedural generation
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

    # ========== MONSTER SPRITES ==========

    def create_monster_sprite(self, monster_type: str, size: int = 96,
                              is_boss: bool = False) -> pygame.Surface:
        """Create a monster battle sprite."""
        key = f"monster_{monster_type}_{size}_{is_boss}"
        return self.get_or_create(key, self._create_monster_impl, monster_type, size, is_boss)

    def _create_monster_impl(self, monster_type: str, size: int, is_boss: bool) -> pygame.Surface:
        # Try to load from external assets first
        asset_sprite = self.asset_loader.get_monster_sprite(monster_type, size, is_boss)
        if asset_sprite:
            return asset_sprite

        # Fall back to procedural generation
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2

        # Monster type definitions
        monster_defs = {
            'goblin': {'color': (80, 140, 60), 'eyes': 2, 'shape': 'humanoid'},
            'orc': {'color': (60, 100, 50), 'eyes': 2, 'shape': 'humanoid'},
            'skeleton': {'color': (220, 220, 200), 'eyes': 2, 'shape': 'humanoid'},
            'zombie': {'color': (100, 120, 80), 'eyes': 2, 'shape': 'humanoid'},
            'wolf': {'color': (100, 90, 80), 'eyes': 2, 'shape': 'beast'},
            'spider': {'color': (50, 40, 50), 'eyes': 8, 'shape': 'spider'},
            'slime': {'color': (80, 200, 100), 'eyes': 2, 'shape': 'blob'},
            'bat': {'color': (80, 70, 90), 'eyes': 2, 'shape': 'bat'},
            'ghost': {'color': (180, 200, 220), 'eyes': 2, 'shape': 'ghost'},
            'demon': {'color': (180, 50, 50), 'eyes': 2, 'shape': 'demon'},
            'dragon': {'color': (150, 50, 50), 'eyes': 2, 'shape': 'dragon'},
            'troll': {'color': (80, 100, 70), 'eyes': 2, 'shape': 'humanoid'},
            'minotaur': {'color': (120, 80, 60), 'eyes': 2, 'shape': 'humanoid'},
            'lich': {'color': (100, 80, 150), 'eyes': 2, 'shape': 'humanoid'},
            'golem': {'color': (130, 130, 140), 'eyes': 2, 'shape': 'humanoid'},
        }

        # Default monster if type not found
        mdef = monster_defs.get(monster_type.lower(), {'color': (120, 100, 100), 'eyes': 2, 'shape': 'humanoid'})
        color = mdef['color']
        dark_color = tuple(max(0, c - 40) for c in color)
        light_color = tuple(min(255, c + 40) for c in color)

        # Boss modifier - make larger and add effects
        scale = 1.3 if is_boss else 1.0

        shape = mdef['shape']

        if shape == 'humanoid':
            self._draw_humanoid_monster(surf, cx, cy, size, color, dark_color, light_color, scale, is_boss)
        elif shape == 'beast':
            self._draw_beast_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        elif shape == 'spider':
            self._draw_spider_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        elif shape == 'blob':
            self._draw_blob_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        elif shape == 'ghost':
            self._draw_ghost_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        elif shape == 'demon':
            self._draw_demon_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        elif shape == 'dragon':
            self._draw_dragon_monster(surf, cx, cy, size, color, dark_color, light_color, scale, is_boss)
        elif shape == 'bat':
            self._draw_bat_monster(surf, cx, cy, size, color, dark_color, light_color, scale)
        else:
            self._draw_humanoid_monster(surf, cx, cy, size, color, dark_color, light_color, scale, is_boss)

        # Boss aura
        if is_boss:
            aura_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            for i in range(5):
                alpha = 30 - i * 5
                pygame.draw.circle(aura_surf, (*PALETTE['red'][:3], alpha),
                                  (cx, cy), int(size * 0.45) + i * 3)
            surf.blit(aura_surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        return surf

    def _draw_humanoid_monster(self, surf, cx, cy, size, color, dark, light, scale, is_boss):
        """Draw a humanoid-shaped monster."""
        # Body
        body_w = int(size * 0.35 * scale)
        body_h = int(size * 0.4 * scale)
        pygame.draw.ellipse(surf, color, (cx - body_w // 2, cy - body_h // 4, body_w, body_h))
        pygame.draw.ellipse(surf, dark, (cx - body_w // 2, cy - body_h // 4, body_w, body_h), 2)

        # Head
        head_r = int(size * 0.18 * scale)
        head_y = cy - int(size * 0.25 * scale)
        pygame.draw.circle(surf, color, (cx, head_y), head_r)
        pygame.draw.circle(surf, dark, (cx, head_y), head_r, 2)

        # Eyes - menacing
        eye_y = head_y - 2
        eye_spacing = int(head_r * 0.6)
        pygame.draw.circle(surf, PALETTE['red'], (cx - eye_spacing, eye_y), 4)
        pygame.draw.circle(surf, PALETTE['red'], (cx + eye_spacing, eye_y), 4)
        pygame.draw.circle(surf, PALETTE['red_light'], (cx - eye_spacing - 1, eye_y - 1), 2)
        pygame.draw.circle(surf, PALETTE['red_light'], (cx + eye_spacing - 1, eye_y - 1), 2)

        # Arms
        arm_y = cy
        pygame.draw.ellipse(surf, color, (cx - body_w, arm_y - 5, body_w // 2, size // 4))
        pygame.draw.ellipse(surf, color, (cx + body_w // 2, arm_y - 5, body_w // 2, size // 4))

        # Weapon for humanoids
        if is_boss:
            # Big weapon
            pygame.draw.polygon(surf, PALETTE['gray_light'], [
                (cx + body_w, cy - size // 4),
                (cx + body_w + 8, cy - size // 4 - 20),
                (cx + body_w + 12, cy - size // 4),
            ])

    def _draw_beast_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a beast-shaped monster (wolf, etc)."""
        body_w = int(size * 0.5 * scale)
        body_h = int(size * 0.25 * scale)

        # Body
        pygame.draw.ellipse(surf, color, (cx - body_w // 2, cy, body_w, body_h))
        pygame.draw.ellipse(surf, dark, (cx - body_w // 2, cy, body_w, body_h), 2)

        # Head
        head_x = cx + body_w // 3
        head_y = cy - 5
        pygame.draw.circle(surf, color, (head_x, head_y), size // 6)

        # Snout
        pygame.draw.ellipse(surf, light, (head_x, head_y - 3, size // 5, size // 10))

        # Eyes
        pygame.draw.circle(surf, PALETTE['gold'], (head_x - 5, head_y - 5), 3)

        # Ears
        pygame.draw.polygon(surf, color, [
            (head_x - 10, head_y - 15), (head_x - 5, head_y - 25), (head_x, head_y - 15)
        ])

        # Legs
        for lx in [cx - body_w // 3, cx - body_w // 6, cx + body_w // 6]:
            pygame.draw.rect(surf, dark, (lx, cy + body_h - 5, 6, 15))

        # Tail
        pygame.draw.arc(surf, color, (cx - body_w, cy - 10, 30, 30), -0.5, 1.5, 4)

    def _draw_spider_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a spider monster."""
        body_r = int(size * 0.15 * scale)

        # Body
        pygame.draw.circle(surf, color, (cx, cy), body_r)
        pygame.draw.circle(surf, color, (cx, cy + body_r), int(body_r * 0.8))

        # Legs (8)
        for i in range(4):
            angle_l = math.pi * 0.3 + i * 0.4
            angle_r = math.pi * 0.7 - i * 0.4
            for angle in [angle_l, -angle_r]:
                lx = cx + int(math.cos(angle) * body_r * 2.5)
                ly = cy + int(math.sin(angle) * body_r * 1.5)
                pygame.draw.line(surf, dark, (cx, cy), (lx, ly), 3)
                pygame.draw.line(surf, dark, (lx, ly), (lx + 5, ly + 10), 2)

        # Eyes (8 small ones)
        for i in range(4):
            for side in [-1, 1]:
                ex = cx + side * (3 + i * 3)
                ey = cy - body_r // 2 + i * 2
                pygame.draw.circle(surf, PALETTE['red'], (ex, ey), 2)

    def _draw_blob_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a slime/blob monster."""
        # Wobbly blob shape
        for i in range(5):
            wobble = math.sin(i * 1.2) * 5
            r = int((size * 0.3 - i * 3) * scale)
            pygame.draw.circle(surf, color, (cx + int(wobble), cy + i * 2), r)

        # Shine
        pygame.draw.circle(surf, light, (cx - 10, cy - 15), 8)
        pygame.draw.circle(surf, (255, 255, 255), (cx - 8, cy - 18), 4)

        # Eyes
        pygame.draw.circle(surf, PALETTE['black'], (cx - 8, cy - 5), 5)
        pygame.draw.circle(surf, PALETTE['black'], (cx + 8, cy - 5), 5)
        pygame.draw.circle(surf, PALETTE['white'], (cx - 6, cy - 7), 2)
        pygame.draw.circle(surf, PALETTE['white'], (cx + 10, cy - 7), 2)

    def _draw_ghost_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a ghost monster."""
        # Transparent ghostly body
        ghost_color = (*color, 180)

        # Body
        body_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(body_surf, ghost_color,
                           (cx - size // 4, cy - size // 3, size // 2, size // 2))

        # Wavy bottom
        for i in range(5):
            wx = cx - size // 4 + i * size // 10
            wy = cy + size // 6 + (i % 2) * 8
            pygame.draw.circle(body_surf, ghost_color, (wx, wy), 10)

        surf.blit(body_surf, (0, 0))

        # Eyes (hollow)
        pygame.draw.circle(surf, PALETTE['black'], (cx - 10, cy - 10), 8)
        pygame.draw.circle(surf, PALETTE['black'], (cx + 10, cy - 10), 8)

        # Mouth
        pygame.draw.ellipse(surf, PALETTE['black'], (cx - 6, cy + 5, 12, 8))

    def _draw_demon_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a demon monster."""
        self._draw_humanoid_monster(surf, cx, cy, size, color, dark, light, scale, False)

        # Horns
        horn_color = (60, 40, 40)
        pygame.draw.polygon(surf, horn_color, [
            (cx - 15, cy - size // 3),
            (cx - 25, cy - size // 2),
            (cx - 10, cy - size // 3),
        ])
        pygame.draw.polygon(surf, horn_color, [
            (cx + 15, cy - size // 3),
            (cx + 25, cy - size // 2),
            (cx + 10, cy - size // 3),
        ])

        # Wings
        wing_color = (100, 30, 30)
        pygame.draw.polygon(surf, wing_color, [
            (cx - 20, cy - 10),
            (cx - 45, cy - 30),
            (cx - 40, cy + 10),
            (cx - 20, cy + 5),
        ])
        pygame.draw.polygon(surf, wing_color, [
            (cx + 20, cy - 10),
            (cx + 45, cy - 30),
            (cx + 40, cy + 10),
            (cx + 20, cy + 5),
        ])

    def _draw_bat_monster(self, surf, cx, cy, size, color, dark, light, scale):
        """Draw a bat monster."""
        # Body
        pygame.draw.ellipse(surf, color, (cx - 10, cy - 5, 20, 25))

        # Head
        pygame.draw.circle(surf, color, (cx, cy - 15), 10)

        # Ears
        pygame.draw.polygon(surf, color, [(cx - 8, cy - 20), (cx - 12, cy - 35), (cx - 3, cy - 20)])
        pygame.draw.polygon(surf, color, [(cx + 8, cy - 20), (cx + 12, cy - 35), (cx + 3, cy - 20)])

        # Wings
        wing_points_l = [(cx - 10, cy), (cx - 45, cy - 20), (cx - 40, cy + 15), (cx - 10, cy + 10)]
        wing_points_r = [(cx + 10, cy), (cx + 45, cy - 20), (cx + 40, cy + 15), (cx + 10, cy + 10)]
        pygame.draw.polygon(surf, dark, wing_points_l)
        pygame.draw.polygon(surf, dark, wing_points_r)

        # Eyes
        pygame.draw.circle(surf, PALETTE['red'], (cx - 5, cy - 17), 3)
        pygame.draw.circle(surf, PALETTE['red'], (cx + 5, cy - 17), 3)

    def _draw_dragon_monster(self, surf, cx, cy, size, color, dark, light, scale, is_boss):
        """Draw a dragon monster."""
        s = 1.5 if is_boss else 1.0

        # Body
        body_w = int(50 * s)
        body_h = int(35 * s)
        pygame.draw.ellipse(surf, color, (cx - body_w // 2, cy - 5, body_w, body_h))

        # Neck and head
        pygame.draw.ellipse(surf, color, (cx - 30, cy - 35, 25, 40))
        pygame.draw.circle(surf, color, (cx - 35, cy - 40), int(15 * s))

        # Snout
        pygame.draw.ellipse(surf, light, (cx - 55, cy - 45, 25, 12))

        # Eye
        pygame.draw.circle(surf, PALETTE['gold'], (cx - 40, cy - 45), 5)
        pygame.draw.circle(surf, PALETTE['black'], (cx - 40, cy - 45), 2)

        # Horns
        pygame.draw.polygon(surf, dark, [
            (cx - 30, cy - 50), (cx - 35, cy - 70), (cx - 25, cy - 50)
        ])
        pygame.draw.polygon(surf, dark, [
            (cx - 20, cy - 45), (cx - 18, cy - 60), (cx - 12, cy - 45)
        ])

        # Wings
        wing_h = int(50 * s)
        pygame.draw.polygon(surf, dark, [
            (cx - 10, cy - 10),
            (cx + 30, cy - wing_h),
            (cx + 50, cy - wing_h + 20),
            (cx + 40, cy),
            (cx + 10, cy + 10),
        ])

        # Tail
        pygame.draw.arc(surf, color, (cx + 10, cy, 40, 30), -1, 1, 6)

        # Spikes on back
        for i in range(5):
            sx = cx - 15 + i * 12
            pygame.draw.polygon(surf, dark, [
                (sx, cy - 10), (sx + 5, cy - 25), (sx + 10, cy - 10)
            ])

        # Fire breath for boss
        if is_boss:
            for i in range(8):
                fx = cx - 60 - i * 5
                fy = cy - 40 + random.randint(-5, 5) if 'random' in dir() else cy - 40
                pygame.draw.circle(surf, PALETTE['orange'], (fx, fy), 6 - i // 2)
            pygame.draw.circle(surf, PALETTE['gold'], (cx - 60, cy - 40), 8)

    # ========== BATTLE CHARACTER SPRITES ==========

    def create_battle_character(self, char_id: str, size: int = 96) -> pygame.Surface:
        """Create a larger battle sprite for character."""
        key = f"battle_char_{char_id}_{size}"
        return self.get_or_create(key, self._create_battle_char_impl, char_id, size)

    def _create_battle_char_impl(self, char_id: str, size: int) -> pygame.Surface:
        # Try to load from external assets first
        asset_sprite = self.asset_loader.get_player_sprite(char_id, size)
        if asset_sprite:
            return asset_sprite

        # Fall back to procedural generation
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2 + 10

        char_colors = {
            'warrior': ((120, 120, 130), PALETTE['red'], 'sword_shield'),
            'rogue': ((60, 50, 70), PALETTE['green'], 'daggers'),
            'paladin': ((200, 180, 100), PALETTE['blue'], 'sword_shield'),
            'berserker': ((80, 60, 60), PALETTE['red'], 'axe'),
            'monk': ((180, 140, 100), PALETTE['orange'], 'fists'),
            'gambler': ((50, 100, 50), PALETTE['gold'], 'cards'),
            'vampire': ((40, 30, 50), PALETTE['red'], 'claws'),
            'mage': ((40, 60, 120), PALETTE['cyan'], 'staff'),
            'necromancer': ((60, 40, 80), PALETTE['green'], 'staff'),
            'jester': ((150, 50, 100), PALETTE['gold'], 'cards'),
            'avatar': ((180, 160, 100), PALETTE['white'], 'sword_shield'),
        }

        armor_color, accent, weapon = char_colors.get(char_id, ((100, 100, 100), PALETTE['gray'], 'sword'))
        dark_armor = tuple(max(0, c - 40) for c in armor_color)
        light_armor = tuple(min(255, c + 40) for c in armor_color)

        # Legs
        pygame.draw.rect(surf, dark_armor, (cx - 12, cy + 10, 10, 25))
        pygame.draw.rect(surf, dark_armor, (cx + 2, cy + 10, 10, 25))

        # Body/armor
        pygame.draw.ellipse(surf, armor_color, (cx - 18, cy - 20, 36, 35))
        pygame.draw.ellipse(surf, dark_armor, (cx - 18, cy - 20, 36, 35), 2)

        # Armor detail
        pygame.draw.line(surf, light_armor, (cx, cy - 18), (cx, cy + 10), 2)

        # Arms
        pygame.draw.ellipse(surf, armor_color, (cx - 28, cy - 15, 14, 25))
        pygame.draw.ellipse(surf, armor_color, (cx + 14, cy - 15, 14, 25))

        # Head
        skin = (220, 180, 150)
        pygame.draw.circle(surf, skin, (cx, cy - 30), 14)

        # Face
        pygame.draw.circle(surf, PALETTE['black'], (cx - 5, cy - 32), 2)
        pygame.draw.circle(surf, PALETTE['black'], (cx + 5, cy - 32), 2)

        # Character-specific head gear
        if char_id == 'warrior':
            pygame.draw.arc(surf, PALETTE['gray_light'], (cx - 16, cy - 48, 32, 24), 0, math.pi, 4)
        elif char_id == 'mage' or char_id == 'necromancer':
            pygame.draw.polygon(surf, accent, [(cx, cy - 60), (cx - 14, cy - 40), (cx + 14, cy - 40)])
        elif char_id == 'paladin':
            pygame.draw.arc(surf, PALETTE['gold'], (cx - 16, cy - 48, 32, 24), 0, math.pi, 4)
            pygame.draw.circle(surf, PALETTE['gold'], (cx, cy - 45), 4)
        elif char_id == 'rogue':
            pygame.draw.arc(surf, (40, 35, 50), (cx - 18, cy - 50, 36, 30), 0, math.pi, 5)
        elif char_id == 'vampire':
            # Cape
            pygame.draw.polygon(surf, (30, 20, 40), [
                (cx - 20, cy - 25), (cx - 30, cy + 30), (cx + 30, cy + 30), (cx + 20, cy - 25)
            ])
            # Fangs
            pygame.draw.polygon(surf, (255, 255, 255), [(cx - 3, cy - 22), (cx - 1, cy - 16), (cx + 1, cy - 22)])
            pygame.draw.polygon(surf, (255, 255, 255), [(cx + 1, cy - 22), (cx + 3, cy - 16), (cx + 5, cy - 22)])
        elif char_id == 'jester':
            pygame.draw.circle(surf, PALETTE['pink'], (cx - 14, cy - 45), 8)
            pygame.draw.circle(surf, PALETTE['gold'], (cx + 14, cy - 45), 8)

        # Weapon
        if weapon == 'sword_shield':
            # Sword
            pygame.draw.rect(surf, PALETTE['gray_light'], (cx + 25, cy - 35, 6, 40))
            pygame.draw.polygon(surf, PALETTE['gray_light'], [
                (cx + 28, cy - 35), (cx + 22, cy - 50), (cx + 34, cy - 50)
            ])
            # Shield
            pygame.draw.ellipse(surf, accent, (cx - 40, cy - 20, 20, 30))
            pygame.draw.ellipse(surf, dark_armor, (cx - 40, cy - 20, 20, 30), 2)
        elif weapon == 'daggers':
            pygame.draw.polygon(surf, PALETTE['gray_light'], [
                (cx - 30, cy - 25), (cx - 38, cy - 35), (cx - 25, cy - 28)
            ])
            pygame.draw.polygon(surf, PALETTE['gray_light'], [
                (cx + 30, cy - 25), (cx + 38, cy - 35), (cx + 25, cy - 28)
            ])
        elif weapon == 'axe':
            pygame.draw.rect(surf, (100, 70, 50), (cx + 20, cy - 45, 6, 50))
            pygame.draw.polygon(surf, PALETTE['gray'], [
                (cx + 23, cy - 45), (cx + 10, cy - 55), (cx + 10, cy - 35)
            ])
        elif weapon == 'staff':
            pygame.draw.rect(surf, (100, 70, 50), (cx + 22, cy - 50, 6, 60))
            pygame.draw.circle(surf, accent, (cx + 25, cy - 55), 10)
            pygame.draw.circle(surf, (255, 255, 255), (cx + 25, cy - 55), 5)
        elif weapon == 'fists':
            pygame.draw.circle(surf, skin, (cx - 30, cy - 5), 8)
            pygame.draw.circle(surf, skin, (cx + 30, cy - 5), 8)

        return surf

    # ========== DAMAGE NUMBERS ==========

    def create_damage_number(self, value: int, is_crit: bool = False,
                             is_heal: bool = False, size: int = 24) -> pygame.Surface:
        """Create a floating damage number."""
        font = pygame.font.Font(None, size)

        if is_heal:
            color = PALETTE['green']
            text = f"+{value}"
        elif is_crit:
            color = PALETTE['gold']
            text = f"{value}!"
        else:
            color = PALETTE['white']
            text = str(value)

        # Render with outline
        text_surf = font.render(text, True, color)
        w, h = text_surf.get_size()

        surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)

        # Outline
        outline = font.render(text, True, PALETTE['black'])
        for ox, oy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            surf.blit(outline, (2 + ox, 2 + oy))

        surf.blit(text_surf, (2, 2))
        return surf


# Global sprite generator instance
sprites = SpriteGenerator()
