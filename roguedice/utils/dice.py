"""Dice rolling utilities."""

import random
import re
from typing import List, Tuple


def roll_dice(num_dice: int, sides: int) -> List[int]:
    """
    Roll multiple dice and return individual results.

    Args:
        num_dice: Number of dice to roll
        sides: Number of sides per die

    Returns:
        List of individual die results
    """
    return [random.randint(1, sides) for _ in range(num_dice)]


def roll_d6() -> int:
    """Roll a single d6."""
    return random.randint(1, 6)


def roll_2d6() -> Tuple[int, int, int]:
    """
    Roll 2d6 for movement.

    Returns:
        Tuple of (die1, die2, total)
    """
    die1 = random.randint(1, 6)
    die2 = random.randint(1, 6)
    return (die1, die2, die1 + die2)


def roll_formula(formula: str, special: str = "none") -> Tuple[List[int], int, int]:
    """
    Roll dice based on a formula string.

    Supports formats:
    - "2d6" - roll 2 six-sided dice
    - "3d4" - roll 3 four-sided dice
    - "1d12" - roll 1 twelve-sided die
    - "1d6+1d8" - roll 1d6 and 1d8, sum them
    - "2d4+2" - roll 2d4 and add 2

    Special rules:
    - "none" - normal rolling
    - "reroll_ones" - reroll any 1s once

    Args:
        formula: Dice formula string
        special: Special rolling rule

    Returns:
        Tuple of (individual_rolls, modifier, total)
    """
    rolls = []
    modifier = 0

    # Parse the formula
    # Examples: "2d6", "1d6+1d8", "2d4+2"
    parts = formula.lower().replace(" ", "").split("+")

    for part in parts:
        if "d" in part:
            # It's a dice roll (e.g., "2d6")
            match = re.match(r"(\d+)d(\d+)", part)
            if match:
                num_dice = int(match.group(1))
                sides = int(match.group(2))

                for _ in range(num_dice):
                    roll = random.randint(1, sides)

                    # Apply reroll_ones rule
                    if special == "reroll_ones" and roll == 1:
                        roll = random.randint(1, sides)

                    rolls.append(roll)
        else:
            # It's a flat modifier (e.g., "+2")
            try:
                modifier += int(part)
            except ValueError:
                pass

    total = sum(rolls) + modifier
    return (rolls, modifier, total)


def roll_for_character(character_id: str) -> Tuple[List[int], int, int]:
    """
    Roll movement dice for a specific character.

    Args:
        character_id: Character template ID

    Returns:
        Tuple of (individual_rolls, modifier, total)
    """
    from ..models.characters import get_character

    character = get_character(character_id)
    return roll_formula(character.dice_formula, character.dice_special)


def format_roll(rolls: List[int], modifier: int, total: int) -> str:
    """
    Format a dice roll result as a readable string.

    Args:
        rolls: Individual die results
        modifier: Flat modifier
        total: Total result

    Returns:
        Formatted string like "3+4+2=9" or "3+4+2+2=11"
    """
    roll_str = "+".join(str(r) for r in rolls)
    if modifier > 0:
        return f"{roll_str}+{modifier}={total}"
    elif modifier < 0:
        return f"{roll_str}{modifier}={total}"
    else:
        return f"{roll_str}={total}"


def roll_d20() -> int:
    """Roll a d20."""
    return random.randint(1, 20)


def roll_percent() -> float:
    """Roll a percentage (0.0 to 1.0)."""
    return random.random()


def check_chance(chance: float) -> bool:
    """
    Check if a random roll succeeds against a chance.

    Args:
        chance: Success chance (0.0 to 1.0)

    Returns:
        True if roll succeeds
    """
    return random.random() < chance
