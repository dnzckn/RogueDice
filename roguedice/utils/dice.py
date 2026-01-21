"""Dice rolling utilities with advanced mechanics."""

import random
import re
from typing import List, Tuple, Optional


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


def roll_formula(
    formula: str,
    special: str = "none",
    momentum: int = 0,
    death_stacks: int = 0,
) -> Tuple[List[int], int, int, dict]:
    """
    Roll dice based on a formula string with special mechanics.

    Supports formats:
    - "2d6" - roll 2 six-sided dice
    - "3d4" - roll 3 four-sided dice
    - "1d12" - roll 1 twelve-sided die
    - "1d6+1d8" - roll 1d6 and 1d8, sum them
    - "2d4+2" - roll 2d4 and add 2

    Special rules:
    - "none" - normal rolling
    - "reroll_ones" - reroll any 1s once
    - "exploding" - on max value, roll again and add
    - "doubles_bonus" - if doubles, double the total
    - "momentum" - add momentum value to roll
    - "random_dice" - random die type (d4, d6, d8, d10, d12, d20)
    - "cursed_fortune" - roll 3d6, 80% keep best 2, 20% keep worst 2

    Args:
        formula: Dice formula string
        special: Special rolling rule
        momentum: Current momentum stacks (for warrior)
        death_stacks: Kills for necromancer die scaling (0-4 = d6/d8/d10/d12/d20)

    Returns:
        Tuple of (individual_rolls, modifier, total, extra_info)
        extra_info contains: rolled_doubles, exploded, cursed, etc.
    """
    rolls = []
    modifier = 0
    extra_info = {
        "rolled_doubles": False,
        "exploded": False,
        "cursed": False,
        "random_die": None,
    }

    # Handle special: random_dice (Jester)
    if special == "random_dice":
        die_types = [4, 6, 8, 10, 12, 20]
        chosen_die = random.choice(die_types)
        extra_info["random_die"] = chosen_die
        formula = f"1d{chosen_die}"

    # Handle death_stacks (Necromancer) - upgrade die size
    if death_stacks > 0 and "1d6" in formula.lower():
        die_progression = [6, 8, 10, 12, 20]
        stack_index = min(death_stacks, len(die_progression) - 1)
        new_die = die_progression[stack_index]
        formula = formula.lower().replace("1d6", f"1d{new_die}")

    # Handle special: cursed_fortune (Gambler)
    if special == "cursed_fortune":
        # Roll 3d6
        three_rolls = [random.randint(1, 6) for _ in range(3)]

        # 80% chance to keep best 2, 20% chance to keep worst 2
        if random.random() < 0.8:
            # Keep best 2
            three_rolls.sort(reverse=True)
            rolls = three_rolls[:2]
        else:
            # Cursed! Keep worst 2
            three_rolls.sort()
            rolls = three_rolls[:2]
            extra_info["cursed"] = True

        total = sum(rolls) + modifier
        return (rolls, modifier, total, extra_info)

    # Parse the formula
    parts = formula.lower().replace(" ", "").split("+")

    for part in parts:
        if "d" in part:
            match = re.match(r"(\d+)d(\d+)", part)
            if match:
                num_dice = int(match.group(1))
                sides = int(match.group(2))

                for _ in range(num_dice):
                    roll = random.randint(1, sides)

                    # Apply reroll_ones rule
                    if special == "reroll_ones" and roll == 1:
                        roll = random.randint(1, sides)

                    # Apply exploding rule
                    if special == "exploding" and roll == sides:
                        extra_info["exploded"] = True
                        # Keep rolling while we hit max
                        while roll == sides:
                            extra_roll = random.randint(1, sides)
                            rolls.append(roll)
                            roll = extra_roll

                    rolls.append(roll)
        else:
            try:
                modifier += int(part)
            except ValueError:
                pass

    # Check for doubles (for doubles_bonus and paladin shield)
    if len(rolls) == 2 and rolls[0] == rolls[1]:
        extra_info["rolled_doubles"] = True

    # Apply momentum bonus
    if special == "momentum" and momentum > 0:
        modifier += momentum

    # Calculate total
    total = sum(rolls) + modifier

    # Apply doubles bonus (Monk) - double the total
    if special == "doubles_bonus" and extra_info["rolled_doubles"]:
        total *= 2

    return (rolls, modifier, total, extra_info)


