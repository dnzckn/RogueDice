"""Combat system for automatic tick-based combat."""

import random
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from ..core.system import System
from ..components.stats import StatsComponent
from ..components.combat import CombatStateComponent
from ..components.monster import MonsterComponent
from ..components.player import PlayerComponent


@dataclass
class CombatResult:
    """Result of a complete combat."""
    victory: bool
    player_hp_remaining: int
    player_hp_max: int
    ticks: int
    duration: float
    damage_dealt: int
    damage_taken: int
    log: list = field(default_factory=list)
    monster_name: str = ""
    gold_earned: int = 0
    item_dropped: bool = False


class CombatSystem(System):
    """
    Tick-based automatic combat simulation.
    Combat runs at a fixed tick rate.
    """

    TICKS_PER_SECOND = 10
    TICK_DURATION = 1.0 / TICKS_PER_SECOND
    MAX_TICKS = 1000  # Safety limit

    priority = 100

    def start_combat(self, player_id: int, monster_id: int) -> None:
        """Initialize combat between player and monster."""
        combat = self.world.get_component(player_id, CombatStateComponent)
        if combat:
            combat.start_combat(monster_id)

    def run_full_combat(self, player_id: int, monster_id: int) -> CombatResult:
        """
        Run combat to completion and return results.

        Args:
            player_id: Entity ID of player
            monster_id: Entity ID of monster

        Returns:
            CombatResult with full combat details
        """
        self.start_combat(player_id, monster_id)

        combat = self.world.get_component(player_id, CombatStateComponent)
        player_stats = self.world.get_component(player_id, StatsComponent)
        monster_stats = self.world.get_component(monster_id, StatsComponent)
        monster_comp = self.world.get_component(monster_id, MonsterComponent)

        if not all([combat, player_stats, monster_stats]):
            return CombatResult(
                victory=False,
                player_hp_remaining=0,
                player_hp_max=100,
                ticks=0,
                duration=0,
                damage_dealt=0,
                damage_taken=0,
                log=["Error: Missing components"],
            )

        monster_name = monster_comp.name if monster_comp else "Monster"
        combat.add_log(f"You encounter a {monster_name}!")
        combat.add_log(f"Your HP: {player_stats.current_hp}/{player_stats.max_hp}")
        combat.add_log(f"Enemy HP: {monster_stats.current_hp}/{monster_stats.max_hp}")

        # Run combat ticks
        while combat.in_combat and combat.combat_tick < self.MAX_TICKS:
            self._process_tick(player_id, monster_id, combat, player_stats, monster_stats)

        # Determine result
        victory = player_stats.is_alive()
        combat.end_combat(victory)

        # Calculate rewards
        gold_earned = 0
        if victory and monster_comp:
            gold_earned = monster_comp.gold_reward

        return CombatResult(
            victory=victory,
            player_hp_remaining=player_stats.current_hp,
            player_hp_max=player_stats.max_hp,
            ticks=combat.combat_tick,
            duration=combat.combat_tick * self.TICK_DURATION,
            damage_dealt=combat.damage_dealt,
            damage_taken=combat.damage_taken,
            log=combat.combat_log.copy(),
            monster_name=monster_name,
            gold_earned=gold_earned,
        )

    def _process_tick(
        self,
        player_id: int,
        monster_id: int,
        combat: CombatStateComponent,
        player_stats: StatsComponent,
        monster_stats: StatsComponent,
    ) -> None:
        """Process one tick of combat."""
        combat.combat_tick += 1
        current_time = combat.combat_tick * self.TICK_DURATION

        # Player attack
        if current_time >= combat.next_attack_tick:
            damage = self._calculate_damage(player_stats, monster_stats)
            actual_damage = monster_stats.take_damage(damage)
            combat.damage_dealt += actual_damage

            # Life steal
            if player_stats.life_steal > 0 and actual_damage > 0:
                heal = int(actual_damage * player_stats.life_steal)
                player_stats.heal(heal)
                if heal > 0:
                    combat.add_log(f"  [Life steal: +{heal} HP]")

            combat.add_log(
                f"[{current_time:.1f}s] You deal {actual_damage} damage! "
                f"(Enemy: {monster_stats.current_hp} HP)"
            )

            # Schedule next attack
            attack_interval = 1.0 / max(0.1, player_stats.attack_speed)
            combat.next_attack_tick = current_time + attack_interval

        # Monster attack
        if current_time >= combat.opponent_next_attack_tick:
            damage = self._calculate_damage(monster_stats, player_stats)
            actual_damage = player_stats.take_damage(damage)
            combat.damage_taken += actual_damage

            combat.add_log(
                f"[{current_time:.1f}s] Enemy deals {actual_damage} damage! "
                f"(You: {player_stats.current_hp} HP)"
            )

            # Schedule next attack
            attack_interval = 1.0 / max(0.1, monster_stats.attack_speed)
            combat.opponent_next_attack_tick = current_time + attack_interval

        # Check end conditions
        if not monster_stats.is_alive():
            combat.add_log("Enemy defeated!")
            combat.in_combat = False
        elif not player_stats.is_alive():
            combat.add_log("You have been defeated...")
            combat.in_combat = False

    def _calculate_damage(
        self,
        attacker: StatsComponent,
        defender: StatsComponent,
    ) -> int:
        """Calculate damage for a single attack."""
        # Base damage
        damage = attacker.base_damage

        # Critical hit check
        is_crit = random.random() < attacker.crit_chance
        if is_crit:
            damage *= attacker.crit_multiplier

        # Dodge check
        if random.random() < defender.dodge_chance:
            return 0

        # Apply defense (flat reduction)
        damage -= defender.defense

        # Apply resistance (percentage reduction)
        damage *= (1 - defender.resistance)

        # Add true damage (ignores defenses)
        damage += attacker.true_damage

        # Minimum 1 damage
        return max(1, int(damage))

    def update(self, delta_time: float) -> None:
        """Not used - combat is run synchronously."""
        pass
