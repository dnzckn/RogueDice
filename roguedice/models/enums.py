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


class ItemTheme(Enum):
    """Item themes that provide special combat effects and visuals."""
    NONE = auto()
    CYBERPUNK = auto()   # +gold on kill
    STEAMPUNK = auto()   # +crit chance
    MAGICAL = auto()     # Mana burst (bonus magic damage)
    ELEMENTAL = auto()   # Element-based effects
    ANGELIC = auto()     # Heal on attack
    DEMONIC = auto()     # Spend HP for more damage

    @property
    def color(self) -> tuple:
        """Primary RGB color for this theme."""
        colors = {
            ItemTheme.NONE: (180, 180, 180),
            ItemTheme.CYBERPUNK: (0, 255, 255),      # Cyan/Neon
            ItemTheme.STEAMPUNK: (184, 115, 51),     # Copper/Brass
            ItemTheme.MAGICAL: (148, 103, 255),      # Purple/Arcane
            ItemTheme.ELEMENTAL: (100, 200, 100),    # Green (varies by element)
            ItemTheme.ANGELIC: (255, 215, 100),      # Golden/Holy
            ItemTheme.DEMONIC: (180, 30, 60),        # Dark red
        }
        return colors.get(self, (180, 180, 180))

    @property
    def display_name(self) -> str:
        """Human-readable theme name."""
        names = {
            ItemTheme.NONE: "",
            ItemTheme.CYBERPUNK: "Cyberpunk",
            ItemTheme.STEAMPUNK: "Steampunk",
            ItemTheme.MAGICAL: "Magical",
            ItemTheme.ELEMENTAL: "Elemental",
            ItemTheme.ANGELIC: "Angelic",
            ItemTheme.DEMONIC: "Demonic",
        }
        return names.get(self, "")


class Element(Enum):
    """Elements for Elemental-themed items."""
    NONE = auto()
    FIRE = auto()      # DoT burn damage
    WATER = auto()     # Flinch (enemy skips attack)
    WIND = auto()      # Attack speed bonus
    EARTH = auto()     # More damage, less speed
    ELECTRIC = auto()  # Paralyze (enemy can't attack)

    @property
    def color(self) -> tuple:
        """RGB color for this element."""
        colors = {
            Element.NONE: (180, 180, 180),
            Element.FIRE: (255, 100, 30),       # Orange-red
            Element.WATER: (50, 150, 255),      # Blue
            Element.WIND: (200, 255, 200),      # Light green
            Element.EARTH: (139, 90, 43),       # Brown
            Element.ELECTRIC: (255, 255, 50),   # Yellow
        }
        return colors.get(self, (180, 180, 180))

    @property
    def display_name(self) -> str:
        """Human-readable element name."""
        names = {
            Element.NONE: "",
            Element.FIRE: "Fire",
            Element.WATER: "Water",
            Element.WIND: "Wind",
            Element.EARTH: "Earth",
            Element.ELECTRIC: "Electric",
        }
        return names.get(self, "")