def roll_for_character(
    character_id: str,
    momentum: int = 0,
    death_stacks: int = 0,
) -> Tuple[List[int], int, int, dict]:
    """
    Roll movement dice for a specific character.

    Args:
        character_id: Character template ID
        momentum: Current momentum stacks
        death_stacks: Kill stacks for necromancer

    Returns:
        Tuple of (individual_rolls, modifier, total, extra_info)
    """
    from ..models.characters import get_character

    character = get_character(character_id)
    return roll_formula(
        character.dice_formula,
        character.dice_special,
        momentum=momentum,
        death_stacks=death_stacks,
    )


def format_roll(rolls: List[int], modifier: int, total: int, extra_info: dict = None) -> str:
    """
    Format a dice roll result as a readable string.

    Args:
        rolls: Individual die results
        modifier: Flat modifier
        total: Total result
        extra_info: Optional extra info dict

    Returns:
        Formatted string like "3+4+2=9" or "3+4+2+2=11"
    """
    roll_str = "+".join(str(r) for r in rolls)

    result = ""
    if modifier > 0:
        result = f"{roll_str}+{modifier}={total}"
    elif modifier < 0:
        result = f"{roll_str}{modifier}={total}"
    else:
        result = f"{roll_str}={total}"

    # Add special indicators
    if extra_info:
        if extra_info.get("exploded"):
            result += " EXPLODED!"
        if extra_info.get("rolled_doubles"):
            result += " DOUBLES!"
        if extra_info.get("cursed"):
            result += " CURSED!"
        if extra_info.get("random_die"):
            result = f"d{extra_info['random_die']}: " + result

    return result


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


# =============================================================================
# FATE POINT DICE MANIPULATION
# =============================================================================

def nudge_roll(rolls: List[int], die_index: int, direction: int, sides: int = 6) -> List[int]:
    """
    Apply Nudge: +1 or -1 to a specific die.

    Args:
        rolls: List of die values
        die_index: Which die to nudge (0-indexed)
        direction: +1 or -1
        sides: Number of sides on the die

    Returns:
        Modified rolls list
    """
    new_rolls = rolls.copy()
    if 0 <= die_index < len(new_rolls):
        new_value = new_rolls[die_index] + direction
        # Clamp to valid range
        new_value = max(1, min(sides, new_value))
        new_rolls[die_index] = new_value
    return new_rolls


def apply_locked_die(rolls: List[int], locked_value: int) -> List[int]:
    """
    Replace one die with the locked value.

    Args:
        rolls: List of die values
        locked_value: The locked die value to apply

    Returns:
        Modified rolls with first die replaced
    """
    new_rolls = rolls.copy()
    if new_rolls:
        new_rolls[0] = locked_value
    return new_rolls


def roll_for_character_with_fate(
    character_id: str,
    momentum: int = 0,
    death_stacks: int = 0,
    locked_die_value: Optional[int] = None,
) -> Tuple[List[int], int, int, dict]:
    """
    Roll movement dice for a character, applying fate point modifiers.

    Args:
        character_id: Character template ID
        momentum: Current momentum stacks
        death_stacks: Kill stacks for necromancer
        locked_die_value: If set, replace first die with this value

    Returns:
        Tuple of (individual_rolls, modifier, total, extra_info)
    """
    rolls, modifier, total, extra_info = roll_for_character(
        character_id, momentum, death_stacks
    )

    # Apply locked die if present
    if locked_die_value is not None and rolls:
        original_first = rolls[0]
        rolls[0] = locked_die_value
        total = total - original_first + locked_die_value
        extra_info["locked_die_used"] = True

    return rolls, modifier, total, extra_info
