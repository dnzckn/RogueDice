"""Character templates with unique dice mechanics and stats."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class CharacterTemplate:
    """Template defining a playable character."""

    id: str
    name: str
    description: str
    flavor_text: str

    # Dice mechanics
    dice_formula: str  # e.g. "2d6", "3d4", "1d12", "1d6+1d8", "2d4+2"
    dice_special: str  # "none", "reroll_ones", "exploding"
    dice_description: str  # Human-readable dice description

    # Cost to unlock (0 = free starter)
    cost: int

    # Stat multipliers (applied to base stats)
    hp_mult: float = 1.0
    damage_mult: float = 1.0
    crit_chance_mult: float = 1.0
    crit_damage_mult: float = 1.0
    attack_speed_mult: float = 1.0
    defense_mult: float = 1.0
    life_steal_base: float = 0.0  # Flat life steal bonus

    # Special modifiers
    damage_taken_mult: float = 1.0  # >1 = takes more damage
    gold_mult: float = 1.0  # Gold find multiplier
    heal_on_rest_mult: float = 1.0  # Healing at inn multiplier
    can_equip_armor: bool = True

    # Unique traits
    has_spells: bool = False  # Mage special
    lucky_crits: bool = False  # Gambler special - crits deal more

    @property
    def pros(self) -> str:
        """Get summary of character advantages."""
        pros = []
        if self.hp_mult > 1:
            pros.append(f"+{int((self.hp_mult - 1) * 100)}% HP")
        if self.damage_mult > 1:
            pros.append(f"+{int((self.damage_mult - 1) * 100)}% damage")
        if self.crit_chance_mult > 1:
            pros.append(f"+{int((self.crit_chance_mult - 1) * 100)}% crit")
        if self.attack_speed_mult > 1:
            pros.append(f"+{int((self.attack_speed_mult - 1) * 100)}% speed")
        if self.defense_mult > 1:
            pros.append(f"+{int((self.defense_mult - 1) * 100)}% defense")
        if self.life_steal_base > 0:
            pros.append(f"+{int(self.life_steal_base * 100)}% life steal")
        if self.gold_mult > 1:
            pros.append(f"+{int((self.gold_mult - 1) * 100)}% gold")
        if self.heal_on_rest_mult > 1:
            pros.append("bonus healing")
        if self.has_spells:
            pros.append("spell damage")
        if self.lucky_crits:
            pros.append("lucky crits")
        return ", ".join(pros) if pros else "balanced"

    @property
    def cons(self) -> str:
        """Get summary of character disadvantages."""
        cons = []
        if self.hp_mult < 1:
            cons.append(f"-{int((1 - self.hp_mult) * 100)}% HP")
        if self.damage_mult < 1:
            cons.append(f"-{int((1 - self.damage_mult) * 100)}% damage")
        if self.damage_taken_mult > 1:
            cons.append(f"+{int((self.damage_taken_mult - 1) * 100)}% damage taken")
        if not self.can_equip_armor:
            cons.append("no armor")
        # Check for general stat penalty (gambler)
        if (self.hp_mult < 1 and self.damage_mult < 1 and
            self.crit_chance_mult < 1 and self.defense_mult < 1):
            return "-15% all stats"
        return ", ".join(cons) if cons else "none"


# All playable characters
CHARACTERS: Dict[str, CharacterTemplate] = {
    "warrior": CharacterTemplate(
        id="warrior",
        name="Warrior",
        description="A balanced fighter with no weaknesses.",
        flavor_text="The classic hero. Reliable and steady.",
        dice_formula="2d6",
        dice_special="none",
        dice_description="2d6 (2-12, avg 7)",
        cost=0,
        hp_mult=1.1,  # +10% HP
    ),

    "rogue": CharacterTemplate(
        id="rogue",
        name="Rogue",
        description="Fast and deadly with consistent movement.",
        flavor_text="Three dice, more control. Strike fast, strike true.",
        dice_formula="3d4",
        dice_special="none",
        dice_description="3d4 (3-12, avg 7.5, consistent)",
        cost=500,
        hp_mult=0.8,  # -20% HP
        crit_chance_mult=1.15,  # +15% crit
        attack_speed_mult=1.1,  # +10% speed
    ),

    "berserker": CharacterTemplate(
        id="berserker",
        name="Berserker",
        description="High risk, high reward. Embrace the chaos.",
        flavor_text="One die. Maximum variance. Feel the rage.",
        dice_formula="1d12",
        dice_special="none",
        dice_description="1d12 (1-12, avg 6.5, wild)",
        cost=750,
        damage_mult=1.3,  # +30% damage
        life_steal_base=0.1,  # +10% base life steal
        damage_taken_mult=1.25,  # Takes +25% damage
    ),

    "paladin": CharacterTemplate(
        id="paladin",
        name="Paladin",
        description="Slow but steady. The blessed protector.",
        flavor_text="When you roll a 1, roll again. Fortune favors the faithful.",
        dice_formula="2d6",
        dice_special="reroll_ones",
        dice_description="2d6 reroll 1s (2-12, avg 8.2)",
        cost=600,
        damage_mult=0.85,  # -15% damage
        defense_mult=1.2,  # +20% defense
        heal_on_rest_mult=1.5,  # 50% bonus healing at inn
    ),

    "gambler": CharacterTemplate(
        id="gambler",
        name="Gambler",
        description="Lady luck's favorite. High rolls, high stakes.",
        flavor_text="A d6 and a d8. Can you feel it? That's opportunity.",
        dice_formula="1d6+1d8",
        dice_special="none",
        dice_description="1d6+1d8 (2-14, avg 8)",
        cost=800,
        hp_mult=0.85,
        damage_mult=0.85,
        crit_chance_mult=0.85,
        defense_mult=0.85,
        gold_mult=1.3,  # +30% gold
        lucky_crits=True,  # Crits deal 50% more
    ),

    "mage": CharacterTemplate(
        id="mage",
        name="Mage",
        description="Glass cannon. Spells ignore armor.",
        flavor_text="Small dice, but always reliable. Magic finds a way.",
        dice_formula="2d4+2",
        dice_special="none",
        dice_description="2d4+2 (4-10, avg 7, very consistent)",
        cost=1000,
        hp_mult=0.7,  # -30% HP
        can_equip_armor=False,
        has_spells=True,  # Damage ignores defense
    ),
}


def get_character(character_id: str) -> CharacterTemplate:
    """Get a character template by ID."""
    return CHARACTERS.get(character_id, CHARACTERS["warrior"])


def get_unlockable_characters() -> Dict[str, CharacterTemplate]:
    """Get all characters that cost gold to unlock."""
    return {k: v for k, v in CHARACTERS.items() if v.cost > 0}
