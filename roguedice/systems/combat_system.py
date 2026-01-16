"""Combat system for automatic tick-based combat."""

import random
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..core.system import System
from ..components.stats import StatsComponent
from ..components.combat import CombatStateComponent
from ..components.monster import MonsterComponent
from ..components.player import PlayerComponent
from ..components.equipment import EquipmentComponent
from ..components.item import ItemComponent
from ..models.enums import ItemTheme, Element


@dataclass
class ThemeEffectState:
    """Track active theme effects during combat."""
    # Burn (Fire) - NOW STACKS up to 3x
    burn_damage: int = 0
    burn_ticks_remaining: int = 0
    burn_stacks: int = 0  # Each stack increases burn damage

    # Water - flinch + "Soaked" debuff
    enemy_flinched: bool = False
    enemy_soaked: bool = False  # Soaked enemies take +25% damage
    soaked_until: float = 0.0

    # Paralyze (Electric) - enemy can't attack for duration
    paralyzed_until: float = 0.0
    # Paralyzed enemies take bonus damage
    paralyzed_damage_bonus: float = 0.30

    # Cyberpunk - gold + "Neural Hack" damage reduction
    bonus_gold_percent: float = 0.0
    hack_chance: float = 0.0
    enemy_hacked: bool = False  # Hacked = next attack deals 40% less

    # Steampunk - pressure system
    crit_bonus: float = 0.0
    pressure: int = 0  # Builds with each attack
    pressure_threshold: int = 5  # Steam burst at this level
    steam_burst_damage: int = 0

    # Angelic - heal + Guardian Angel (survive fatal once)
    angelic_heal_percent: float = 0.0
    guardian_angel_ready: bool = False  # Once per combat survive lethal
    desperate_healing: bool = False  # 2x healing below 25% HP

    # Demonic - HP cost, but damage scales with MISSING HP
    demonic_base_mult: float = 0.0
    demonic_hp_cost_percent: float = 0.0
    demonic_has_item: bool = False  # Track if demonic theme equipped
    soul_harvest_percent: float = 0.0  # Heal on kill

    # Magical - mana burst with amplification stacking
    mana_burst_chance: float = 0.0
    mana_burst_damage: int = 0
    arcane_amplification: int = 0  # Consecutive bursts increase damage

    # Wind - free attack chance + dodge bonus
    gust_chance: float = 0.0
    wind_dodge_bonus: float = 0.0

    # Earth - damage reduction + tremor (delay enemy attacks)
    earth_damage_reduction: float = 0.0
    attack_count: int = 0  # For tremor every 4th attack
    tremor_delay: float = 0.3


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
    monster_max_hp: int = 0  # Monster's max HP for battle scene display
    monster_sprite: str = ""  # Monster sprite type for battle scene


