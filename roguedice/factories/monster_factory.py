"""Factory for creating monster entities."""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from ..core.world import World
from ..components.stats import StatsComponent
from ..components.monster import MonsterComponent


class MonsterFactory:
    """Creates monster entities from templates."""

    def __init__(self, world: World, data_path: Optional[Path] = None):
        self.world = world
        self.data_path = data_path or Path(__file__).parent.parent / "data" / "monsters"
        self.templates = self._load_templates()

    def _load_templates(self) -> List[Dict]:
        """Load monster templates from JSON file."""
        filepath = self.data_path / "monsters.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
                return data.get("templates", [])
        return []

    def create_monster(
        self,
        current_round: int,
        tier: Optional[int] = None,
        template_id: Optional[str] = None,
    ) -> int:
        """
        Create a monster entity.

        Args:
            current_round: Current game round (affects scaling)
            tier: Monster tier (1-5), or None for auto based on round
            template_id: Specific template ID, or None for random

        Returns:
            Entity ID of created monster
        """
        # Determine tier based on round if not specified
        if tier is None:
            tier = 1 + (current_round - 1) // 5  # Tier increases every 5 rounds
            tier = min(tier, 5)

        # Get appropriate templates
        appropriate_templates = [
            t for t in self.templates
            if t.get("tier", 1) <= tier and not t.get("is_boss", False)
        ]

        if not appropriate_templates:
            appropriate_templates = self.templates or [self._default_template()]

        # Pick template with weighted tier selection (lower tiers more common)
        if template_id:
            template = next(
                (t for t in self.templates if t.get("id") == template_id),
                random.choice(appropriate_templates)
            )
        else:
            # Weight templates: higher tier = lower weight
            # Tier 1 at max_tier 3: weight 3, Tier 2: weight 2, Tier 3: weight 1
            weights = []
            for t in appropriate_templates:
                t_tier = t.get("tier", 1)
                weight = max(1, tier - t_tier + 1)  # Higher difference = higher weight
                weights.append(weight)

            template = random.choices(appropriate_templates, weights=weights, k=1)[0]

        # Create entity
        entity_id = self.world.create_entity()

        # Scale stats based on round
        scaling = template.get("scaling", {})
        rounds_scaling = current_round - 1

        base_hp = template.get("base_hp", 50)
        hp_per_round = scaling.get("hp_per_round", 10)
        final_hp = int(base_hp + hp_per_round * rounds_scaling)

        base_damage = template.get("base_damage", 10)
        damage_per_round = scaling.get("damage_per_round", 2)
        final_damage = base_damage + damage_per_round * rounds_scaling

        # Create stats component
        stats = StatsComponent(
            max_hp=final_hp,
            current_hp=final_hp,
            base_damage=final_damage,
            attack_speed=template.get("attack_speed", 1.0),
            defense=min(15, template.get("defense", 0) + current_round),
            crit_chance=template.get("crit_chance", 0.05),
            life_steal=template.get("life_steal", 0),
            true_damage=template.get("true_damage", 0),
        )
        self.world.add_component(entity_id, stats)

        # Create monster component
        monster = MonsterComponent(
            name=template.get("name", "Monster"),
            template_id=template.get("id", ""),
            tier=template.get("tier", 1),
            sprite_name=template.get("sprite", "goblin"),
            drop_chance=template.get("drop_chance", 0.5),
            gold_reward=int(template.get("gold_reward", 10) * (1 + current_round * 0.2)),
            special_moves=template.get("special_moves", []),
        )
        self.world.add_component(entity_id, monster)

        return entity_id

    def _default_template(self) -> Dict:
        """Return default monster template."""
        return {
            "id": "default",
            "name": "Monster",
            "tier": 1,
            "base_hp": 50,
            "base_damage": 10,
            "attack_speed": 1.0,
            "defense": 0,
            "crit_chance": 0.05,
            "sprite": "goblin",
            "drop_chance": 0.4,
            "gold_reward": 10,
            "scaling": {
                "hp_per_round": 10,
                "damage_per_round": 2,
            }
        }
