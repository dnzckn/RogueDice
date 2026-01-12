"""Game enumerations and constants."""

from enum import Enum, auto


class Rarity(Enum):
    """Item rarity levels."""
    COMMON = 1
    UNCOMMON = 2
    RARE = 3
    EPIC = 4
    LEGENDARY = 5
    MYTHICAL = 6

    @property
    def color(self) -> tuple:
        """RGB color for this rarity."""
        colors = {
            Rarity.COMMON: (200, 200, 200),      # Gray
            Rarity.UNCOMMON: (30, 255, 30),      # Green
            Rarity.RARE: (30, 144, 255),         # Blue
            Rarity.EPIC: (138, 43, 226),         # Purple
            Rarity.LEGENDARY: (255, 165, 0),     # Orange
            Rarity.MYTHICAL: (255, 0, 128),      # Pink/Red
        }
        return colors[self]

    @property
    def multiplier(self) -> float:
        """Stat multiplier for this rarity."""
        multipliers = {
            Rarity.COMMON: 1.0,
            Rarity.UNCOMMON: 1.3,
            Rarity.RARE: 1.7,
            Rarity.EPIC: 2.2,
            Rarity.LEGENDARY: 3.0,
            Rarity.MYTHICAL: 4.0,
        }
        return multipliers[self]


class ItemType(Enum):
    """Types of equippable items."""
    WEAPON = auto()
    ARMOR = auto()
    JEWELRY = auto()


class SquareType(Enum):
    """Types of board squares."""
    EMPTY = auto()
    MONSTER = auto()
    ITEM = auto()
    BLESSING = auto()        # Shrine that grants blessings
    CURSE = auto()           # Bad luck - spawns monsters on random tiles
    CORNER_START = auto()    # Index 0
    CORNER_SHOP = auto()     # Index 10 - Merchant
    CORNER_REST = auto()     # Index 20 - Inn/heal
    CORNER_BOSS = auto()     # Index 30 - Boss spawns after round 20
    SPECIAL = auto()         # Random events


class StatType(Enum):
    """Types of combat statistics."""
    MAX_HP = auto()
    CURRENT_HP = auto()
    DAMAGE = auto()
    ATTACK_SPEED = auto()
    CRIT_CHANCE = auto()
    CRIT_MULTIPLIER = auto()
    TRUE_DAMAGE = auto()
    AREA_DAMAGE = auto()
    LIFE_STEAL = auto()
    DEFENSE = auto()
    RESISTANCE = auto()
    DODGE_CHANCE = auto()
