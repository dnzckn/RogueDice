"""Persistent data that survives between game runs."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PermanentUpgrade:
    """A permanent upgrade that applies each run."""
    id: str
    name: str
    description: str
    effect_per_level: float
    max_level: int
    base_cost: int

    def get_cost(self, current_level: int) -> int:
        """Get cost to upgrade from current_level to current_level + 1."""
        if current_level >= self.max_level:
            return 0
        return self.base_cost * (current_level + 1)

    def get_total_effect(self, level: int) -> float:
        """Get total effect at given level."""
        return self.effect_per_level * level


# Define all permanent upgrades
UPGRADES: Dict[str, PermanentUpgrade] = {
    "vitality": PermanentUpgrade(
        id="vitality",
        name="Vitality",
        description="+10 max HP",
        effect_per_level=10,
        max_level=10,
        base_cost=50,
    ),
    "strength": PermanentUpgrade(
        id="strength",
        name="Strength",
        description="+2 damage",
        effect_per_level=2,
        max_level=10,
        base_cost=60,
    ),
    "precision": PermanentUpgrade(
        id="precision",
        name="Precision",
        description="+2% crit",
        effect_per_level=0.02,
        max_level=10,
        base_cost=75,
    ),
    "fortitude": PermanentUpgrade(
        id="fortitude",
        name="Fortitude",
        description="+2 defense",
        effect_per_level=2,
        max_level=10,
        base_cost=50,
    ),
    "swiftness": PermanentUpgrade(
        id="swiftness",
        name="Swiftness",
        description="+5% attack speed",
        effect_per_level=0.05,
        max_level=5,
        base_cost=100,
    ),
    "vampirism": PermanentUpgrade(
        id="vampirism",
        name="Vampirism",
        description="+2% life steal",
        effect_per_level=0.02,
        max_level=5,
        base_cost=150,
    ),
    "prosperity": PermanentUpgrade(
        id="prosperity",
        name="Prosperity",
        description="+25 starting gold",
        effect_per_level=25,
        max_level=5,
        base_cost=80,
    ),
}


# Boss victory unlocks - what each victory count unlocks
BOSS_VICTORY_UNLOCKS = {
    1: {"type": "character", "id": "rogue", "description": "Unlocks Rogue character for free"},
    2: {"type": "feature", "id": "double_blessings", "description": "Blessing shrines grant 2 blessings"},
    3: {"type": "feature", "id": "rare_start", "description": "Start with a random Rare item"},
    4: {"type": "feature", "id": "extra_potion", "description": "Start with 2 potions instead of 1"},
    5: {"type": "mode", "id": "nightmare", "description": "Unlock Nightmare mode (harder, better rewards)"},
    6: {"type": "character", "id": "mage", "description": "Unlocks Mage character for free"},
    7: {"type": "feature", "id": "gold_interest", "description": "Earn 5% interest on gold between runs"},
    10: {"type": "title", "id": "champion", "description": "Title: Champion of the Dice"},
}


@dataclass
class PersistentData:
    """Data that persists between game runs. Saved to disk."""

    # Currency
    lifetime_gold: int = 0
    current_gold: int = 0

    # Statistics
    total_runs: int = 0
    best_round: int = 0
    total_kills: int = 0
    total_boss_victories: int = 0

    # Unlocks
    unlocked_characters: List[str] = field(default_factory=lambda: ["warrior"])
    selected_character: str = "warrior"
    unlocked_features: List[str] = field(default_factory=list)

    # Upgrade levels (upgrade_id -> level)
    upgrade_levels: Dict[str, int] = field(default_factory=dict)

    # Game modes
    nightmare_mode: bool = False

    def add_gold(self, amount: int) -> None:
        """Add gold earned during a run."""
        self.lifetime_gold += amount
        self.current_gold += amount

    def spend_gold(self, amount: int) -> bool:
        """Spend gold. Returns True if successful."""
        if self.current_gold >= amount:
            self.current_gold -= amount
            return True
        return False

    def get_upgrade_level(self, upgrade_id: str) -> int:
        """Get current level of an upgrade."""
        return self.upgrade_levels.get(upgrade_id, 0)

    def get_upgrade_effect(self, upgrade_id: str) -> float:
        """Get the total effect of an upgrade at current level."""
        if upgrade_id not in UPGRADES:
            return 0
        level = self.get_upgrade_level(upgrade_id)
        return UPGRADES[upgrade_id].get_total_effect(level)

    def purchase_upgrade(self, upgrade_id: str) -> bool:
        """Purchase one level of an upgrade. Returns True if successful."""
        if upgrade_id not in UPGRADES:
            return False

        upgrade = UPGRADES[upgrade_id]
        current_level = self.get_upgrade_level(upgrade_id)

        if current_level >= upgrade.max_level:
            return False

        cost = upgrade.get_cost(current_level)
        if self.spend_gold(cost):
            self.upgrade_levels[upgrade_id] = current_level + 1
            return True
        return False

    def unlock_character(self, character_id: str, cost: int) -> bool:
        """Unlock a character. Returns True if successful."""
        if character_id in self.unlocked_characters:
            return False

        if self.spend_gold(cost):
            self.unlocked_characters.append(character_id)
            return True
        return False

    def is_character_unlocked(self, character_id: str) -> bool:
        """Check if a character is unlocked."""
        return character_id in self.unlocked_characters

    def record_run_end(self, final_round: int, kills: int, gold_earned: int) -> None:
        """Record statistics at end of a run."""
        self.total_runs += 1
        self.best_round = max(self.best_round, final_round)
        self.total_kills += kills
        self.add_gold(gold_earned)

    def record_boss_victory(self) -> Optional[dict]:
        """
        Record a boss victory and process unlocks.
        Returns the unlock info if something new was unlocked.
        """
        self.total_boss_victories += 1

        # Check for new unlocks at this victory count
        unlock = BOSS_VICTORY_UNLOCKS.get(self.total_boss_victories)
        if unlock:
            unlock_type = unlock["type"]
            unlock_id = unlock["id"]

            if unlock_type == "character":
                if unlock_id not in self.unlocked_characters:
                    self.unlocked_characters.append(unlock_id)
                    return unlock
            elif unlock_type == "feature":
                if unlock_id not in self.unlocked_features:
                    self.unlocked_features.append(unlock_id)
                    return unlock
            elif unlock_type == "mode":
                if unlock_id not in self.unlocked_features:
                    self.unlocked_features.append(unlock_id)
                    return unlock
            elif unlock_type == "title":
                if unlock_id not in self.unlocked_features:
                    self.unlocked_features.append(unlock_id)
                    return unlock

        return None

    def has_feature(self, feature_id: str) -> bool:
        """Check if a feature is unlocked."""
        return feature_id in self.unlocked_features

    def get_starting_potions(self) -> int:
        """Get number of potions to start with."""
        return 2 if self.has_feature("extra_potion") else 1

    def apply_gold_interest(self) -> int:
        """Apply gold interest if unlocked. Returns interest earned."""
        if self.has_feature("gold_interest"):
            interest = int(self.current_gold * 0.05)
            self.current_gold += interest
            return interest
        return 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "lifetime_gold": self.lifetime_gold,
            "current_gold": self.current_gold,
            "total_runs": self.total_runs,
            "best_round": self.best_round,
            "total_kills": self.total_kills,
            "total_boss_victories": self.total_boss_victories,
            "unlocked_characters": self.unlocked_characters,
            "selected_character": self.selected_character,
            "unlocked_features": self.unlocked_features,
            "upgrade_levels": self.upgrade_levels,
            "nightmare_mode": self.nightmare_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PersistentData":
        """Create from dictionary."""
        return cls(
            lifetime_gold=data.get("lifetime_gold", 0),
            current_gold=data.get("current_gold", 0),
            total_runs=data.get("total_runs", 0),
            best_round=data.get("best_round", 0),
            total_kills=data.get("total_kills", 0),
            total_boss_victories=data.get("total_boss_victories", 0),
            unlocked_characters=data.get("unlocked_characters", ["warrior"]),
            selected_character=data.get("selected_character", "warrior"),
            unlocked_features=data.get("unlocked_features", []),
            upgrade_levels=data.get("upgrade_levels", {}),
            nightmare_mode=data.get("nightmare_mode", False),
        )

    def save(self, path: Optional[Path] = None) -> None:
        """Save to disk."""
        if path is None:
            path = Path.home() / ".roguedice" / "save.json"

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PersistentData":
        """Load from disk, or create new if not found."""
        if path is None:
            path = Path.home() / ".roguedice" / "save.json"

        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass

        return cls()
