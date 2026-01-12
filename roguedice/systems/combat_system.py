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
    monsters_defeated: int = 1  # Number of monsters killed (for 1vX)


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

    def run_multi_combat(self, player_id: int, monster_ids: list) -> CombatResult:
        """
        Run combat against multiple monsters (1vX).
        Player must defeat all monsters to win.

        Args:
            player_id: Entity ID of player
            monster_ids: List of monster entity IDs

        Returns:
            CombatResult with full combat details
        """
        if not monster_ids:
            return CombatResult(
                victory=True, player_hp_remaining=100, player_hp_max=100,
                ticks=0, duration=0, damage_dealt=0, damage_taken=0,
                log=["No monsters to fight!"], monsters_defeated=0
            )

        # For single monster, use regular combat
        if len(monster_ids) == 1:
            return self.run_full_combat(player_id, monster_ids[0])

        # Multi-monster combat
        combat = self.world.get_component(player_id, CombatStateComponent)
        player_stats = self.world.get_component(player_id, StatsComponent)

        if not combat or not player_stats:
            return CombatResult(
                victory=False, player_hp_remaining=0, player_hp_max=100,
                ticks=0, duration=0, damage_dealt=0, damage_taken=0,
                log=["Error: Missing player components"], monsters_defeated=0
            )

        # Get all monster stats
        monsters = []
        for mid in monster_ids:
            mstats = self.world.get_component(mid, StatsComponent)
            mcomp = self.world.get_component(mid, MonsterComponent)
            if mstats and mcomp:
                monsters.append({
                    'id': mid,
                    'stats': mstats,
                    'comp': mcomp,
                    'next_attack': 0.0,
                    'alive': True
                })

        if not monsters:
            return CombatResult(
                victory=True, player_hp_remaining=player_stats.current_hp,
                player_hp_max=player_stats.max_hp, ticks=0, duration=0,
                damage_dealt=0, damage_taken=0, log=["No valid monsters!"],
                monsters_defeated=0
            )

        # Start combat
        combat.start_combat(monsters[0]['id'])
        monster_names = ", ".join(m['comp'].name for m in monsters)
        combat.add_log(f"You face {len(monsters)} enemies: {monster_names}!")
        combat.add_log(f"Your HP: {player_stats.current_hp}/{player_stats.max_hp}")
        for m in monsters:
            combat.add_log(f"  {m['comp'].name}: {m['stats'].current_hp} HP")

        total_gold = 0
        monsters_killed = 0

        # Run combat ticks
        while combat.in_combat and combat.combat_tick < self.MAX_TICKS:
            combat.combat_tick += 1
            current_time = combat.combat_tick * self.TICK_DURATION

            # Player attacks
            if current_time >= combat.next_attack_tick:
                # Find first alive monster as primary target
                primary_target = None
                for m in monsters:
                    if m['alive'] and m['stats'].is_alive():
                        primary_target = m
                        break

                if primary_target:
                    # Primary target takes full damage
                    damage = self._calculate_damage(player_stats, primary_target['stats'])
                    actual_damage = primary_target['stats'].take_damage(damage)
                    combat.damage_dealt += actual_damage

                    # Life steal on primary damage
                    if player_stats.life_steal > 0 and actual_damage > 0:
                        heal = int(actual_damage * player_stats.life_steal)
                        player_stats.heal(heal)

                    combat.add_log(
                        f"[{current_time:.1f}s] You hit {primary_target['comp'].name} for {actual_damage}! "
                        f"({primary_target['stats'].current_hp} HP)"
                    )

                    # Cleave damage to other alive monsters
                    if player_stats.cleave > 0:
                        for m in monsters:
                            if m['alive'] and m['stats'].is_alive() and m != primary_target:
                                cleave_damage = int(damage * player_stats.cleave)
                                if cleave_damage > 0:
                                    cleave_actual = m['stats'].take_damage(cleave_damage)
                                    combat.damage_dealt += cleave_actual
                                    combat.add_log(
                                        f"  [Cleave] {m['comp'].name} takes {cleave_actual}! "
                                        f"({m['stats'].current_hp} HP)"
                                    )

                    # Check for kills
                    for m in monsters:
                        if m['alive'] and not m['stats'].is_alive():
                            m['alive'] = False
                            monsters_killed += 1
                            total_gold += m['comp'].gold_reward
                            combat.add_log(f"  {m['comp'].name} defeated!")

                # Schedule next attack
                attack_interval = 1.0 / max(0.1, player_stats.attack_speed)
                combat.next_attack_tick = current_time + attack_interval

            # All alive monsters attack player
            for m in monsters:
                if not m['alive'] or not m['stats'].is_alive():
                    continue

                if current_time >= m['next_attack']:
                    damage = self._calculate_damage(m['stats'], player_stats)
                    actual_damage = player_stats.take_damage(damage)
                    combat.damage_taken += actual_damage

                    combat.add_log(
                        f"[{current_time:.1f}s] {m['comp'].name} hits you for {actual_damage}! "
                        f"(You: {player_stats.current_hp} HP)"
                    )

                    # Schedule next attack
                    attack_interval = 1.0 / max(0.1, m['stats'].attack_speed)
                    m['next_attack'] = current_time + attack_interval

            # Check end conditions
            alive_monsters = sum(1 for m in monsters if m['alive'] and m['stats'].is_alive())
            if alive_monsters == 0:
                combat.add_log("All enemies defeated!")
                combat.in_combat = False
            elif not player_stats.is_alive():
                combat.add_log("You have been defeated...")
                combat.in_combat = False

        victory = player_stats.is_alive()
        combat.end_combat(victory)

        return CombatResult(
            victory=victory,
            player_hp_remaining=player_stats.current_hp,
            player_hp_max=player_stats.max_hp,
            ticks=combat.combat_tick,
            duration=combat.combat_tick * self.TICK_DURATION,
            damage_dealt=combat.damage_dealt,
            damage_taken=combat.damage_taken,
            log=combat.combat_log.copy(),
            monster_name=monster_names,
            gold_earned=total_gold,
            monsters_defeated=monsters_killed,
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
