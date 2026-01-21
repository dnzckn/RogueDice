"""Player component for player-specific data."""

from dataclasses import dataclass, field
from typing import List, Optional
from ..core.component import Component


@dataclass
class PlayerComponent(Component):
    """Player-specific data."""

    name: str = "Hero"
    character_id: str = "warrior"  # Character template ID
    current_round: int = 1
    laps_completed: int = 0
    monsters_killed: int = 0
    items_collected: int = 0
    gold: int = 0
    gold_multiplier: float = 1.0  # Modified by blessings/character

    # Potions
    potion_count: int = 1
    max_potions: int = 1

    # Active blessings (list of Blessing objects)
    active_blessings: List = field(default_factory=list)

    # Boss tracking
    boss_defeated: bool = False
    continuing_after_boss: bool = False  # True if player chose to continue

    # Character-specific mechanics
    momentum: int = 0  # Warrior: builds +1 per non-combat move
    combo_stacks: int = 0  # Monk: builds stacks for damage
    death_stacks: int = 0  # Necromancer: kills / 5 = die upgrade level
    temp_shield: int = 0  # Paladin: temporary HP from doubles
    poison_stacks: int = 0  # Rogue: poison damage to apply

    # Last roll info (for UI display)
    last_roll_doubled: bool = False
    last_roll_exploded: bool = False
    last_roll_cursed: bool = False

    # Fate Points system for dice manipulation
    fate_points: int = 0
    locked_die_value: Optional[int] = None  # Value locked for next N rolls
    locked_die_rolls_left: int = 0  # How many rolls the lock persists

    # Sprite info
    sprite_name: str = "player"

    def complete_lap(self) -> bool:
        """
        Register a completed lap.
        Returns True if this starts a new round.
        """
        self.laps_completed += 1
        self.current_round = self.laps_completed + 1

        # Tick blessing durations
        self.tick_blessings()

        # Award fate points for lap completion
        self.add_fate_points(2)

        return True

    def on_move(self, had_combat: bool = False) -> None:
        """Called after each move to update character mechanics."""
        if had_combat:
            # Combat resets momentum
            self.momentum = 0
            self.poison_stacks = 0
        else:
            # Non-combat move builds momentum
            self.momentum += 1

    def on_combat_start(self, movement_roll: int) -> None:
        """Called when combat starts to apply character effects."""
        # Rogue poison = movement roll
        from ..models.characters import get_character
        char = get_character(self.character_id)
        if char.poison_damage:
            self.poison_stacks = movement_roll

    def on_kill(self) -> None:
        """Called when player kills a monster."""
        self.monsters_killed += 1

        # Necromancer death stacks (every 5 kills = +1 stack, max 4)
        from ..models.characters import get_character
        char = get_character(self.character_id)
        if char.death_stacks:
            self.death_stacks = min(4, self.monsters_killed // 5)

        # Monk combo stacks
        if char.combo_master:
            self.combo_stacks += 1

        # Award fate points for kills
        self.add_fate_points(1)

    def add_fate_points(self, amount: int) -> None:
        """Add fate points (capped at 10)."""
        self.fate_points = min(10, self.fate_points + amount)

    def use_fate_nudge(self) -> bool:
        """Use Nudge ability (1 FP): +1 or -1 to die. Returns True if successful."""
        if self.fate_points >= 1:
            self.fate_points -= 1
            return True
        return False

    def use_fate_reroll(self) -> bool:
        """Use Reroll ability (2 FP): Reroll all dice. Returns True if successful."""
        if self.fate_points >= 2:
            self.fate_points -= 2
            return True
        return False

    def use_fate_lock(self, value: int) -> bool:
        """Use Lock ability (2 FP): Lock one die value for next 2 rolls. Returns True if successful."""
        if self.fate_points >= 2:
            self.fate_points -= 2
            self.locked_die_value = value
            self.locked_die_rolls_left = 2
            return True
        return False

    def use_fate_roll(self) -> bool:
        """Use Fate Roll ability (3 FP): Roll twice, pick preferred. Returns True if successful."""
        if self.fate_points >= 3:
            self.fate_points -= 3
            return True
        return False

    def consume_locked_die(self) -> Optional[int]:
        """Consume one use of locked die. Returns locked value if active, None otherwise."""
        if self.locked_die_value is not None and self.locked_die_rolls_left > 0:
            value = self.locked_die_value
            self.locked_die_rolls_left -= 1
            if self.locked_die_rolls_left <= 0:
                self.locked_die_value = None
            return value
        return None

    def on_doubles_rolled(self, roll_total: int) -> None:
        """Called when doubles are rolled."""
        from ..models.characters import get_character
        char = get_character(self.character_id)

        # Paladin shield on doubles
        if char.shield_on_doubles:
            self.temp_shield += roll_total

    def consume_temp_shield(self, damage: int) -> int:
        """
        Consume temp shield before taking damage.
        Returns remaining damage after shield.
        """
        if self.temp_shield > 0:
            if damage <= self.temp_shield:
                self.temp_shield -= damage
                return 0
            else:
                damage -= self.temp_shield
                self.temp_shield = 0
                return damage
        return damage

    def add_gold(self, amount: int) -> None:
        """Add gold to player (applies gold multiplier)."""
        actual_amount = int(amount * self.gold_multiplier)
        self.gold += actual_amount

    def spend_gold(self, amount: int) -> bool:
        """Spend gold if possible. Returns True if successful."""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def use_potion(self) -> bool:
        """Use a potion. Returns True if successful."""
        if self.potion_count > 0:
            self.potion_count -= 1
            return True
        return False

    def add_potion(self) -> bool:
        """Add a potion. Returns True if successful (not at max)."""
        if self.potion_count < self.max_potions:
            self.potion_count += 1
            return True
        return False

    def add_blessing(self, blessing) -> None:
        """Add a blessing effect."""
        self.active_blessings.append(blessing)

        # Update gold multiplier if it's a gold blessing
        from ..models.blessings import BlessingType
        if blessing.blessing_type == BlessingType.GOLD_FIND:
            self.gold_multiplier += blessing.value

    def tick_blessings(self) -> List:
        """
        Decrement blessing durations at end of round.
        Returns list of expired blessings.
        """
        from ..models.blessings import BlessingType

        expired = []
        remaining = []

        for blessing in self.active_blessings:
            if blessing.tick():
                remaining.append(blessing)
            else:
                expired.append(blessing)
                # Remove gold multiplier if it was a gold blessing
                if blessing.blessing_type == BlessingType.GOLD_FIND:
                    self.gold_multiplier -= blessing.value

        self.active_blessings = remaining
        return expired

    def get_blessing_bonus(self, blessing_type) -> float:
        """Get total bonus from active blessings of a specific type."""
        total = 0.0
        for blessing in self.active_blessings:
            if blessing.blessing_type == blessing_type:
                total += blessing.value
        return total

    @property
    def has_potion(self) -> bool:
        """Check if player has a potion available."""
        return self.potion_count > 0

    @property
    def should_spawn_boss(self) -> bool:
        """Check if boss should spawn (after round 20, not yet defeated)."""
        return self.current_round > 20 and not self.boss_defeated
