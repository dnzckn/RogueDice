"""Probability and weighted random utilities."""

import random
from typing import List, TypeVar, Dict
from ..models.enums import Rarity

T = TypeVar('T')


# Rarity weights (exponentially decreasing)
RARITY_WEIGHTS: Dict[Rarity, int] = {
    Rarity.COMMON: 1000,
    Rarity.UNCOMMON: 400,
    Rarity.RARE: 150,
    Rarity.EPIC: 50,
    Rarity.LEGENDARY: 15,
    Rarity.MYTHICAL: 3,
}


def weighted_choice(items: List[T], weights: List[float]) -> T:
    """
    Select an item based on weighted probabilities.

    Args:
        items: List of items to choose from
        weights: Corresponding weights for each item

    Returns:
        Randomly selected item based on weights
    """
    total = sum(weights)
    r = random.uniform(0, total)

    cumulative = 0
    for item, weight in zip(items, weights):
        cumulative += weight
        if r <= cumulative:
            return item

    return items[-1]  # Fallback


def roll_rarity() -> Rarity:
    """
    Roll for item rarity using weighted probabilities.

    Returns:
        Randomly selected Rarity
    """
    items = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    return weighted_choice(items, weights)


def calculate_item_level(current_round: int, variance: int = 3) -> int:
    """
    Calculate item level based on current round.

    Args:
        current_round: Current game round
        variance: Random variance to apply

    Returns:
        Item level (1-20)
    """
    base_level = min(current_round, 20)
    actual_variance = random.randint(-variance, variance)
    return max(1, min(20, base_level + actual_variance))


def scale_stat(base_value: float, level: int, rarity: Rarity) -> float:
    """
    Scale a stat value based on level and rarity.

    Args:
        base_value: Base stat value
        level: Item/monster level (1-20)
        rarity: Item rarity

    Returns:
        Scaled stat value
    """
    # Level scaling: +15% per level
    level_scale = 1.0 + (level - 1) * 0.15

    # Apply rarity multiplier
    return base_value * level_scale * rarity.multiplier
