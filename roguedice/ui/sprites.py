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
from ..models.enums import Rarity, ItemType, SquareType, ItemTheme, Element


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
                # Load and scale - just use requested size directly
                img = self.load_image(path, (size - 8, size - 8))
                if img:
                    # Create surface and center the image
                    surf = pygame.Surface((size, size), pygame.SRCALPHA)
                    surf.blit(img, (4, 4))

                    # Add boss aura
                    if is_boss:
                        self._add_boss_aura(surf, size)

                    return surf
            elif path.is_dir():
                # Check for files in directory
                for subfile in path.glob("*.png"):
                    img = self.load_image(subfile, (size - 8, size - 8))
                    if img:
                        surf = pygame.Surface((size, size), pygame.SRCALPHA)
                        surf.blit(img, (4, 4))
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

    def clear_cache(self, pattern: str = None):
        """Clear sprite cache. If pattern provided, only clear matching keys."""
        if pattern is None:
            self.cache.clear()
        else:
            keys_to_remove = [k for k in self.cache if pattern in k]
            for k in keys_to_remove:
                del self.cache[k]

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
                         level: int, size: int = 64,
                         theme: ItemTheme = None, element: Element = None) -> pygame.Surface:
        """Create a polished item icon."""
        theme_name = theme.name if theme else "NONE"
        element_name = element.name if element else "NONE"
        key = f"item_{item_type.name}_{rarity.name}_{level}_{size}_{theme_name}_{element_name}"
        return self.get_or_create(key, self._create_item_impl, item_type, rarity, level, size, theme, element)

    def _create_item_impl(self, item_type: ItemType, rarity: Rarity,
                          level: int, size: int,
                          item_theme: ItemTheme = None, element: Element = None) -> pygame.Surface:
        # Try to load from external assets first
        asset_icon = self.asset_loader.get_item_icon(item_type, rarity, level, size)
        if asset_icon:
            return asset_icon

        # Fall back to procedural generation with ENHANCED visuals
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        colors = RARITY_SCHEMES.get(rarity, RARITY_SCHEMES[Rarity.COMMON])
        main_color, dark_color, light_color, glow_color = colors

        # Determine tier from level (affects size/complexity)
        # Tier 1: levels 1-5, Tier 2: 6-10, Tier 3: 11-15, Tier 4: 16+
        tier = min(4, (level - 1) // 5 + 1)

        # Determine theme - use ItemTheme if provided, else fall back to rarity-based
        if item_theme and item_theme != ItemTheme.NONE:
            if item_theme == ItemTheme.CYBERPUNK:
                theme = "cyberpunk"
            elif item_theme == ItemTheme.STEAMPUNK:
                theme = "steampunk"
            elif item_theme == ItemTheme.MAGICAL:
                theme = "magical"
            elif item_theme == ItemTheme.ELEMENTAL:
                # Map element to theme string
                if element == Element.FIRE:
                    theme = "fire"
                elif element == Element.WATER:
                    theme = "water"
                elif element == Element.WIND:
                    theme = "wind"
                elif element == Element.EARTH:
                    theme = "earth"
                elif element == Element.ELECTRIC:
                    theme = "electric"
                else:
                    theme = "magical"
            elif item_theme == ItemTheme.ANGELIC:
                theme = "angelic"
            elif item_theme == ItemTheme.DEMONIC:
                theme = "demonic"
            else:
                theme = "normal"
        else:
            # Fallback: determine theme from rarity
            if rarity == Rarity.EPIC:
                theme = "demonic"
            elif rarity == Rarity.LEGENDARY:
                theme = "angelic"
            elif rarity == Rarity.MYTHICAL:
                theme = "chaotic"
            elif rarity == Rarity.RARE:
                theme = "magical"
            else:
                theme = "normal"

        # Draw enhanced glow based on rarity and theme
        self._draw_item_aura(surf, size, rarity, theme, tier)

        # Draw item based on type with tier and theme
        if item_type == ItemType.WEAPON:
            self._draw_enhanced_weapon(surf, size, main_color, dark_color, light_color, tier, theme, rarity)
        elif item_type == ItemType.ARMOR:
            self._draw_enhanced_armor(surf, size, main_color, dark_color, light_color, tier, theme, rarity)
        elif item_type == ItemType.JEWELRY:
            self._draw_enhanced_ring(surf, size, main_color, dark_color, light_color, tier, theme, rarity)
        else:
            self._draw_enhanced_potion(surf, size, main_color, dark_color, light_color, tier, theme, rarity)

        return surf

    def _draw_item_aura(self, surf: pygame.Surface, size: int, rarity: Rarity, theme: str, tier: int):
        """Draw background aura/effects based on rarity and theme."""
        cx, cy = size // 2, size // 2

        if theme == "demonic":
            # Dark flames and sinister glow
            for i in range(5):
                alpha = 50 - i * 10
                pygame.draw.circle(surf, (80, 20, 40, alpha), (cx, cy), size // 2 - i * 3)
            # Flickering dark fire particles
            for i in range(6):
                fx = cx + int(math.sin(i * 1.2) * size * 0.35)
                fy = cy + size // 3 - i * 4
                pygame.draw.circle(surf, (120, 30, 60, 60), (fx, fy), 4 + tier)

        elif theme == "angelic":
            # Holy golden glow with rays
            for i in range(6):
                alpha = 40 - i * 6
                pygame.draw.circle(surf, (255, 220, 150, alpha), (cx, cy), size // 2 - i * 2)
            # Light rays
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = cx + int(math.cos(rad) * size * 0.2)
                y1 = cy + int(math.sin(rad) * size * 0.2)
                x2 = cx + int(math.cos(rad) * size * 0.45)
                y2 = cy + int(math.sin(rad) * size * 0.45)
                pygame.draw.line(surf, (255, 240, 200, 40), (x1, y1), (x2, y2), 2)

        elif theme == "chaotic":
            # Reality-bending multicolor aura
            for i in range(5):
                hue_shift = (i * 60) % 360
                r = int(128 + 127 * math.sin(math.radians(hue_shift)))
                g = int(128 + 127 * math.sin(math.radians(hue_shift + 120)))
                b = int(128 + 127 * math.sin(math.radians(hue_shift + 240)))
                alpha = 35 - i * 6
                pygame.draw.circle(surf, (r, g, b, alpha), (cx, cy), size // 2 - i * 3)
            # Crackling energy
            for i in range(4):
                angle = random.uniform(0, math.pi * 2)
                x1 = cx + int(math.cos(angle) * size * 0.15)
                y1 = cy + int(math.sin(angle) * size * 0.15)
                x2 = cx + int(math.cos(angle + 0.3) * size * 0.4)
                y2 = cy + int(math.sin(angle + 0.3) * size * 0.4)
                pygame.draw.line(surf, (255, 100, 255, 50), (x1, y1), (x2, y2), 1)

        elif theme == "magical":
            # Subtle purple magical glow with runes
            for i in range(4):
                alpha = 30 - i * 7
                pygame.draw.circle(surf, (148, 103, 255, alpha), (cx, cy), size // 2 - i * 4)

        elif theme == "cyberpunk":
            # Neon cyan/magenta glow with circuit patterns
            for i in range(4):
                alpha = 40 - i * 10
                pygame.draw.circle(surf, (0, 255, 255, alpha), (cx, cy), size // 2 - i * 3)
            # Circuit lines
            for i in range(3):
                x1 = cx - size // 3 + i * size // 6
                y1 = cy - size // 4
                x2 = x1 + size // 8
                y2 = y1 + size // 3
                pygame.draw.line(surf, (255, 0, 255, 50), (x1, y1), (x2, y2), 1)
                pygame.draw.circle(surf, (0, 255, 255, 70), (x2, y2), 2)

        elif theme == "steampunk":
            # Copper/brass glow with gear patterns
            for i in range(4):
                alpha = 35 - i * 8
                pygame.draw.circle(surf, (184, 115, 51, alpha), (cx, cy), size // 2 - i * 3)
            # Small gears
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                gx = cx + int(math.cos(rad) * size * 0.3)
                gy = cy + int(math.sin(rad) * size * 0.3)
                pygame.draw.circle(surf, (205, 127, 50, 50), (gx, gy), 3 + tier)

        elif theme == "fire":
            # Orange-red flame aura
            for i in range(5):
                alpha = 45 - i * 9
                pygame.draw.circle(surf, (255, 100, 30, alpha), (cx, cy), size // 2 - i * 3)
            # Flame particles
            for i in range(5):
                fx = cx + int(math.sin(i * 1.5) * size * 0.3)
                fy = cy - size // 4 + i * 3
                pygame.draw.circle(surf, (255, 150, 50, 60), (fx, fy), 3 + tier)

        elif theme == "water":
            # Blue ripple effect
            for i in range(5):
                alpha = 35 - i * 7
                pygame.draw.circle(surf, (50, 150, 255, alpha), (cx, cy), size // 2 - i * 3)
            # Ripple rings
            for i in range(2):
                pygame.draw.circle(surf, (100, 200, 255, 30), (cx, cy), size // 4 + i * 8, 1)

        elif theme == "wind":
            # Light green swirling aura
            for i in range(4):
                alpha = 30 - i * 7
                pygame.draw.circle(surf, (200, 255, 200, alpha), (cx, cy), size // 2 - i * 4)
            # Swirl lines
            for i in range(3):
                angle = i * 2.1
                x1 = cx + int(math.cos(angle) * size * 0.2)
                y1 = cy + int(math.sin(angle) * size * 0.2)
                x2 = cx + int(math.cos(angle + 1) * size * 0.4)
                y2 = cy + int(math.sin(angle + 1) * size * 0.4)
                pygame.draw.line(surf, (150, 255, 150, 50), (x1, y1), (x2, y2), 2)

        elif theme == "earth":
            # Brown rocky aura
            for i in range(4):
                alpha = 35 - i * 8
                pygame.draw.circle(surf, (139, 90, 43, alpha), (cx, cy), size // 2 - i * 3)
            # Rock particles
            for i in range(4):
                rx = cx + int(math.cos(i * 1.6) * size * 0.35)
                ry = cy + int(math.sin(i * 1.6) * size * 0.35)
                pygame.draw.polygon(surf, (100, 70, 30, 60), [
                    (rx, ry - 3), (rx + 3, ry + 2), (rx - 3, ry + 2)
                ])

        elif theme == "electric":
            # Yellow lightning aura
            for i in range(4):
                alpha = 40 - i * 10
                pygame.draw.circle(surf, (255, 255, 50, alpha), (cx, cy), size // 2 - i * 3)
            # Lightning bolts
            for i in range(3):
                angle = i * 2.1
                x1 = cx + int(math.cos(angle) * size * 0.15)
                y1 = cy + int(math.sin(angle) * size * 0.15)
                x2 = cx + int(math.cos(angle + 0.5) * size * 0.35)
                y2 = cy + int(math.sin(angle + 0.5) * size * 0.35)
                x_mid = (x1 + x2) // 2 + random.randint(-3, 3)
                y_mid = (y1 + y2) // 2 + random.randint(-3, 3)
                pygame.draw.line(surf, (255, 255, 100, 70), (x1, y1), (x_mid, y_mid), 1)
                pygame.draw.line(surf, (255, 255, 100, 70), (x_mid, y_mid), (x2, y2), 1)

    def _draw_enhanced_weapon(self, surf: pygame.Surface, size: int,
                              main: Tuple, dark: Tuple, light: Tuple,
                              tier: int, theme: str, rarity: Rarity):
        """Draw an enhanced weapon that scales with tier and changes with theme."""
        cx, cy = size // 2, size // 2

        # Weapon type varies by tier (sword -> greatsword -> demonic blade)
        blade_length = size // 8 + tier * (size // 12)
        blade_width = size // 6 + tier * 2
        guard_width = size // 2 + tier * 4

        # Theme-based blade colors
        if theme == "demonic":
            blade_color = (60, 20, 30)
            blade_edge = (180, 50, 50)
            blade_highlight = (255, 100, 80)
        elif theme == "angelic":
            blade_color = (240, 240, 255)
            blade_edge = (255, 220, 150)
            blade_highlight = (255, 255, 255)
        elif theme == "chaotic":
            blade_color = (80, 40, 120)
            blade_edge = (200, 100, 255)
            blade_highlight = (255, 180, 255)
        elif theme == "magical":
            blade_color = (148, 103, 255)
            blade_edge = (180, 140, 255)
            blade_highlight = (220, 200, 255)
        elif theme == "cyberpunk":
            blade_color = (0, 180, 180)
            blade_edge = (0, 255, 255)
            blade_highlight = (200, 255, 255)
        elif theme == "steampunk":
            blade_color = (140, 90, 40)
            blade_edge = (184, 115, 51)
            blade_highlight = (220, 170, 100)
        elif theme == "fire":
            blade_color = (200, 80, 20)
            blade_edge = (255, 100, 30)
            blade_highlight = (255, 180, 80)
        elif theme == "water":
            blade_color = (40, 120, 200)
            blade_edge = (50, 150, 255)
            blade_highlight = (150, 200, 255)
        elif theme == "wind":
            blade_color = (160, 220, 160)
            blade_edge = (200, 255, 200)
            blade_highlight = (230, 255, 230)
        elif theme == "earth":
            blade_color = (100, 70, 35)
            blade_edge = (139, 90, 43)
            blade_highlight = (180, 140, 100)
        elif theme == "electric":
            blade_color = (200, 200, 50)
            blade_edge = (255, 255, 50)
            blade_highlight = (255, 255, 180)
        else:
            blade_color = (200, 210, 220)
            blade_edge = (150, 160, 170)
            blade_highlight = (240, 245, 255)

        # Draw blade - bigger and more elaborate at higher tiers
        tip_y = size // 10 - tier * 2
        base_y = cy + size // 8

        # Main blade shape
        if tier >= 3:
            # Elaborate blade with curves
            blade_points = [
                (cx, tip_y),
                (cx + blade_width // 2 + tier, cy - size // 6),
                (cx + blade_width // 2, base_y - 5),
                (cx + blade_width // 4, base_y),
                (cx - blade_width // 4, base_y),
                (cx - blade_width // 2, base_y - 5),
                (cx - blade_width // 2 - tier, cy - size // 6),
            ]
        else:
            blade_points = [
                (cx, tip_y),
                (cx + blade_width // 2, cy - size // 8),
                (cx + blade_width // 3, base_y),
                (cx - blade_width // 3, base_y),
                (cx - blade_width // 2, cy - size // 8),
            ]

        pygame.draw.polygon(surf, blade_color, blade_points)
        pygame.draw.polygon(surf, blade_edge, blade_points, 2)

        # Blade center highlight
        pygame.draw.line(surf, blade_highlight, (cx, tip_y + 5), (cx, base_y - 5), 2 + tier // 2)

        # Theme-specific blade decorations
        if theme == "demonic":
            # Serrated edges and evil runes
            for i in range(tier + 2):
                spike_y = tip_y + 10 + i * (size // 10)
                pygame.draw.polygon(surf, (100, 30, 30), [
                    (cx + blade_width // 2 - 2, spike_y),
                    (cx + blade_width // 2 + 4 + tier, spike_y + 4),
                    (cx + blade_width // 2 - 2, spike_y + 8),
                ])
                pygame.draw.polygon(surf, (100, 30, 30), [
                    (cx - blade_width // 2 + 2, spike_y),
                    (cx - blade_width // 2 - 4 - tier, spike_y + 4),
                    (cx - blade_width // 2 + 2, spike_y + 8),
                ])
            # Glowing rune
            if tier >= 2:
                pygame.draw.circle(surf, (255, 50, 50), (cx, cy - size // 8), 4)
                pygame.draw.circle(surf, (255, 150, 100), (cx, cy - size // 8), 2)

        elif theme == "angelic":
            # Wing motifs and holy symbols
            wing_y = cy - size // 6
            if tier >= 2:
                # Small wing decorations on blade
                pygame.draw.ellipse(surf, (255, 240, 200), (cx - blade_width, wing_y - 3, blade_width // 2, 8))
                pygame.draw.ellipse(surf, (255, 240, 200), (cx + blade_width // 2, wing_y - 3, blade_width // 2, 8))
            # Holy gem
            if tier >= 3:
                pygame.draw.circle(surf, (255, 255, 200), (cx, cy - size // 8), 5)
                pygame.draw.circle(surf, (255, 255, 255), (cx - 1, cy - size // 8 - 1), 2)

        elif theme == "chaotic":
            # Crackling energy along blade
            for i in range(tier + 1):
                ey = tip_y + 8 + i * (size // 8)
                ex_off = random.randint(-3, 3)
                pygame.draw.circle(surf, (200, 100, 255), (cx + ex_off, ey), 3)
                pygame.draw.circle(surf, (255, 200, 255), (cx + ex_off, ey), 1)

        # Guard - more elaborate at higher tiers
        guard_y = base_y
        if tier >= 3:
            # Ornate curved guard
            pygame.draw.arc(surf, main, (cx - guard_width // 2, guard_y - 5, guard_width, 15), 0, math.pi, 4)
            pygame.draw.circle(surf, light, (cx - guard_width // 2 + 3, guard_y), 4)
            pygame.draw.circle(surf, light, (cx + guard_width // 2 - 3, guard_y), 4)
        else:
            pygame.draw.rect(surf, main, (cx - guard_width // 2, guard_y, guard_width, size // 12))
            pygame.draw.rect(surf, dark, (cx - guard_width // 2, guard_y, guard_width, size // 12), 1)

        # Handle
        handle_height = size // 4
        handle_color = (80, 60, 40) if theme != "demonic" else (40, 20, 20)
        pygame.draw.rect(surf, handle_color, (cx - size // 14, guard_y + size // 12, size // 7, handle_height))
        # Handle wrap
        wrap_color = main if theme != "angelic" else (200, 180, 100)
        for i in range(3):
            wy = guard_y + size // 12 + 4 + i * (handle_height // 4)
            pygame.draw.line(surf, wrap_color, (cx - size // 14, wy), (cx + size // 14, wy), 2)

        # Pommel - gem for higher rarities
        pommel_y = guard_y + size // 12 + handle_height
        pommel_size = 4 + tier
        pygame.draw.circle(surf, main, (cx, pommel_y), pommel_size)
        if rarity.value >= Rarity.RARE.value:
            # Glowing gem
            gem_color = light if theme != "demonic" else (255, 80, 80)
            pygame.draw.circle(surf, gem_color, (cx, pommel_y), pommel_size - 2)
            pygame.draw.circle(surf, (255, 255, 255), (cx - 1, pommel_y - 1), pommel_size // 3)

    def _draw_enhanced_armor(self, surf: pygame.Surface, size: int,
                             main: Tuple, dark: Tuple, light: Tuple,
                             tier: int, theme: str, rarity: Rarity):
        """Draw enhanced armor that scales with tier and theme."""
        cx, cy = size // 2, size // 2

        # Theme-based armor colors
        if theme == "demonic":
            armor_main = (50, 30, 40)
            armor_dark = (30, 15, 25)
            armor_light = (100, 50, 60)
            accent = (180, 50, 50)
        elif theme == "angelic":
            armor_main = (240, 230, 200)
            armor_dark = (200, 180, 140)
            armor_light = (255, 250, 240)
            accent = (255, 220, 100)
        elif theme == "chaotic":
            armor_main = (80, 60, 100)
            armor_dark = (50, 35, 70)
            armor_light = (140, 100, 180)
            accent = (200, 100, 255)
        elif theme == "magical":
            armor_main = (120, 100, 180)
            armor_dark = (80, 60, 140)
            armor_light = (180, 160, 220)
            accent = (148, 103, 255)
        elif theme == "cyberpunk":
            armor_main = (30, 80, 80)
            armor_dark = (20, 50, 50)
            armor_light = (60, 140, 140)
            accent = (0, 255, 255)
        elif theme == "steampunk":
            armor_main = (120, 80, 40)
            armor_dark = (80, 50, 25)
            armor_light = (180, 130, 80)
            accent = (184, 115, 51)
        elif theme == "fire":
            armor_main = (150, 60, 30)
            armor_dark = (100, 40, 20)
            armor_light = (200, 100, 60)
            accent = (255, 100, 30)
        elif theme == "water":
            armor_main = (50, 100, 150)
            armor_dark = (30, 70, 110)
            armor_light = (80, 140, 200)
            accent = (50, 150, 255)
        elif theme == "wind":
            armor_main = (130, 180, 130)
            armor_dark = (90, 140, 90)
            armor_light = (180, 220, 180)
            accent = (200, 255, 200)
        elif theme == "earth":
            armor_main = (100, 70, 50)
            armor_dark = (70, 45, 30)
            armor_light = (140, 100, 70)
            accent = (139, 90, 43)
        elif theme == "electric":
            armor_main = (140, 140, 60)
            armor_dark = (100, 100, 40)
            armor_light = (180, 180, 100)
            accent = (255, 255, 50)
        else:
            armor_main = main
            armor_dark = dark
            armor_light = light
            accent = (180, 160, 140)

        # Armor size scales with tier
        shoulder_width = size // 3 + tier * 3
        body_height = size // 2 + tier * 2

        # Draw shoulders - spiky for demonic, winged for angelic
        shoulder_y = size // 6
        if theme == "demonic" and tier >= 2:
            # Spiked pauldrons
            pygame.draw.polygon(surf, armor_main, [
                (cx - shoulder_width, shoulder_y + 10),
                (cx - shoulder_width - 8 - tier * 2, shoulder_y - 5 - tier * 3),
                (cx - shoulder_width // 2, shoulder_y),
            ])
            pygame.draw.polygon(surf, armor_main, [
                (cx + shoulder_width, shoulder_y + 10),
                (cx + shoulder_width + 8 + tier * 2, shoulder_y - 5 - tier * 3),
                (cx + shoulder_width // 2, shoulder_y),
            ])
        elif theme == "angelic" and tier >= 2:
            # Wing-shaped pauldrons
            pygame.draw.ellipse(surf, armor_light, (cx - shoulder_width - 10, shoulder_y - 5, 20, 15))
            pygame.draw.ellipse(surf, armor_light, (cx + shoulder_width - 10, shoulder_y - 5, 20, 15))

        # Main pauldrons
        pygame.draw.ellipse(surf, armor_main, (cx - shoulder_width, shoulder_y, shoulder_width // 2, size // 5))
        pygame.draw.ellipse(surf, armor_main, (cx + shoulder_width // 2, shoulder_y, shoulder_width // 2, size // 5))
        pygame.draw.ellipse(surf, armor_dark, (cx - shoulder_width, shoulder_y, shoulder_width // 2, size // 5), 2)
        pygame.draw.ellipse(surf, armor_dark, (cx + shoulder_width // 2, shoulder_y, shoulder_width // 2, size // 5), 2)

        # Body/chestplate
        body_points = [
            (cx - shoulder_width + 5, shoulder_y + size // 10),
            (cx + shoulder_width - 5, shoulder_y + size // 10),
            (cx + shoulder_width - 10, cy + size // 10),
            (cx + size // 4, size - size // 5),
            (cx, size - size // 6),
            (cx - size // 4, size - size // 5),
            (cx - shoulder_width + 10, cy + size // 10),
        ]
        pygame.draw.polygon(surf, armor_main, body_points)
        pygame.draw.polygon(surf, armor_dark, body_points, 2)

        # Center detail - varies by theme
        if theme == "demonic":
            # Skull emblem
            skull_y = cy - 5
            pygame.draw.circle(surf, (60, 50, 55), (cx, skull_y), 8 + tier)
            pygame.draw.circle(surf, accent, (cx - 4, skull_y - 2), 2)
            pygame.draw.circle(surf, accent, (cx + 4, skull_y - 2), 2)
            pygame.draw.polygon(surf, accent, [(cx, skull_y + 2), (cx - 2, skull_y + 6), (cx + 2, skull_y + 6)])
        elif theme == "angelic":
            # Holy symbol / cross
            pygame.draw.rect(surf, accent, (cx - 2, cy - 12, 4, 20))
            pygame.draw.rect(surf, accent, (cx - 8, cy - 6, 16, 4))
            pygame.draw.circle(surf, (255, 255, 255), (cx, cy - 8), 3)
        elif theme == "chaotic":
            # Swirling void
            for i in range(3):
                r = 6 + i * 3
                pygame.draw.circle(surf, (100 + i * 30, 50 + i * 20, 150 + i * 20), (cx, cy - 3), r, 1)
        else:
            # Simple line detail
            pygame.draw.line(surf, armor_light, (cx, shoulder_y + size // 8), (cx, size - size // 4), 2)

        # Collar/neck guard
        pygame.draw.ellipse(surf, armor_dark, (cx - size // 6, size // 8, size // 3, size // 8))

        # Highlight on chest
        pygame.draw.arc(surf, armor_light, (cx - size // 5, shoulder_y + size // 12, size // 2.5, size // 4), 0.5, 2.6, 2)

        # Extra details for high tier
        if tier >= 3:
            # Belt/waist detail
            pygame.draw.rect(surf, armor_dark, (cx - size // 4, cy + size // 8, size // 2, 6))
            pygame.draw.circle(surf, accent, (cx, cy + size // 8 + 3), 4)

    def _draw_enhanced_ring(self, surf: pygame.Surface, size: int,
                            main: Tuple, dark: Tuple, light: Tuple,
                            tier: int, theme: str, rarity: Rarity):
        """Draw enhanced ring/jewelry with tier and theme effects."""
        cx, cy = size // 2, size // 2

        # Theme-based colors
        if theme == "demonic":
            band_color = (50, 30, 35)
            gem_color = (200, 50, 50)
            gem_glow = (255, 100, 80)
        elif theme == "angelic":
            band_color = (255, 240, 200)
            gem_color = (255, 255, 220)
            gem_glow = (255, 255, 150)
        elif theme == "chaotic":
            band_color = (100, 60, 140)
            gem_color = (200, 100, 255)
            gem_glow = (255, 150, 255)
        elif theme == "magical":
            band_color = (120, 100, 180)
            gem_color = (148, 103, 255)
            gem_glow = (200, 170, 255)
        elif theme == "cyberpunk":
            band_color = (40, 60, 60)
            gem_color = (0, 255, 255)
            gem_glow = (100, 255, 255)
        elif theme == "steampunk":
            band_color = (140, 100, 50)
            gem_color = (184, 115, 51)
            gem_glow = (220, 170, 100)
        elif theme == "fire":
            band_color = (120, 50, 20)
            gem_color = (255, 100, 30)
            gem_glow = (255, 150, 80)
        elif theme == "water":
            band_color = (40, 80, 120)
            gem_color = (50, 150, 255)
            gem_glow = (100, 200, 255)
        elif theme == "wind":
            band_color = (100, 150, 100)
            gem_color = (200, 255, 200)
            gem_glow = (220, 255, 220)
        elif theme == "earth":
            band_color = (80, 55, 35)
            gem_color = (139, 90, 43)
            gem_glow = (180, 140, 100)
        elif theme == "electric":
            band_color = (100, 100, 40)
            gem_color = (255, 255, 50)
            gem_glow = (255, 255, 150)
        else:
            band_color = main
            gem_color = light
            gem_glow = (255, 255, 255)

        # Ring band - more ornate at higher tiers
        band_width = size * 2 // 3 + tier * 2
        band_height = size * 2 // 5 + tier

        # Main band
        pygame.draw.ellipse(surf, dark, (cx - band_width // 2, cy - band_height // 4, band_width, band_height))
        pygame.draw.ellipse(surf, band_color, (cx - band_width // 2 + 2, cy - band_height // 4 + 2, band_width - 4, band_height - 4))
        pygame.draw.ellipse(surf, PALETTE['panel_bg'], (cx - band_width // 3, cy - band_height // 8, band_width * 2 // 3, band_height // 2))

        # Decorative band details for high tier
        if tier >= 2:
            # Side gems or decorations
            pygame.draw.circle(surf, gem_glow, (cx - band_width // 3, cy), 3)
            pygame.draw.circle(surf, gem_glow, (cx + band_width // 3, cy), 3)

        # Main gem - size based on tier
        gem_radius = size // 6 + tier * 2
        gem_y = cy - band_height // 4 - gem_radius // 2

        # Gem glow
        for i in range(3):
            glow_alpha = 60 - i * 20
            pygame.draw.circle(surf, (*gem_glow[:3], glow_alpha), (cx, gem_y), gem_radius + 4 - i * 2)

        # Gem shape varies by theme
        if theme == "demonic":
            # Evil eye gem
            pygame.draw.ellipse(surf, gem_color, (cx - gem_radius, gem_y - gem_radius // 2, gem_radius * 2, gem_radius))
            pygame.draw.ellipse(surf, (40, 20, 20), (cx - gem_radius // 3, gem_y - gem_radius // 4, gem_radius * 2 // 3, gem_radius // 2))
            pygame.draw.circle(surf, (255, 50, 50), (cx, gem_y), 2)
        elif theme == "angelic":
            # Brilliant cut diamond
            points = []
            for i in range(8):
                angle = i * math.pi / 4 - math.pi / 8
                r = gem_radius if i % 2 == 0 else gem_radius * 0.7
                points.append((cx + int(math.cos(angle) * r), gem_y + int(math.sin(angle) * r)))
            pygame.draw.polygon(surf, gem_color, points)
            pygame.draw.polygon(surf, (255, 255, 255), points, 1)
            # Inner sparkle
            pygame.draw.circle(surf, (255, 255, 255), (cx - 2, gem_y - 2), gem_radius // 3)
        elif theme == "chaotic":
            # Void gem
            pygame.draw.circle(surf, (30, 10, 40), (cx, gem_y), gem_radius)
            pygame.draw.circle(surf, gem_color, (cx, gem_y), gem_radius, 2)
            # Swirling energy
            for i in range(3):
                angle = i * math.pi * 2 / 3
                ex = cx + int(math.cos(angle) * gem_radius // 2)
                ey = gem_y + int(math.sin(angle) * gem_radius // 2)
                pygame.draw.circle(surf, gem_glow, (ex, ey), 2)
        else:
            # Standard gem
            pygame.draw.circle(surf, gem_color, (cx, gem_y), gem_radius)
            pygame.draw.circle(surf, dark, (cx, gem_y), gem_radius, 1)
            # Highlight
            pygame.draw.circle(surf, (255, 255, 255), (cx - gem_radius // 3, gem_y - gem_radius // 3), gem_radius // 3)

        # Prongs holding gem
        if tier >= 2:
            pygame.draw.line(surf, band_color, (cx - gem_radius + 2, gem_y + gem_radius // 2), (cx - gem_radius + 2, gem_y), 2)
            pygame.draw.line(surf, band_color, (cx + gem_radius - 2, gem_y + gem_radius // 2), (cx + gem_radius - 2, gem_y), 2)

    def _draw_enhanced_potion(self, surf: pygame.Surface, size: int,
                              main: Tuple, dark: Tuple, light: Tuple,
                              tier: int, theme: str, rarity: Rarity):
        """Draw enhanced potion with tier and theme effects."""
        cx, cy = size // 2, size // 2

        # Theme-based liquid colors
        if theme == "demonic":
            liquid = (150, 30, 50)
            liquid_light = (200, 80, 100)
            bottle_tint = (60, 40, 50)
        elif theme == "angelic":
            liquid = (255, 240, 180)
            liquid_light = (255, 255, 220)
            bottle_tint = (240, 230, 210)
        elif theme == "chaotic":
            liquid = (150, 80, 200)
            liquid_light = (200, 150, 255)
            bottle_tint = (100, 80, 120)
        elif theme == "magical":
            liquid = (80, 150, 220)
            liquid_light = (150, 200, 255)
            bottle_tint = (100, 120, 150)
        else:
            liquid = main
            liquid_light = light
            bottle_tint = (200, 200, 210)

        # Bottle size scales with tier
        bottle_width = size // 2 + tier * 2
        bottle_height = size // 2 + tier * 2
        bottle_y = cy

        # Bottle body
        pygame.draw.ellipse(surf, bottle_tint, (cx - bottle_width // 2, bottle_y, bottle_width, bottle_height - 4))
        pygame.draw.ellipse(surf, dark, (cx - bottle_width // 2, bottle_y, bottle_width, bottle_height - 4), 2)

        # Liquid fill
        liquid_rect = (cx - bottle_width // 2 + 4, bottle_y + 8, bottle_width - 8, bottle_height - 16)
        pygame.draw.ellipse(surf, liquid, liquid_rect)

        # Liquid bubbles
        for i in range(tier + 1):
            bx = cx - bottle_width // 4 + i * (bottle_width // 3)
            by = bottle_y + bottle_height // 3 + (i % 2) * 8
            pygame.draw.circle(surf, liquid_light, (bx, by), 3)

        # Liquid shine
        pygame.draw.ellipse(surf, liquid_light, (cx - bottle_width // 4, bottle_y + 10, bottle_width // 3, bottle_height // 4))

        # Bottle neck
        neck_width = size // 5
        neck_height = size // 4
        pygame.draw.rect(surf, bottle_tint, (cx - neck_width // 2, bottle_y - neck_height + 5, neck_width, neck_height))
        pygame.draw.rect(surf, dark, (cx - neck_width // 2, bottle_y - neck_height + 5, neck_width, neck_height), 1)

        # Cork
        cork_color = (120, 80, 50) if theme != "demonic" else (60, 40, 30)
        pygame.draw.rect(surf, cork_color, (cx - neck_width // 2 - 2, bottle_y - neck_height - 2, neck_width + 4, size // 8))

        # Theme-specific effects
        if theme == "demonic":
            # Smoke wisps
            for i in range(3):
                sy = bottle_y - neck_height - 8 - i * 6
                sx = cx + int(math.sin(i * 1.5) * 5)
                pygame.draw.circle(surf, (80, 40, 60, 100), (sx, sy), 4 - i)
            # Skull on bottle
            if tier >= 2:
                pygame.draw.circle(surf, (80, 60, 70), (cx, bottle_y + bottle_height // 3), 6)
                pygame.draw.circle(surf, (40, 20, 30), (cx - 2, bottle_y + bottle_height // 3 - 1), 1)
                pygame.draw.circle(surf, (40, 20, 30), (cx + 2, bottle_y + bottle_height // 3 - 1), 1)

        elif theme == "angelic":
            # Sparkles around bottle
            for i in range(4):
                angle = i * math.pi / 2 + math.pi / 4
                sx = cx + int(math.cos(angle) * (bottle_width // 2 + 5))
                sy = bottle_y + bottle_height // 3 + int(math.sin(angle) * 10)
                self._draw_sparkle(surf, sx, sy, 4)
            # Halo above cork
            if tier >= 2:
                pygame.draw.ellipse(surf, (255, 240, 150), (cx - 8, bottle_y - neck_height - 12, 16, 6), 1)

        elif theme == "chaotic":
            # Reality distortion
            for i in range(3):
                pygame.draw.circle(surf, (150, 100, 200, 50), (cx + (i - 1) * 8, bottle_y + bottle_height // 2), bottle_width // 4 - i * 3, 1)

        # Label for high tier
        if tier >= 3:
            label_color = main if theme == "normal" else (200, 180, 150)
            pygame.draw.rect(surf, label_color, (cx - bottle_width // 3, bottle_y + bottle_height // 2 - 4, bottle_width * 2 // 3, 10))
            pygame.draw.rect(surf, dark, (cx - bottle_width // 3, bottle_y + bottle_height // 2 - 4, bottle_width * 2 // 3, 10), 1)

    def _draw_sparkle(self, surf: pygame.Surface, x: int, y: int, size: int):
        """Draw a sparkle/star effect."""
        pygame.draw.line(surf, (255, 255, 255), (x - size, y), (x + size, y), 1)
        pygame.draw.line(surf, (255, 255, 255), (x, y - size), (x, y + size), 1)
        pygame.draw.line(surf, (255, 255, 200), (x - size // 2, y - size // 2), (x + size // 2, y + size // 2), 1)
        pygame.draw.line(surf, (255, 255, 200), (x + size // 2, y - size // 2), (x - size // 2, y + size // 2), 1)

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
                          has_monster: bool = False, has_player: bool = False,
                          square_index: int = -1) -> pygame.Surface:
        """Create a polished board tile."""
        key = f"tile_{size}_{square_type.name}_{has_monster}_{has_player}_{square_index}"
        return self.get_or_create(key, self._create_tile_impl, size, square_type, has_monster, has_player, square_index)

    def _create_tile_impl(self, size: int, square_type: SquareType,
                          has_monster: bool, has_player: bool, square_index: int) -> pygame.Surface:
        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        # Map square types to floor tile types
        type_to_floor = {
            SquareType.EMPTY: 'empty',
            SquareType.MONSTER: 'monster',
            SquareType.ITEM: 'item',
            SquareType.BLESSING: 'blessing',
            SquareType.CURSE: 'curse',
            SquareType.CORNER_START: 'start',
            SquareType.CORNER_SHOP: 'shop',
            SquareType.CORNER_REST: 'rest',
            SquareType.CORNER_BOSS: 'boss',
            SquareType.SPECIAL: 'special',
            SquareType.ARCADE: 'arcade',
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
            # Color coding: Red=danger, Blue=loot, Green=safe, Purple=magic, Yellow=shop
            type_colors = {
                SquareType.EMPTY: ((60, 70, 60), (45, 55, 45)),           # Gray-green (safe path)
                SquareType.MONSTER: ((80, 40, 40), (60, 25, 25)),         # Dark red (danger zone)
                SquareType.ITEM: ((40, 60, 90), (25, 40, 70)),            # Blue (loot)
                SquareType.BLESSING: ((70, 50, 100), (50, 35, 80)),       # Purple (magic buff)
                SquareType.CURSE: ((50, 30, 60), (35, 20, 45)),           # Dark purple (bad magic)
                SquareType.CORNER_START: ((50, 80, 50), (35, 60, 35)),    # Green (safe start)
                SquareType.CORNER_SHOP: ((100, 85, 40), (80, 65, 25)),    # Gold (shop)
                SquareType.CORNER_REST: ((40, 70, 90), (25, 50, 70)),     # Blue (healing)
                SquareType.CORNER_BOSS: ((100, 30, 30), (80, 20, 20)),    # Bright red (boss)
                SquareType.SPECIAL: ((80, 60, 100), (60, 45, 80)),        # Purple (random)
                SquareType.ARCADE: ((30, 90, 90), (20, 70, 70)),          # Cyan (arcade minigames)
            }

            main_color, dark_color = type_colors.get(square_type, (PALETTE['gray'], PALETTE['gray_dark']))

            # Tile base with slight 3D effect
            pygame.draw.rect(surf, dark_color, (0, 0, size, size))
            pygame.draw.rect(surf, main_color, (2, 2, size - 4, size - 4))
            # Highlight edge
            pygame.draw.line(surf, tuple(min(255, c + 30) for c in main_color), (2, 2), (size - 3, 2), 1)
            pygame.draw.line(surf, tuple(min(255, c + 30) for c in main_color), (2, 2), (2, size - 3), 1)

        # Border - color coded for quick identification
        border_colors = {
            SquareType.MONSTER: (180, 60, 60),      # Red border
            SquareType.ITEM: (80, 140, 200),        # Blue border
            SquareType.BLESSING: (180, 140, 220),   # Light purple
            SquareType.CURSE: (100, 50, 120),       # Dark purple
            SquareType.CORNER_SHOP: (200, 170, 80), # Gold
            SquareType.CORNER_REST: (100, 180, 220),# Cyan
            SquareType.CORNER_BOSS: (220, 80, 80),  # Bright red
            SquareType.ARCADE: (0, 220, 220),       # Bright cyan (arcade)
        }
        border_color = border_colors.get(square_type, PALETTE['black'])
        pygame.draw.rect(surf, border_color, (0, 0, size, size), 2)

        # Type indicator icons - INTUITIVE VISUAL DESIGN
        cx, cy = size // 2, size // 2

        if square_type == SquareType.MONSTER:
            # MONSTER square = has monster = show skull with red glow
            # (Squares revert to EMPTY when monsters cleared, so MONSTER type always has monsters)
            pygame.draw.circle(surf, (200, 50, 50, 100), (cx, cy), 14)  # Red glow
            skull_color = (240, 240, 230)
            eye_color = (30, 30, 30)

            # Draw skull
            pygame.draw.circle(surf, skull_color, (cx, cy - 2), 9)
            pygame.draw.circle(surf, eye_color, (cx - 3, cy - 4), 2)  # Left eye
            pygame.draw.circle(surf, eye_color, (cx + 3, cy - 4), 2)  # Right eye
            pygame.draw.polygon(surf, eye_color, [(cx - 1, cy), (cx + 1, cy), (cx, cy + 2)])  # Nose
            pygame.draw.rect(surf, skull_color, (cx - 5, cy + 4, 10, 5))  # Jaw
            # Teeth marks
            for i in range(-4, 5, 2):
                pygame.draw.line(surf, eye_color, (cx + i, cy + 4), (cx + i, cy + 8), 1)

        elif square_type == SquareType.ITEM:
            # TREASURE CHEST: Blue glow + chest = LOOT!
            pygame.draw.circle(surf, (60, 100, 150, 80), (cx, cy), 12)
            # Chest body
            pygame.draw.rect(surf, (160, 110, 60), (cx - 8, cy - 4, 16, 11))
            pygame.draw.rect(surf, (120, 80, 40), (cx - 8, cy - 4, 16, 11), 1)
            # Chest lid
            pygame.draw.rect(surf, (180, 130, 70), (cx - 9, cy - 7, 18, 4))
            # Lock/clasp
            pygame.draw.rect(surf, PALETTE['gold'], (cx - 2, cy, 4, 4))
            pygame.draw.circle(surf, PALETTE['gold'], (cx, cy - 1), 2)

        elif square_type == SquareType.BLESSING:
            # SHRINE: Star with glow = BUFF!
            pygame.draw.circle(surf, (140, 100, 180, 80), (cx, cy), 12)
            self._draw_star(surf, cx, cy, 9, PALETTE['gold'])
            # Small + sign to indicate buff
            pygame.draw.line(surf, (200, 255, 200), (cx - 12, cy), (cx - 8, cy), 2)
            pygame.draw.line(surf, (200, 255, 200), (cx - 10, cy - 2), (cx - 10, cy + 2), 2)

        elif square_type == SquareType.CURSE:
            # CURSE: Skull with purple aura = BAD STUFF HAPPENS!
            pygame.draw.circle(surf, (80, 40, 100, 100), (cx, cy), 14)
            # Cracked skull (evil)
            pygame.draw.circle(surf, (140, 120, 160), (cx, cy - 1), 8)
            pygame.draw.circle(surf, (60, 20, 80), (cx - 3, cy - 3), 2)  # Left eye
            pygame.draw.circle(surf, (60, 20, 80), (cx + 3, cy - 3), 2)  # Right eye
            # Crack line
            pygame.draw.line(surf, (60, 20, 80), (cx, cy - 8), (cx + 2, cy + 2), 1)
            # Warning symbol below
            pygame.draw.polygon(surf, (180, 100, 180), [(cx, cy + 6), (cx - 4, cy + 12), (cx + 4, cy + 12)])
            pygame.draw.line(surf, (60, 20, 80), (cx, cy + 7), (cx, cy + 10), 1)

        elif square_type == SquareType.CORNER_SHOP:
            # MERCHANT: Coin/gold sack = BUY STUFF!
            pygame.draw.circle(surf, (180, 150, 60, 80), (cx, cy), 14)
            # Gold coin
            pygame.draw.circle(surf, PALETTE['gold'], (cx, cy), 11)
            pygame.draw.circle(surf, PALETTE['gold_dark'], (cx, cy), 11, 2)
            pygame.draw.circle(surf, PALETTE['gold_light'], (cx - 3, cy - 3), 4)
            # $ symbol
            pygame.draw.line(surf, PALETTE['gold_dark'], (cx, cy - 6), (cx, cy + 6), 2)
            pygame.draw.arc(surf, PALETTE['gold_dark'], (cx - 4, cy - 5, 8, 6), 0.5, 2.5, 2)
            pygame.draw.arc(surf, PALETTE['gold_dark'], (cx - 4, cy, 8, 6), 3.5, 5.8, 2)

        elif square_type == SquareType.CORNER_REST:
            # INN: Heart = HEAL!
            pygame.draw.circle(surf, (100, 180, 220, 80), (cx, cy), 14)
            self._draw_heart(surf, cx, cy, 11)
            # + symbol to indicate healing
            pygame.draw.line(surf, (255, 255, 255), (cx - 3, cy), (cx + 3, cy), 2)
            pygame.draw.line(surf, (255, 255, 255), (cx, cy - 3), (cx, cy + 3), 2)

        elif square_type == SquareType.CORNER_BOSS:
            # BOSS ARENA: Crown with fire = BIG FIGHT!
            pygame.draw.circle(surf, (200, 60, 60, 100), (cx, cy), 14)
            self._draw_crown(surf, cx, cy - 2, 13)
            # Fire particles below crown
            for i in range(-4, 5, 3):
                pygame.draw.polygon(surf, (255, 150, 50), [
                    (cx + i, cy + 8), (cx + i - 2, cy + 14), (cx + i + 2, cy + 14)
                ])

        elif square_type == SquareType.CORNER_START:
            # START: Flag = BEGIN HERE!
            # Flag pole
            pygame.draw.line(surf, (100, 80, 60), (cx - 6, cy - 10), (cx - 6, cy + 10), 2)
            # Flag
            pygame.draw.polygon(surf, (80, 180, 80), [(cx - 5, cy - 10), (cx + 8, cy - 5), (cx - 5, cy)])

        elif square_type == SquareType.SPECIAL:
            # SPECIAL: Question mark = RANDOM EVENT!
            pygame.draw.circle(surf, (130, 100, 160, 80), (cx, cy), 12)
            # Big ?
            pygame.draw.circle(surf, (220, 200, 240), (cx, cy - 4), 6, 2)
            pygame.draw.line(surf, (220, 200, 240), (cx + 3, cy - 2), (cx, cy + 3), 2)
            pygame.draw.circle(surf, (220, 200, 240), (cx, cy + 7), 2)

        elif square_type == SquareType.ARCADE:
            # ARCADE: Game controller/joystick = MINIGAME FUN!
            pygame.draw.circle(surf, (0, 180, 180, 100), (cx, cy), 14)
            # Joystick base
            pygame.draw.ellipse(surf, (60, 60, 70), (cx - 10, cy + 2, 20, 8))
            pygame.draw.ellipse(surf, (80, 80, 90), (cx - 8, cy + 3, 16, 6))
            # Joystick stick
            pygame.draw.line(surf, (100, 100, 110), (cx, cy + 5), (cx, cy - 6), 3)
            # Joystick ball top
            pygame.draw.circle(surf, (255, 50, 100), (cx, cy - 8), 5)
            pygame.draw.circle(surf, (255, 150, 180), (cx - 1, cy - 9), 2)
            # Sparkle effects
            pygame.draw.line(surf, (0, 255, 255), (cx - 10, cy - 8), (cx - 7, cy - 8), 1)
            pygame.draw.line(surf, (255, 0, 255), (cx + 7, cy - 10), (cx + 10, cy - 10), 1)
            pygame.draw.circle(surf, (255, 255, 0), (cx + 8, cy - 4), 1)

        # Add small arcade/joystick indicator for corner squares 10, 20, 30 (minigame squares)
        if square_index in (10, 20, 30):
            # Draw small joystick in top-right corner
            ax, ay = size - 10, 10  # Top-right corner position
            # Mini joystick base
            pygame.draw.ellipse(surf, (60, 60, 70), (ax - 5, ay + 1, 10, 4))
            # Mini joystick stick
            pygame.draw.line(surf, (100, 100, 110), (ax, ay + 2), (ax, ay - 3), 2)
            # Mini joystick ball
            pygame.draw.circle(surf, (255, 50, 100), (ax, ay - 4), 3)
            pygame.draw.circle(surf, (255, 150, 180), (ax - 1, ay - 5), 1)
            # Cyan glow around it
            pygame.draw.circle(surf, (0, 180, 180), (ax, ay), 8, 1)

        # Player token (not used since player is drawn separately now)
        if has_player:
            pygame.draw.circle(surf, PALETTE['cyan'], (cx, cy), 12)
            pygame.draw.circle(surf, PALETTE['white'], (cx, cy), 12, 2)

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
        """Draw a dragon monster - properly scaled to fit within size."""
        # Scale factor based on size (designed for 96px base)
        sf = size / 96.0
        s = (1.3 if is_boss else 1.0) * sf

        # Offset to center the dragon properly (dragon design is off-center)
        ox = int(10 * sf)  # Shift right to center
        oy = int(5 * sf)   # Shift down slightly

        # Body
        body_w = int(50 * s)
        body_h = int(35 * s)
        pygame.draw.ellipse(surf, color, (cx - body_w // 2 + ox, cy - int(5 * sf) + oy, body_w, body_h))

        # Neck and head
        pygame.draw.ellipse(surf, color, (cx - int(30 * sf) + ox, cy - int(30 * sf) + oy, int(25 * sf), int(35 * sf)))
        pygame.draw.circle(surf, color, (cx - int(32 * sf) + ox, cy - int(32 * sf) + oy), int(14 * s))

        # Snout
        pygame.draw.ellipse(surf, light, (cx - int(48 * sf) + ox, cy - int(38 * sf) + oy, int(22 * sf), int(10 * sf)))

        # Eye
        pygame.draw.circle(surf, PALETTE['gold'], (cx - int(36 * sf) + ox, cy - int(36 * sf) + oy), int(4 * sf))
        pygame.draw.circle(surf, PALETTE['black'], (cx - int(36 * sf) + ox, cy - int(36 * sf) + oy), int(2 * sf))

        # Horns
        pygame.draw.polygon(surf, dark, [
            (cx - int(28 * sf) + ox, cy - int(42 * sf) + oy),
            (cx - int(32 * sf) + ox, cy - int(55 * sf) + oy),
            (cx - int(23 * sf) + ox, cy - int(42 * sf) + oy)
        ])
        pygame.draw.polygon(surf, dark, [
            (cx - int(18 * sf) + ox, cy - int(38 * sf) + oy),
            (cx - int(16 * sf) + ox, cy - int(48 * sf) + oy),
            (cx - int(10 * sf) + ox, cy - int(38 * sf) + oy)
        ])

        # Wings
        wing_h = int(40 * s)
        pygame.draw.polygon(surf, dark, [
            (cx - int(8 * sf) + ox, cy - int(8 * sf) + oy),
            (cx + int(25 * sf) + ox, cy - wing_h + oy),
            (cx + int(40 * sf) + ox, cy - wing_h + int(18 * sf) + oy),
            (cx + int(32 * sf) + ox, cy + oy),
            (cx + int(8 * sf) + ox, cy + int(8 * sf) + oy),
        ])

        # Tail
        tail_rect = (cx + int(8 * sf) + ox, cy + oy, int(35 * sf), int(25 * sf))
        pygame.draw.arc(surf, color, tail_rect, -1, 1, max(3, int(5 * sf)))

        # Spikes on back
        for i in range(4):
            sx = cx - int(12 * sf) + ox + i * int(10 * sf)
            pygame.draw.polygon(surf, dark, [
                (sx, cy - int(8 * sf) + oy),
                (sx + int(4 * sf), cy - int(20 * sf) + oy),
                (sx + int(8 * sf), cy - int(8 * sf) + oy)
            ])

        # Fire breath for boss
        if is_boss:
            for i in range(6):
                fx = cx - int(52 * sf) + ox - i * int(4 * sf)
                fy = cy - int(35 * sf) + oy + random.randint(-3, 3)
                pygame.draw.circle(surf, PALETTE['orange'], (fx, fy), max(2, int((5 - i // 2) * sf)))
            pygame.draw.circle(surf, PALETTE['gold'], (cx - int(52 * sf) + ox, cy - int(35 * sf) + oy), int(6 * sf))

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
