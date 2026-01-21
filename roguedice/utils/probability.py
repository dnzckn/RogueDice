"""Probability and weighted random utilities."""

import random
from typing import List, TypeVar, Dict
from ..models.enums import Rarity

T = TypeVar('T')


# Rarity weights (balanced for progression)
# Common ~45%, Uncommon ~28%, Rare ~18%, Epic ~6%, Legendary ~2.5%, Mythical ~0.5%
RARITY_WEIGHTS: Dict[Rarity, int] = {
    Rarity.COMMON: 450,
    Rarity.UNCOMMON: 280,
    Rarity.RARE: 180,
    Rarity.EPIC: 60,
    Rarity.LEGENDARY: 25,
    Rarity.MYTHICAL: 5,
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


# =============================================================================
# DICE PROBABILITY CALCULATIONS FOR ROUTE PLANNING
# =============================================================================

def calculate_dice_probabilities(dice_formula: str, special: str = "none",
                                  death_stacks: int = 0) -> Dict[int, float]:
    """
    Calculate the probability distribution for a dice formula.

    Args:
        dice_formula: Dice formula string (e.g., "2d6", "3d4", "1d12")
        special: Special dice rule
        death_stacks: Kill stacks for necromancer die scaling

    Returns:
        Dict mapping total roll value to probability (0.0-1.0)
    """
    import re
    from collections import defaultdict

    # Handle death_stacks (Necromancer) - upgrade die size
    if death_stacks > 0 and "1d6" in dice_formula.lower():
        die_progression = [6, 8, 10, 12, 20]
        stack_index = min(death_stacks, len(die_progression) - 1)
        new_die = die_progression[stack_index]
        dice_formula = dice_formula.lower().replace("1d6", f"1d{new_die}")

    # Handle cursed_fortune (Gambler) - special case
    if special == "cursed_fortune":
        return _calculate_cursed_fortune_probabilities()

    # Handle random_dice (Jester) - average across all die types
    if special == "random_dice":
        return _calculate_random_dice_probabilities()

    # Parse the formula
    parts = dice_formula.lower().replace(" ", "").split("+")
    dice_specs = []  # List of (num_dice, sides)
    modifier = 0

    for part in parts:
        if "d" in part:
            match = re.match(r"(\d+)d(\d+)", part)
            if match:
                num_dice = int(match.group(1))
                sides = int(match.group(2))
                dice_specs.append((num_dice, sides))
        else:
            try:
                modifier += int(part)
            except ValueError:
                pass

    if not dice_specs:
        return {modifier: 1.0}

    # Calculate base probabilities
    probs = _calculate_dice_distribution(dice_specs)

    # Apply special rules
    if special == "reroll_ones":
        probs = _apply_reroll_ones(probs, dice_specs)
    elif special == "exploding":
        probs = _apply_exploding(probs, dice_specs)
    elif special == "doubles_bonus" and len(dice_specs) == 1 and dice_specs[0][0] == 2:
        probs = _apply_doubles_bonus(probs, dice_specs[0][1])

    # Apply modifier
    if modifier != 0:
        new_probs = {}
        for value, prob in probs.items():
            new_probs[value + modifier] = prob
        probs = new_probs

    return probs


def _calculate_dice_distribution(dice_specs: List[tuple]) -> Dict[int, float]:
    """Calculate probability distribution for multiple dice."""
    from collections import defaultdict

    # Start with 100% chance of 0
    current = {0: 1.0}

    for num_dice, sides in dice_specs:
        for _ in range(num_dice):
            new_probs = defaultdict(float)
            prob_per_face = 1.0 / sides
            for current_val, current_prob in current.items():
                for face in range(1, sides + 1):
                    new_probs[current_val + face] += current_prob * prob_per_face
            current = dict(new_probs)

    return current


def _apply_reroll_ones(probs: Dict[int, float], dice_specs: List[tuple]) -> Dict[int, float]:
    """Apply reroll_ones rule - slightly increases average."""
    from collections import defaultdict

    new_probs = defaultdict(float)

    for num_dice, sides in dice_specs:
        die_probs = {}
        # After rerolling 1: P(1) = 1/sides^2, P(x>1) = (sides+1)/sides^2
        die_probs[1] = 1.0 / (sides * sides)
        for face in range(2, sides + 1):
            die_probs[face] = (sides + 1) / (sides * sides)

        if not new_probs:
            new_probs = dict(die_probs)
        else:
            combined = defaultdict(float)
            for v1, p1 in new_probs.items():
                for v2, p2 in die_probs.items():
                    combined[v1 + v2] += p1 * p2
            new_probs = dict(combined)

    total = sum(new_probs.values())
    if abs(total - 1.0) > 0.001:
        new_probs = {k: v / total for k, v in new_probs.items()}

    return new_probs


def _apply_exploding(probs: Dict[int, float], dice_specs: List[tuple]) -> Dict[int, float]:
    """Apply exploding dice rule - max value triggers another roll."""
    from collections import defaultdict

    if len(dice_specs) != 1 or dice_specs[0][0] != 1:
        return probs

    sides = dice_specs[0][1]
    new_probs = defaultdict(float)
    base_prob = 1.0 / sides
    explode_prob = base_prob

    for face in range(1, sides):
        new_probs[face] = base_prob

    # Explosions (cap at 3)
    for extra in range(1, sides):
        new_probs[sides + extra] += explode_prob * base_prob
    for extra in range(1, sides):
        new_probs[sides * 2 + extra] += explode_prob * explode_prob * base_prob
    new_probs[sides * 3] += explode_prob ** 3

    total = sum(new_probs.values())
    return {k: v / total for k, v in new_probs.items()}


def _apply_doubles_bonus(probs: Dict[int, float], sides: int) -> Dict[int, float]:
    """Apply doubles bonus - doubles double the total."""
    from collections import defaultdict

    new_probs = defaultdict(float)
    p_per = 1.0 / (sides * sides)

    for d1 in range(1, sides + 1):
        for d2 in range(1, sides + 1):
            total = d1 + d2
            if d1 == d2:
                new_probs[total * 2] += p_per
            else:
                new_probs[total] += p_per

    return dict(new_probs)


def _calculate_cursed_fortune_probabilities() -> Dict[int, float]:
    """Calculate probabilities for Gambler's cursed fortune (3d6, usually best 2)."""
    from collections import defaultdict

    new_probs = defaultdict(float)
    p_per = 1.0 / (6 * 6 * 6)

    for d1 in range(1, 7):
        for d2 in range(1, 7):
            for d3 in range(1, 7):
                dice = sorted([d1, d2, d3])
                best_2 = dice[1] + dice[2]
                worst_2 = dice[0] + dice[1]
                new_probs[best_2] += p_per * 0.8
                new_probs[worst_2] += p_per * 0.2

    return dict(new_probs)


def _calculate_random_dice_probabilities() -> Dict[int, float]:
    """Calculate average probabilities for Jester's random dice."""
    from collections import defaultdict

    die_types = [4, 6, 8, 10, 12, 20]
    combined = defaultdict(float)

    for die in die_types:
        p_per = 1.0 / die
        p_die = 1.0 / len(die_types)
        for face in range(1, die + 1):
            combined[face] += p_per * p_die

    return dict(combined)


def get_landing_probabilities(
    current_pos: int,
    board_size: int,
    character_id: str,
    momentum: int = 0,
    death_stacks: int = 0
) -> Dict[int, float]:
    """
    Get probability of landing on each square given current position and character.

    Args:
        current_pos: Current board position
        board_size: Total number of squares on board
        character_id: Character template ID
        momentum: Current momentum stacks
        death_stacks: Kill stacks for necromancer

    Returns:
        Dict mapping square index to probability (0.0-1.0)
    """
    from ..models.characters import get_character

    character = get_character(character_id)
    dice_probs = calculate_dice_probabilities(
        character.dice_formula,
        character.dice_special,
        death_stacks
    )

    # Add momentum modifier if applicable
    if character.dice_special == "momentum" and momentum > 0:
        adjusted_probs = {}
        for roll, prob in dice_probs.items():
            adjusted_probs[roll + momentum] = prob
        dice_probs = adjusted_probs

    # Convert to landing positions
    landing_probs = {}
    for roll, prob in dice_probs.items():
        if roll > 0:
            landing_pos = (current_pos + roll) % board_size
            if landing_pos in landing_probs:
                landing_probs[landing_pos] += prob
            else:
                landing_probs[landing_pos] = prob

    return landing_probs


def get_dice_range(character_id: str, momentum: int = 0, death_stacks: int = 0) -> tuple:
    """
    Get the min and max possible roll for a character.

    Returns:
        Tuple of (min_roll, max_roll)
    """
    from ..models.characters import get_character

    character = get_character(character_id)
    probs = calculate_dice_probabilities(
        character.dice_formula,
        character.dice_special,
        death_stacks
    )

    modifier = momentum if character.dice_special == "momentum" else 0
    min_roll = min(probs.keys()) + modifier
    max_roll = max(probs.keys()) + modifier

    return (min_roll, max_roll)
