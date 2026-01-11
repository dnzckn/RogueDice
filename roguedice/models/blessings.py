"""Blessing definitions and effects."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List
import random
import copy


class BlessingType(Enum):
    """Types of blessing effects."""
    CRIT_BOOST = auto()
    DAMAGE_BOOST = auto()
    DEFENSE_BOOST = auto()
    ATTACK_SPEED = auto()
    LIFE_STEAL = auto()
    MAX_HP = auto()
    GOLD_FIND = auto()
    DODGE = auto()


@dataclass
class Blessing:
    """A blessing effect that can be applied to the player."""

    blessing_type: BlessingType
    name: str
    description: str
    value: float  # The magnitude of the effect
    duration: int  # Rounds remaining, -1 = permanent
    is_permanent: bool = False
    shop_price: int = 75  # Price when bought at merchant

    @property
    def duration_text(self) -> str:
        """Get human-readable duration."""
        if self.is_permanent:
            return "permanent"
        return f"{self.duration} rounds"

    def tick(self) -> bool:
        """
        Decrement duration by 1 round.
        Returns True if blessing is still active, False if expired.
        """
        if self.is_permanent or self.duration == -1:
            return True
        self.duration -= 1
        return self.duration > 0


# All available blessings (templates)
BLESSING_POOL: List[Blessing] = [
    Blessing(
        blessing_type=BlessingType.CRIT_BOOST,
        name="Eagle Eye",
        description="+10% crit chance",
        value=0.10,
        duration=5,
        shop_price=75,
    ),
    Blessing(
        blessing_type=BlessingType.DAMAGE_BOOST,
        name="Warrior's Might",
        description="+15 damage",
        value=15,
        duration=5,
        shop_price=80,
    ),
    Blessing(
        blessing_type=BlessingType.DEFENSE_BOOST,
        name="Stone Skin",
        description="+10 defense",
        value=10,
        duration=5,
        shop_price=70,
    ),
    Blessing(
        blessing_type=BlessingType.ATTACK_SPEED,
        name="Haste",
        description="+25% attack speed",
        value=0.25,
        duration=5,
        shop_price=85,
    ),
    Blessing(
        blessing_type=BlessingType.LIFE_STEAL,
        name="Vampiric Touch",
        description="+10% life steal",
        value=0.10,
        duration=5,
        shop_price=90,
    ),
    Blessing(
        blessing_type=BlessingType.MAX_HP,
        name="Vitality Surge",
        description="+25 max HP",
        value=25,
        duration=-1,
        is_permanent=True,
        shop_price=100,
    ),
    Blessing(
        blessing_type=BlessingType.GOLD_FIND,
        name="Midas Touch",
        description="+50% gold find",
        value=0.50,
        duration=8,
        shop_price=60,
    ),
    Blessing(
        blessing_type=BlessingType.DODGE,
        name="Shadow Step",
        description="+10% dodge chance",
        value=0.10,
        duration=5,
        shop_price=75,
    ),
]

# Higher tier blessings for later rounds or boss victories
RARE_BLESSING_POOL: List[Blessing] = [
    Blessing(
        blessing_type=BlessingType.CRIT_BOOST,
        name="Perfect Focus",
        description="+20% crit chance",
        value=0.20,
        duration=8,
        shop_price=150,
    ),
    Blessing(
        blessing_type=BlessingType.DAMAGE_BOOST,
        name="Titan's Strength",
        description="+30 damage",
        value=30,
        duration=8,
        shop_price=160,
    ),
    Blessing(
        blessing_type=BlessingType.MAX_HP,
        name="Dragon's Vitality",
        description="+50 max HP",
        value=50,
        duration=-1,
        is_permanent=True,
        shop_price=200,
    ),
    Blessing(
        blessing_type=BlessingType.LIFE_STEAL,
        name="Blood Pact",
        description="+20% life steal",
        value=0.20,
        duration=8,
        shop_price=180,
    ),
]


def get_random_blessing(include_rare: bool = False) -> Blessing:
    """
    Get a random blessing from the pool.

    Args:
        include_rare: If True, has 20% chance to get a rare blessing
    """
    if include_rare and random.random() < 0.20:
        template = random.choice(RARE_BLESSING_POOL)
    else:
        template = random.choice(BLESSING_POOL)

    # Return a copy so duration can be modified
    return copy.deepcopy(template)


def get_shop_blessings(count: int = 2, current_round: int = 1) -> List[Blessing]:
    """
    Get blessings available at merchant shop.

    Args:
        count: Number of blessings to generate
        current_round: Current game round (affects rare chance)
    """
    include_rare = current_round >= 10
    blessings = []

    # Avoid duplicates
    available = BLESSING_POOL.copy()
    if include_rare:
        available.extend(RARE_BLESSING_POOL)

    for _ in range(min(count, len(available))):
        template = random.choice(available)
        available.remove(template)
        blessings.append(copy.deepcopy(template))

    return blessings