class CombatSystem(System):
    """
    Tick-based automatic combat simulation.
    Combat runs at a fixed tick rate.
    """

    TICKS_PER_SECOND = 10
    TICK_DURATION = 1.0 / TICKS_PER_SECOND
    MAX_TICKS = 1000  # Safety limit

    priority = 100

    def _get_theme_effect_state(self, player_id: int) -> ThemeEffectState:
        """Build theme effect state from player's equipped items."""
        state = ThemeEffectState()

        equipment = self.world.get_component(player_id, EquipmentComponent)
        if not equipment:
            return state

        # Check all equipped items for themes
        for item_id in equipment.get_all_equipped():
            if item_id is None:
                continue
            item = self.world.get_component(item_id, ItemComponent)
            if not item or item.theme == ItemTheme.NONE:
                continue

            # Calculate scaling factor from rarity and level
            rarity_factor = item.rarity.multiplier
            level_factor = 1 + (item.level - 1) * 0.15
            scale = rarity_factor * level_factor

            if item.theme == ItemTheme.CYBERPUNK:
                # Gold bonus + Neural Hack (reduce enemy damage)
                state.bonus_gold_percent += 0.15 * scale
                state.hack_chance = min(0.12 + 0.03 * scale, 0.25)  # 12-25% chance

            elif item.theme == ItemTheme.STEAMPUNK:
                # Pressure system - builds to steam burst
                state.crit_bonus += 0.03 * scale  # Keep crit bonus
                state.steam_burst_damage = int(15 * scale)  # Burst damage
                state.pressure_threshold = max(3, 6 - int(scale))  # Faster at high level

            elif item.theme == ItemTheme.MAGICAL:
                # Mana burst with arcane amplification
                state.mana_burst_chance = min(0.20 + 0.03 * scale, 0.35)
                state.mana_burst_damage = int(12 * scale)

            elif item.theme == ItemTheme.ANGELIC:
                # Heal + Guardian Angel (once per combat survive lethal)
                state.angelic_heal_percent += 0.04 * scale  # Slightly higher base
                state.guardian_angel_ready = True  # Unlocks with any angelic item
                state.desperate_healing = True  # 2x healing below 25% HP

            elif item.theme == ItemTheme.DEMONIC:
                # HP cost, damage scales with MISSING HP, soul harvest on kill
                state.demonic_hp_cost_percent = 0.02 * scale
                state.demonic_base_mult = 0.15 * scale  # Base multiplier
                state.demonic_has_item = True
                state.soul_harvest_percent = 0.10 + 0.02 * scale  # 10-18% heal on kill

            elif item.theme == ItemTheme.ELEMENTAL:
                # Element-specific passives
                if item.element == Element.WIND:
                    state.gust_chance = min(0.15 + 0.03 * scale, 0.30)  # 15-30% free attack
                    state.wind_dodge_bonus += 0.03 * scale  # +3-12% dodge
                elif item.element == Element.EARTH:
                    state.earth_damage_reduction = min(0.08 + 0.02 * scale, 0.20)  # 8-20% DR

        return state

    def _get_elemental_items(self, player_id: int) -> List[tuple]:
        """Get list of (element, scale) for equipped elemental items."""
        elements = []
        equipment = self.world.get_component(player_id, EquipmentComponent)
        if not equipment:
            return elements

        for item_id in equipment.get_all_equipped():
            if item_id is None:
                continue
            item = self.world.get_component(item_id, ItemComponent)
            if not item or item.theme != ItemTheme.ELEMENTAL:
                continue

            rarity_factor = item.rarity.multiplier
            level_factor = 1 + (item.level - 1) * 0.15
            scale = rarity_factor * level_factor
            elements.append((item.element, scale))

        return elements

    def _process_elemental_proc(
        self,
        element: Element,
        scale: float,
        theme_state: ThemeEffectState,
        combat: CombatStateComponent,
        current_time: float,
        player_stats: StatsComponent,
    ) -> None:
        """Process elemental effect proc on hit."""
        # Proc chance: 15-33% based on scale
        proc_chance = min(0.15 + 0.04 * scale, 0.35)

        if random.random() > proc_chance:
            return

        if element == Element.FIRE:
            # ENHANCED: Burns now STACK up to 3x
            base_burn = int(4 * scale)
            if theme_state.burn_stacks < 3:
                theme_state.burn_stacks += 1
            theme_state.burn_damage = base_burn * theme_state.burn_stacks
            theme_state.burn_ticks_remaining = 5
            if theme_state.burn_stacks > 1:
                combat.add_log(f"  [Fire] INFERNO! x{theme_state.burn_stacks} burn! ({theme_state.burn_damage} dmg/tick)")
            else:
                combat.add_log(f"  [Fire] Enemy is burning! ({theme_state.burn_damage} dmg/tick)")

        elif element == Element.WATER:
            # ENHANCED: Flinch + Soaked debuff (+25% damage taken)
            theme_state.enemy_flinched = True
            theme_state.enemy_soaked = True
            theme_state.soaked_until = current_time + 3.0  # 3 seconds
            combat.add_log("  [Water] Tidal wave! Enemy soaked & flinched! (+25% dmg taken)")

        elif element == Element.ELECTRIC:
            # ENHANCED: Check for Water synergy - guaranteed paralyze if soaked
            if theme_state.enemy_soaked:
                # SYNERGY: Water + Electric = guaranteed long paralyze
                duration = 2.0 + 0.3 * scale
                theme_state.paralyzed_until = current_time + duration
                combat.add_log(f"  [Electric] CHAIN LIGHTNING! Soaked enemy paralyzed {duration:.1f}s!")
            else:
                duration = 1.0 + 0.25 * scale
                theme_state.paralyzed_until = current_time + duration
                combat.add_log(f"  [Electric] Enemy paralyzed for {duration:.1f}s!")

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

        # Initialize theme effects
        theme_state = self._get_theme_effect_state(player_id)
        elemental_items = self._get_elemental_items(player_id)

        # Run combat ticks
        while combat.in_combat and combat.combat_tick < self.MAX_TICKS:
            self._process_tick(
                player_id, monster_id, combat, player_stats, monster_stats,
                theme_state, elemental_items
            )

        # Determine result
        victory = player_stats.is_alive()
        combat.end_combat(victory)

        # Calculate rewards
        gold_earned = 0
        if victory and monster_comp:
            gold_earned = monster_comp.gold_reward
            # Cyberpunk: bonus gold on kill
            if theme_state.bonus_gold_percent > 0:
                bonus = int(gold_earned * theme_state.bonus_gold_percent)
                gold_earned += bonus
                combat.add_log(f"  [Cyberpunk] +{bonus} bonus gold!")

        # Get monster sprite for battle scene
        monster_sprite = monster_comp.sprite_name if monster_comp else "goblin"
        monster_max_hp_val = monster_stats.max_hp if monster_stats else 100

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
            monster_max_hp=monster_max_hp_val,
            monster_sprite=monster_sprite,
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

        # Initialize theme effects
        theme_state = self._get_theme_effect_state(player_id)
        elemental_items = self._get_elemental_items(player_id)

        total_gold = 0
        monsters_killed = 0

        # Run combat ticks
        while combat.in_combat and combat.combat_tick < self.MAX_TICKS:
            combat.combat_tick += 1
            current_time = combat.combat_tick * self.TICK_DURATION

            # Process burn DoT on primary target
            if theme_state.burn_ticks_remaining > 0:
                for m in monsters:
                    if m['alive'] and m['stats'].is_alive():
                        burn_actual = m['stats'].take_damage(theme_state.burn_damage)
                        combat.damage_dealt += burn_actual
                        combat.add_log(f"  [Burn] {m['comp'].name} takes {burn_actual} fire damage!")
                        break
                theme_state.burn_ticks_remaining -= 1

            # Player attacks
            if current_time >= combat.next_attack_tick:
                # Demonic: Pay HP cost before attacking
                if theme_state.demonic_hp_cost_percent > 0:
                    hp_cost = max(1, int(player_stats.current_hp * theme_state.demonic_hp_cost_percent))
                    player_stats.current_hp = max(1, player_stats.current_hp - hp_cost)
                    combat.add_log(f"  [Demonic] You spend {hp_cost} HP!")

                # Find first alive monster as primary target
                primary_target = None
                for m in monsters:
                    if m['alive'] and m['stats'].is_alive():
                        primary_target = m
                        break

                if primary_target:
                    # Primary target takes full damage
                    damage, is_crit = self._calculate_damage(player_stats, primary_target['stats'])

                    # Demonic: Damage scales with MISSING HP
                    if theme_state.demonic_has_item:
                        missing_hp_pct = 1.0 - (player_stats.current_hp / max(1, player_stats.max_hp))
                        demonic_mult = theme_state.demonic_base_mult + missing_hp_pct * 0.5
                        bonus = int(damage * demonic_mult)
                        damage += bonus
                        if missing_hp_pct > 0.3:
                            combat.add_log(f"  [Blood Rage] +{int(demonic_mult*100)}% damage!")

                    # Soaked enemies take +25% damage
                    if theme_state.enemy_soaked:
                        damage = int(damage * 1.25)

                    actual_damage = primary_target['stats'].take_damage(damage)
                    combat.damage_dealt += actual_damage

                    crit_text = "CRIT! " if is_crit else ""
                    combat.add_log(
                        f"[{current_time:.1f}s] {crit_text}You hit {primary_target['comp'].name} for {actual_damage}! "
                        f"({primary_target['stats'].current_hp} HP)"
                    )

                    # Steampunk: Pressure system
                    if theme_state.steam_burst_damage > 0:
                        theme_state.pressure += 1
                        if theme_state.pressure >= theme_state.pressure_threshold:
                            burst = primary_target['stats'].take_damage(theme_state.steam_burst_damage)
                            combat.damage_dealt += burst
                            theme_state.pressure = 0
                            combat.add_log(f"  [Steampunk] STEAM BURST! +{burst} damage!")

                    # Magical: Mana burst with amplification
                    if theme_state.mana_burst_chance > 0 and random.random() < theme_state.mana_burst_chance:
                        amp_mult = 1.0 + theme_state.arcane_amplification * 0.25
                        burst_damage = int(theme_state.mana_burst_damage * amp_mult)
                        burst_actual = primary_target['stats'].take_damage(burst_damage)
                        combat.damage_dealt += burst_actual
                        theme_state.arcane_amplification = min(theme_state.arcane_amplification + 1, 3)
                        combat.add_log(f"  [Mana Burst] +{burst_actual} arcane damage!")
                    elif theme_state.mana_burst_chance > 0:
                        theme_state.arcane_amplification = 0

                    # Cyberpunk: Neural hack
                    if theme_state.hack_chance > 0 and random.random() < theme_state.hack_chance:
                        theme_state.enemy_hacked = True
                        combat.add_log("  [Cyberpunk] Neural hack!")

                    # Life steal on primary damage
                    if player_stats.life_steal > 0 and actual_damage > 0:
                        heal = int(actual_damage * player_stats.life_steal)
                        player_stats.heal(heal)

                    # Angelic: Heal percent of damage dealt
                    if theme_state.angelic_heal_percent > 0 and actual_damage > 0:
                        heal_mult = 2.0 if (theme_state.desperate_healing and player_stats.current_hp < player_stats.max_hp * 0.25) else 1.0
                        angelic_heal = int(actual_damage * theme_state.angelic_heal_percent * heal_mult)
                        if angelic_heal > 0:
                            player_stats.heal(angelic_heal)
                            combat.add_log(f"  [Angelic] +{angelic_heal} HP!")

                    # Wind: Gust
                    if theme_state.gust_chance > 0 and random.random() < theme_state.gust_chance:
                        gust_damage, gust_crit = self._calculate_damage(player_stats, primary_target['stats'])
                        gust_actual = primary_target['stats'].take_damage(gust_damage)
                        combat.damage_dealt += gust_actual
                        gust_crit_text = "CRIT " if gust_crit else ""
                        combat.add_log(f"  [Wind] {gust_crit_text}GUST! +{gust_actual} damage!")

                    # Process elemental procs
                    for element, scale in elemental_items:
                        self._process_elemental_proc(
                            element, scale, theme_state, combat, current_time, player_stats
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
                            kill_gold = m['comp'].gold_reward
                            # Cyberpunk: bonus gold on kill
                            if theme_state.bonus_gold_percent > 0:
                                bonus = int(kill_gold * theme_state.bonus_gold_percent)
                                kill_gold += bonus
                                combat.add_log(f"  [Cyberpunk] +{bonus} bonus gold!")
                            total_gold += kill_gold
                            combat.add_log(f"  {m['comp'].name} defeated!")

                # Schedule next attack
                attack_interval = 1.0 / max(0.1, player_stats.attack_speed)
                combat.next_attack_tick = current_time + attack_interval

            # All alive monsters attack player
            for m in monsters:
                if not m['alive'] or not m['stats'].is_alive():
                    continue

                if current_time >= m['next_attack']:
                    # Check if monsters are paralyzed
                    if current_time < theme_state.paralyzed_until:
                        combat.add_log(f"  [Paralyzed] {m['comp'].name} cannot attack!")
                        attack_interval = 1.0 / max(0.1, m['stats'].attack_speed)
                        m['next_attack'] = current_time + attack_interval
                        continue
                    # Check if monsters are flinched (only first monster consumes flinch)
                    if theme_state.enemy_flinched:
                        combat.add_log(f"  [Flinched] {m['comp'].name} skips attack!")
                        theme_state.enemy_flinched = False
                        attack_interval = 1.0 / max(0.1, m['stats'].attack_speed)
                        m['next_attack'] = current_time + attack_interval
                        continue

                    damage, enemy_crit = self._calculate_damage(m['stats'], player_stats)
                    actual_damage = player_stats.take_damage(damage)
                    combat.damage_taken += actual_damage

                    crit_text = "CRIT! " if enemy_crit else ""
                    combat.add_log(
                        f"[{current_time:.1f}s] {crit_text}{m['comp'].name} hits you for {actual_damage}! "
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

        # Get first monster's stats for battle scene (use sum of max HP for multi-combat)
        total_monster_hp = sum(m['stats'].max_hp for m in monsters)
        first_monster_sprite = monsters[0]['comp'].sprite_name if monsters else "goblin"

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
            monster_max_hp=total_monster_hp,
            monster_sprite=first_monster_sprite,
        )

    def _process_tick(
        self,
        player_id: int,
        monster_id: int,
        combat: CombatStateComponent,
        player_stats: StatsComponent,
        monster_stats: StatsComponent,
        theme_state: Optional[ThemeEffectState] = None,
        elemental_items: Optional[List[tuple]] = None,
    ) -> None:
        """Process one tick of combat."""
        combat.combat_tick += 1
        current_time = combat.combat_tick * self.TICK_DURATION

        # Initialize theme state if not provided
        if theme_state is None:
            theme_state = ThemeEffectState()
        if elemental_items is None:
            elemental_items = []

        # Update soaked status
        if theme_state.enemy_soaked and current_time >= theme_state.soaked_until:
            theme_state.enemy_soaked = False

        # Process burn DoT at start of tick
        if theme_state.burn_ticks_remaining > 0:
            burn_actual = monster_stats.take_damage(theme_state.burn_damage)
            combat.damage_dealt += burn_actual
            theme_state.burn_ticks_remaining -= 1
            stack_text = f" (x{theme_state.burn_stacks})" if theme_state.burn_stacks > 1 else ""
            combat.add_log(f"  [Burn{stack_text}] Enemy takes {burn_actual} fire damage!")

        # Player attack
        if current_time >= combat.next_attack_tick:
            theme_state.attack_count += 1

            # Demonic: Pay HP cost before attacking
            if theme_state.demonic_hp_cost_percent > 0:
                hp_cost = max(1, int(player_stats.current_hp * theme_state.demonic_hp_cost_percent))
                player_stats.current_hp = max(1, player_stats.current_hp - hp_cost)
                combat.add_log(f"  [Demonic] Blood sacrifice: -{hp_cost} HP!")

            damage, is_crit = self._calculate_damage(player_stats, monster_stats)

            # Demonic: Damage scales with MISSING HP
            if theme_state.demonic_has_item:
                missing_hp_pct = 1.0 - (player_stats.current_hp / max(1, player_stats.max_hp))
                demonic_mult = theme_state.demonic_base_mult + missing_hp_pct * 0.5  # Up to +50% at low HP
                bonus = int(damage * demonic_mult)
                damage += bonus
                if missing_hp_pct > 0.3:
                    combat.add_log(f"  [Blood Rage] {int(missing_hp_pct*100)}% HP missing = +{int(demonic_mult*100)}% damage!")

            # Soaked enemies take +25% damage
            if theme_state.enemy_soaked:
                bonus = int(damage * 0.25)
                damage += bonus

            # Paralyzed enemies take +30% damage
            if current_time < theme_state.paralyzed_until:
                bonus = int(damage * theme_state.paralyzed_damage_bonus)
                damage += bonus

            actual_damage = monster_stats.take_damage(damage)
            combat.damage_dealt += actual_damage

            crit_text = "CRIT! " if is_crit else ""
            combat.add_log(
                f"[{current_time:.1f}s] {crit_text}You deal {actual_damage} damage! "
                f"(Enemy: {monster_stats.current_hp} HP)"
            )

            # Steampunk: Build pressure, release steam burst
            if theme_state.steam_burst_damage > 0:
                theme_state.pressure += 1
                if theme_state.pressure >= theme_state.pressure_threshold:
                    burst = monster_stats.take_damage(theme_state.steam_burst_damage)
                    combat.damage_dealt += burst
                    theme_state.pressure = 0
                    combat.add_log(f"  [Steampunk] STEAM BURST! +{burst} damage!")

            # Magical: Mana burst with arcane amplification
            if theme_state.mana_burst_chance > 0 and random.random() < theme_state.mana_burst_chance:
                # Amplification: consecutive bursts do more damage
                amp_mult = 1.0 + theme_state.arcane_amplification * 0.25
                burst_damage = int(theme_state.mana_burst_damage * amp_mult)
                burst_actual = monster_stats.take_damage(burst_damage)
                combat.damage_dealt += burst_actual
                theme_state.arcane_amplification = min(theme_state.arcane_amplification + 1, 3)
                amp_text = f" [x{theme_state.arcane_amplification} AMPLIFIED]" if theme_state.arcane_amplification > 1 else ""
                combat.add_log(f"  [Mana Burst] +{burst_actual} arcane damage!{amp_text}")
            else:
                # Reset amplification on miss
                if theme_state.mana_burst_chance > 0:
                    theme_state.arcane_amplification = 0

            # Cyberpunk: Neural hack chance
            if theme_state.hack_chance > 0 and random.random() < theme_state.hack_chance:
                theme_state.enemy_hacked = True
                combat.add_log("  [Cyberpunk] Neural hack! Enemy systems compromised!")

            # Life steal
            if player_stats.life_steal > 0 and actual_damage > 0:
                heal = int(actual_damage * player_stats.life_steal)
                player_stats.heal(heal)
                if heal > 0:
                    combat.add_log(f"  [Life steal: +{heal} HP]")

            # Angelic: Heal percent of damage dealt (doubled when desperate)
            if theme_state.angelic_heal_percent > 0 and actual_damage > 0:
                heal_mult = 2.0 if (theme_state.desperate_healing and player_stats.current_hp < player_stats.max_hp * 0.25) else 1.0
                angelic_heal = int(actual_damage * theme_state.angelic_heal_percent * heal_mult)
                if angelic_heal > 0:
                    player_stats.heal(angelic_heal)
                    desperate_text = " (DESPERATE!)" if heal_mult > 1 else ""
                    combat.add_log(f"  [Angelic] Divine heal +{angelic_heal} HP!{desperate_text}")

            # Wind: Gust - chance for free extra attack
            if theme_state.gust_chance > 0 and random.random() < theme_state.gust_chance:
                gust_damage, gust_crit = self._calculate_damage(player_stats, monster_stats)
                gust_actual = monster_stats.take_damage(gust_damage)
                combat.damage_dealt += gust_actual
                gust_crit_text = "CRIT " if gust_crit else ""
                combat.add_log(f"  [Wind] {gust_crit_text}GUST! Free attack for {gust_actual} damage!")

            # Earth: Tremor every 4th attack
            if theme_state.earth_damage_reduction > 0 and theme_state.attack_count % 4 == 0:
                combat.opponent_next_attack_tick += theme_state.tremor_delay
                combat.add_log("  [Earth] TREMOR! Ground shakes!")

            # Process elemental procs
            for element, scale in elemental_items:
                self._process_elemental_proc(
                    element, scale, theme_state, combat, current_time, player_stats
                )

            # Schedule next attack
            attack_interval = 1.0 / max(0.1, player_stats.attack_speed)
            combat.next_attack_tick = current_time + attack_interval

        # Monster attack
        if current_time >= combat.opponent_next_attack_tick:
            # Check if monster is paralyzed
            if current_time < theme_state.paralyzed_until:
                combat.add_log(f"  [Paralyzed] Enemy cannot attack!")
                attack_interval = 1.0 / max(0.1, monster_stats.attack_speed)
                combat.opponent_next_attack_tick = current_time + attack_interval
            # Check if monster is flinched
            elif theme_state.enemy_flinched:
                combat.add_log(f"  [Flinched] Enemy skips attack!")
                theme_state.enemy_flinched = False
                attack_interval = 1.0 / max(0.1, monster_stats.attack_speed)
                combat.opponent_next_attack_tick = current_time + attack_interval
            else:
                damage, enemy_crit = self._calculate_damage(monster_stats, player_stats)

                # Boss special moves - get monster component to check for special moves
                monster_comp = self.world.get_component(monster_id, MonsterComponent)
                special_move_name = None
                special_move_anim = None
                if monster_comp and hasattr(monster_comp, 'special_moves') and monster_comp.special_moves:
                    move = random.choice(monster_comp.special_moves)
                    special_move_name = move.get('name', 'Attack')
                    special_move_anim = move.get('animation', 'attack')
                    damage_mult = move.get('damage_mult', 1.0)
                    damage = int(damage * damage_mult)

                # Cyberpunk: Hacked enemy deals 40% less damage
                if theme_state.enemy_hacked:
                    damage = int(damage * 0.6)
                    theme_state.enemy_hacked = False
                    combat.add_log("  [Hacked] Enemy attack weakened!")

                # Earth: Damage reduction
                if theme_state.earth_damage_reduction > 0:
                    reduction = int(damage * theme_state.earth_damage_reduction)
                    damage -= reduction

                actual_damage = player_stats.take_damage(damage)
                crit_text = "CRIT! " if enemy_crit else ""
                combat.damage_taken += actual_damage

                # Log with special move name if boss
                if special_move_name:
                    combat.add_log(
                        f"[{current_time:.1f}s] {crit_text}Enemy uses {special_move_name}! {actual_damage} damage! "
                        f"(You: {player_stats.current_hp} HP)"
                    )
                else:
                    combat.add_log(
                        f"[{current_time:.1f}s] {crit_text}Enemy deals {actual_damage} damage! "
                        f"(You: {player_stats.current_hp} HP)"
                    )

                # Schedule next attack
                attack_interval = 1.0 / max(0.1, monster_stats.attack_speed)
                combat.opponent_next_attack_tick = current_time + attack_interval

        # Check end conditions
        if not monster_stats.is_alive():
            # Demonic: Soul Harvest - heal on kill
            if theme_state.soul_harvest_percent > 0:
                heal = int(player_stats.max_hp * theme_state.soul_harvest_percent)
                player_stats.heal(heal)
                combat.add_log(f"  [Soul Harvest] Devoured soul! +{heal} HP!")
            combat.add_log("Enemy defeated!")
            combat.in_combat = False
        elif not player_stats.is_alive():
            # Angelic: Guardian Angel - survive fatal damage ONCE
            if theme_state.guardian_angel_ready:
                player_stats.current_hp = 1
                theme_state.guardian_angel_ready = False
                combat.add_log("  [Guardian Angel] DIVINE INTERVENTION! You survive with 1 HP!")
            else:
                combat.add_log("You have been defeated...")
            combat.in_combat = False

    def _calculate_damage(
        self,
        attacker: StatsComponent,
        defender: StatsComponent,
    ) -> tuple:
        """
        Calculate damage for a single attack.

        Returns:
            Tuple of (damage: int, is_crit: bool)
        """
        # Base damage
        damage = attacker.base_damage

        # Critical hit check
        is_crit = random.random() < attacker.crit_chance
        if is_crit:
            damage *= attacker.crit_multiplier

        # Dodge check
        if random.random() < defender.dodge_chance:
            return (0, False)

        # Apply defense (flat reduction)
        damage -= defender.defense

        # Apply resistance (percentage reduction)
        damage *= (1 - defender.resistance)

        # Add true damage (ignores defenses)
        damage += attacker.true_damage

        # Minimum 1 damage
        return (max(1, int(damage)), is_crit)

    def update(self, delta_time: float) -> None:
        """Not used - combat is run synchronously."""
        pass
