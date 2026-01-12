"""Character templates with unique dice mechanics and stats."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CharacterTemplate:
    """Template defining a playable character."""

    id: str
    name: str
    description: str
    flavor_text: str

    # Dice mechanics
    dice_formula: str  # e.g. "2d6", "3d4", "1d12", "1d6+1d8", "2d4+2"
    dice_special: str  # Special dice rule (see DICE_SPECIALS below)
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

    # Unique combat traits
    has_spells: bool = False  # Damage ignores defense
    lucky_crits: bool = False  # Crits deal 50% more damage
    poison_damage: bool = False  # Deals DOT based on movement
    first_strike: bool = False  # Always attacks first in combat
    rage_mode: bool = False  # More damage when low HP
    shield_on_doubles: bool = False  # Gains temp shield on doubles
    vampiric: bool = False  # Heals on movement too
    combo_master: bool = False  # Builds combo stacks for damage
    chaos_rolls: bool = False  # Random dice type each roll
    death_stacks: bool = False  # Stacks power from kills

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
            pros.append("ignores armor")
        if self.lucky_crits:
            pros.append("super crits")
        if self.poison_damage:
            pros.append("poison")
        if self.first_strike:
            pros.append("first strike")
        if self.rage_mode:
            pros.append("rage when hurt")
        if self.shield_on_doubles:
            pros.append("shield on doubles")
        if self.vampiric:
            pros.append("vampiric")
        if self.combo_master:
            pros.append("combo stacks")
        if self.death_stacks:
            pros.append("grows from kills")
        return ", ".join(pros) if pros else "balanced"

    @property
    def cons(self) -> str:
        """Get summary of character disadvantages."""
        cons = []
        if self.hp_mult < 1:
            cons.append(f"-{int((1 - self.hp_mult) * 100)}% HP")
        if self.damage_mult < 1:
            cons.append(f"-{int((1 - self.damage_mult) * 100)}% damage")
        if self.defense_mult < 1:
            cons.append(f"-{int((1 - self.defense_mult) * 100)}% defense")
        if self.damage_taken_mult > 1:
            cons.append(f"+{int((self.damage_taken_mult - 1) * 100)}% damage taken")
        if not self.can_equip_armor:
            cons.append("no armor")
        if self.chaos_rolls:
            cons.append("unpredictable")
        return ", ".join(cons) if cons else "none"


# Dice special rules:
# - "none": Standard roll
# - "reroll_ones": Reroll any 1s once
# - "exploding": On max value, roll again and add
# - "keep_highest": Roll extra dice, keep highest N
# - "doubles_bonus": Doubles give extra movement
# - "momentum": Each consecutive move adds +1 (resets on combat)
# - "random_dice": Random die type each roll (d4-d20)
# - "cursed_fortune": Roll 3d6, usually best 2, sometimes worst 2


# All playable characters
CHARACTERS: Dict[str, CharacterTemplate] = {
    # ========== STARTER ==========
    "warrior": CharacterTemplate(
        id="warrior",
        name="Warrior",
        description="Balanced fighter who builds momentum over time.",
        flavor_text="Each step forward fuels the next. Unstoppable.",
        dice_formula="2d6",
        dice_special="momentum",  # +1 per consecutive non-combat move
        dice_description="2d6 + momentum (builds +1 per move)",
        cost=0,
        hp_mult=1.15,
        defense_mult=1.1,
    ),

    # ========== TIER 1 UNLOCKS (500-600g) ==========
    "rogue": CharacterTemplate(
        id="rogue",
        name="Rogue",
        description="Swift assassin. Poison stacks, strikes first.",
        flavor_text="They never see me coming. They never see me leave.",
        dice_formula="3d4",
        dice_special="none",
        dice_description="3d4 (3-12, very consistent)",
        cost=500,
        hp_mult=0.75,
        crit_chance_mult=1.25,
        attack_speed_mult=1.2,
        poison_damage=True,  # Deals poison = movement roll
        first_strike=True,  # Always attacks first
    ),

    "paladin": CharacterTemplate(
        id="paladin",
        name="Paladin",
        description="Holy warrior. Blessed dice, shields on doubles.",
        flavor_text="The light protects. Roll doubles, feel divine favor.",
        dice_formula="2d6",
        dice_special="reroll_ones",
        dice_description="2d6 reroll 1s (avg 8.2, blessed)",
        cost=600,
        hp_mult=1.1,
        damage_mult=0.9,
        defense_mult=1.25,
        heal_on_rest_mult=2.0,  # Double healing at inn
        shield_on_doubles=True,  # Temp shield = roll total on doubles
    ),

    # ========== TIER 2 UNLOCKS (750-900g) ==========
    "berserker": CharacterTemplate(
        id="berserker",
        name="Berserker",
        description="Exploding dice! Max rolls explode. Rage when hurt.",
        flavor_text="ROLL A 12? ROLL AGAIN! THE DICE HUNGER FOR MORE!",
        dice_formula="1d12",
        dice_special="exploding",  # On 12, roll again and add
        dice_description="1d12 exploding! (12 = roll again)",
        cost=750,
        damage_mult=1.2,
        life_steal_base=0.15,
        damage_taken_mult=1.2,
        rage_mode=True,  # +50% damage when below 30% HP
    ),

    "monk": CharacterTemplate(
        id="monk",
        name="Monk",
        description="Master of balance. Doubles grant enlightenment.",
        flavor_text="When yin meets yang, the universe moves with you.",
        dice_formula="2d8",
        dice_special="doubles_bonus",  # Doubles = move double + combat bonus
        dice_description="2d8 (2-16), doubles = double move!",
        cost=800,
        hp_mult=0.9,
        damage_mult=1.0,
        attack_speed_mult=1.3,
        crit_damage_mult=1.5,
        combo_master=True,  # Builds combo stacks for damage
    ),

    "gambler": CharacterTemplate(
        id="gambler",
        name="Gambler",
        description="Fortune's favorite. Usually lucky... usually.",
        flavor_text="Roll 3, keep 2. Fate smiles... most of the time.",
        dice_formula="3d6",
        dice_special="cursed_fortune",  # Usually best 2, sometimes worst 2
        dice_description="3d6 keep best 2 (80%) or worst 2 (20%)",
        cost=850,
        hp_mult=0.85,
        gold_mult=1.5,
        lucky_crits=True,  # Crits deal 2x instead of 1.5x
        crit_chance_mult=1.2,
    ),

    # ========== TIER 3 UNLOCKS (1000-1200g) ==========
    "vampire": CharacterTemplate(
        id="vampire",
        name="Vampire",
        description="Immortal predator. Heals from everything.",
        flavor_text="Your movement is my sustenance. Your blood, my power.",
        dice_formula="2d6",
        dice_special="none",
        dice_description="2d6 (2-12), heals on movement",
        cost=1000,
        hp_mult=0.7,  # Starts weak
        damage_mult=1.1,
        life_steal_base=0.25,  # 25% life steal
        vampiric=True,  # Also heals 10% of movement as HP
        attack_speed_mult=1.15,
    ),

    "mage": CharacterTemplate(
        id="mage",
        name="Mage",
        description="Arcane master. Spells pierce all defenses.",
        flavor_text="Consistent power. Every spell finds its mark.",
        dice_formula="2d4+3",
        dice_special="none",
        dice_description="2d4+3 (5-11, ultra consistent)",
        cost=1000,
        hp_mult=0.6,
        can_equip_armor=False,
        has_spells=True,  # Damage ignores defense
        crit_chance_mult=1.3,
        crit_damage_mult=2.0,  # Devastating crits
    ),

    "necromancer": CharacterTemplate(
        id="necromancer",
        name="Necromancer",
        description="Death empowers. Each kill makes dice stronger.",
        flavor_text="The fallen fuel my ascension. Death begets power.",
        dice_formula="1d6",
        dice_special="none",  # But gains +1 die size per 5 kills!
        dice_description="1d6 (+1 die size per 5 kills)",
        cost=1100,
        hp_mult=0.8,
        damage_mult=0.9,
        defense_mult=0.8,
        death_stacks=True,  # Dice grow: d6 -> d8 -> d10 -> d12 -> d20
        life_steal_base=0.1,
    ),

    # ========== TIER 4 UNLOCKS (1500g+) ==========
    "jester": CharacterTemplate(
        id="jester",
        name="Jester",
        description="Agent of chaos. Random dice, random fate!",
        flavor_text="d4? d20? WHO KNOWS! That's the fun part!",
        dice_formula="1d?",  # Special: random die each roll
        dice_special="random_dice",
        dice_description="Random die type each roll!",
        cost=1500,
        hp_mult=1.0,
        damage_mult=1.0,
        gold_mult=1.25,
        crit_chance_mult=1.1,
        chaos_rolls=True,
    ),

    "avatar": CharacterTemplate(
        id="avatar",
        name="Avatar",
        description="The chosen one. Perfectly balanced, ultra rare.",
        flavor_text="All elements. All powers. The ultimate being.",
        dice_formula="2d6+2",
        dice_special="reroll_ones",
        dice_description="2d6+2 reroll 1s (6-14, blessed)",
        cost=2000,
        hp_mult=1.2,
        damage_mult=1.15,
        defense_mult=1.15,
        attack_speed_mult=1.1,
        crit_chance_mult=1.15,
        life_steal_base=0.1,
        heal_on_rest_mult=1.5,
    ),
}


def get_character(character_id: str) -> CharacterTemplate:
    """Get a character template by ID."""
    return CHARACTERS.get(character_id, CHARACTERS["warrior"])


def get_unlockable_characters() -> Dict[str, CharacterTemplate]:
    """Get all characters that cost gold to unlock."""
    return {k: v for k, v in CHARACTERS.items() if v.cost > 0}
