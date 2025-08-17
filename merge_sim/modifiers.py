import random
from .cards import create_card
from .combat_unit import CombatUnit

class ClanSynergyManager:
    def __init__(self, owner):
        self.owner = owner      # player
        self.clan_count = 0
        self.triggered_units = set()

    def setup_round(self):
        self.triggered_units.clear()
        self.clan_count = sum(
            1 for u in getattr(self.owner, "field", [])
            if "clan" in u.card.modifiers
        )

        print(f"🛡️ Clan units at round start: {self.clan_count}")

    def trigger(self, unit):
        """
        Call whenever a unit's HP changes.
        Applies heal + attack speed buff according to clan rules.
        """
        if unit in self.triggered_units:
            return  # already triggered

        if unit.current_hp > unit.max_hp * 0.5:
            return  # not below 50%
        
        if self.clan_count < 2:
            return

        self.triggered_units.add(unit)

        # Determine heal + buff
        if self.clan_count >= 4:
            # Any unit gets 30% buff/heal
            heal = unit.max_hp * 0.3
            attack_speed_buff = 0.3

            if "clan" in unit.card.modifiers:
                # Clan units get 60% instead
                heal = unit.max_hp * 0.6
                attack_speed_buff = 0.6
        else:  # 2 <= clan_count < 4
            if "clan" not in unit.card.modifiers:
                return  # non-clan units get nothing
            heal = unit.max_hp * 0.3
            attack_speed_buff = 0.3

        # Apply self buff
        unit.status_effects["clan_buff"] = 3.0  # duration in seconds
        unit.status_effects["clan_heal"] = heal  # store total heal, spread over 3s
        unit.status_effects["clan_heal_duration"] = 3.0  # track remaining heal duration

        print(f"✨ Clan synergy triggered for {unit.card.name}! "
              f"Heal: {int(heal)}, Attack Speed buff: {int(attack_speed_buff*100)}% for 3s")

class BrawlerSynergyManager:
    def __init__(self, owner):
        self.owner = owner
        self.brawler_count = 0  # Number of Brawler cards at round start

    def setup_round(self):
        """Count Brawlers at round start and apply bonuses."""
        self.brawler_count = sum(
            1 for u in getattr(self.owner, "field", [])
            if "brawler" in u.card.modifiers
        )
        print(f"🤜 Brawler units at round start: {self.brawler_count}")

        if self.brawler_count < 2:
            return  # Not enough Brawlers for any bonus

        # Apply tiered bonus to Brawlers themselves
        for unit in getattr(self.owner, "field", []):
            if "brawler" in unit.card.modifiers:
                bonus_multiplier = 0.8 if self.brawler_count >= 4 else 0.4
                unit.max_hp = int(unit.max_hp * (1 + bonus_multiplier))
                unit.current_hp = unit.max_hp
                print(f"💪 {unit.card.name} HP increased by {int(bonus_multiplier*100)}%")

        # Apply team-wide bonus if 4 or more Brawlers
        if self.brawler_count >= 4:
            for unit in getattr(self.owner, "field", []):
                if "brawler" not in unit.card.modifiers:
                    unit.max_hp = int(unit.max_hp * 1.3)
                    unit.current_hp = unit.max_hp
                    print(f"✨ {unit.card.name} HP increased by 30% for team Brawler bonus")

class NobleSynergyManager:
    def __init__(self, owner, is_top_player=False):
        self.owner = owner
        self.noble_count = 0  # number of Noble troops at round start
        self.is_top_player = is_top_player


    def setup_round(self):
        """Call at start of round to apply Noble bonuses."""
        # Count Noble units
        self.noble_count = sum(
            1 for u in getattr(self.owner, "field", [])
            if "noble" in u.card.modifiers
        )

        print(f"👑 Noble units at round start: {self.noble_count}")

        # Determine bonuses based on count
        if self.noble_count >= 4:
            frontline_reduction = 0.4  # 40% less damage taken
            backline_bonus = 0.4       # 40% more damage dealt
        elif self.noble_count >= 2:
            frontline_reduction = 0.2
            backline_bonus = 0.2
        else:
            # Not enough nobles to trigger bonus
            return

        # Apply bonuses only to noble units
        for unit in getattr(self.owner, "field", []):
            if "noble" not in unit.card.modifiers:
                continue  # skip non-noble units

            # Determine if unit is frontline or backline relative to player
            if self.is_top_player:
                # Bottom player
                frontline_rows = {2, 3}
                backline_rows = {0, 1}
            else:
                # Top player
                frontline_rows = {4, 5}
                backline_rows = {6, 7}

            if unit.row in frontline_rows:
                unit.noble_damage_taken_multiplier = 1 - frontline_reduction
                unit.noble_damage_dealt_multiplier = 1.0
            elif unit.row in backline_rows:
                unit.noble_damage_dealt_multiplier = 1 + backline_bonus
                unit.noble_damage_taken_multiplier = 1.0
            else:
                # Middle row: no bonus
                unit.noble_damage_taken_multiplier = 1.0
                unit.noble_damage_dealt_multiplier = 1.0

            print(f"🛡️ {unit.card.name} (Owner: {unit.owner.name}) "
                  f"Noble bonus applied: "
                  f"Damage taken x{unit.noble_damage_taken_multiplier:.2f}, "
                  f"Damage dealt x{unit.noble_damage_dealt_multiplier:.2f}")

class GoblinSynergyManager:
    def __init__(self, owner):
        self.owner = owner               # reference to player
        self.goblin_count_last_combat = 0
        self.pending_reward = None       # reward type to grant next buy phase

    def setup_round(self):
        """Reset at start of each round."""
        self.goblin_count_last_combat = 0
        self.pending_reward = None
        goblin_names = set()

        for unit in getattr(self.owner, "field", []):
            if unit.alive and "goblin" in getattr(unit.card, "modifiers", []):
                goblin_names.add(unit.card.name.lower())

        self.goblin_count_last_combat = len(goblin_names)
        print(f"👺 Goblins units at round start: {len(goblin_names)}")

        # Decide what reward to prepare
        if self.goblin_count_last_combat >= 4:
            if random.random() < 0.6:
                self.pending_reward = "high"   # Dart Goblin or Goblin Machine
            else:
                self.pending_reward = "mid"    # Goblin or Spear Goblin
        elif self.goblin_count_last_combat >= 2:
            self.pending_reward = "mid"
        else:
            self.pending_reward = None

    def on_buy_phase_start(self, round_number):
        """At the start of buy phase, give the pending goblin reward."""
        if not self.pending_reward:
            return

        # Pick which goblin to spawn
        if self.pending_reward == "mid":
            card_name = random.choice(["goblin", "spear-goblin"])
        elif self.pending_reward == "high":
            card_name = random.choice(["dart-goblin", "goblin-machine"])
        else:
            return

        # Create the card
        new_card = create_card(card_name)
        # Check for merges first (like buying normally)
        merged_unit = self.owner.try_merge(new_card)

        # Wrap in CombatUnit
        new_unit = CombatUnit(row=None, col=None, card=merged_unit, owner=self.owner)

        # --- Place on bench only ---
        max_bench = 5
        if len(self.owner.bench) < max_bench:
            self.owner.bench.append(new_unit)
            print(f"🟢 Goblin Synergy: {self.owner.name} gained a free {card_name} and placed on bench")
        else:
            # No space anywhere, discard
            print(f"🟡 Goblin Synergy: {self.owner.name} could not place free {card_name}, no space")

        # Reset reward so it doesn’t fire twice
        self.pending_reward = None

class ThrowerSynergyManager:
    def __init__(self, owner):
        self.owner = owner
        self.thrower_active = False
        self.buffed_units = []   # <<< initialize this list here

    def setup_round(self):
        """Apply thrower buffs when 3 unique throwers are present."""
        thrower_units = [
            u for u in getattr(self.owner, "field", [])
            if "thrower" in getattr(u.card, "modifiers", [])
        ]
        unique_throwers = {u.card.name for u in thrower_units}

        print(f"🏹 {self.owner.name} has {len(unique_throwers)} unique throwers at start of round")


        if len(unique_throwers) >= 3:
            self.thrower_active = True
            for u in thrower_units:
                if not getattr(u, "_thrower_buffed", False):
                    u.card.range += 1
                    u._thrower_buffed = True
                    self.buffed_units.append(u)

    def reset_synergy(self):
        """Undo thrower buffs at end of combat."""
        for unit in self.buffed_units:
            if getattr(unit, "_thrower_buffed", False):
                unit.card.range -= 1
                unit._thrower_buffed = False
        self.buffed_units.clear()
        self.thrower_active = False

class UndeadSynergyManager:
    def __init__(self, owner):
        self.owner = owner                 # Reference to player
        self.cursed_enemies = []           # Currently cursed enemy units
        self.active_bonus = 0.0            # Cumulative damage bonus for all undead this round

    def setup_round(self):
        """Apply Undead synergy at the start of combat."""
        # Find all unique alive Undead units
        undead_units = []
        seen_names = set()
        for u in getattr(self.owner, "field", []):
            if u.alive and "undead" in getattr(u.card, "modifiers", []):
                if u.card.name.lower() not in seen_names:
                    undead_units.append(u)
                    seen_names.add(u.card.name.lower())

        print(f"🦴 Undead units on field: {len(undead_units)} unique")

        if len(undead_units) < 2:
            print(f"🦴 Undead synergy inactive, only {len(undead_units)} undead on field.")
            return  # Synergy does not activate
        
        # Determine number of enemies to curse
        enemy_count = len(self.owner.opponent.field)
        if len(undead_units) >= 4:
            num_to_curse = min(3, enemy_count)
            max_hp_cut = 0.5
        else:
            num_to_curse = min(2, enemy_count)
            max_hp_cut = 0.25

        # Identify highest HP enemies
        alive_enemies = [u for u in self.owner.opponent.field if u.alive]
        sorted_enemies = sorted(alive_enemies, key=lambda u: u.current_hp, reverse=True)
        self.cursed_enemies = sorted_enemies[:num_to_curse]

        # Apply HP reduction and mark as cursed
        for enemy in self.cursed_enemies:
            enemy.current_hp = min(enemy.current_hp, enemy.current_hp * (1 - max_hp_cut))
            enemy._undead_cursed = True  # Internal flag
            print(f"🦴 {enemy.card.name} cursed by Undead! Max HP reduced by {int(max_hp_cut*100)}%")

        self.active_bonus = 0.0  # Reset bonus at start

    def on_enemy_death(self, enemy):
        """Called when an enemy dies to check for curse triggers."""
        if getattr(enemy, "_undead_cursed", False):
            self.active_bonus += 0.3  # +30% damage
            print(f"🦴 {enemy.card.name} died, undead units gain +30% damage!")
            # Optional: remove the cursed flag
            enemy._undead_cursed = False

    def get_damage_multiplier(self, unit):
        """Return damage multiplier for a given unit based on undead synergy."""
        if "undead" in getattr(unit.card, "modifiers", []):
            return 1.0 + self.active_bonus
        return 1.0

class AvengerSynergyManager:
    def __init__(self, owner):
        self.owner = owner                  # Reference to the player
        self.avengers = []                  # List of alive Avenger units
        self.active_bonus = 0.0             # +30% bonus if synergy active
        self.last_standing_unit = None      # Reference to the last standing Avenger

    def setup_round(self):
        """Activate Avenger synergy at the start of combat."""

        # Reset per-round state
        self.active_bonus = 0.0
        self.last_standing_unit = None

        # Find all unique alive Avenger units
        self.avengers = [u for u in getattr(self.owner, "field", [])
                         if u.alive and "avenger" in getattr(u.card, "modifiers", [])]
        unique_count = len(set(self.avengers))
        print(f"🛡️ Avenger Synergy: {unique_count} unique Avenger units on the field.")

        if unique_count >= 3:
            self.active_bonus = 0.3
            print(f"🛡️ Avenger Synergy active: all Avengers gain +30% damage!")
        else:
            self.active_bonus = 0.0
            print(f"🛡️ Avenger Synergy inactive, less than 3 Avengers.")

        self.update_last_standing()  # Check if last standing applies at start

    def update_last_standing(self):
        """Check which Avenger is last alive for double damage."""
        if self.active_bonus == 0.0:
            return
        alive_avengers = [u for u in self.avengers if u.alive]
        if len(alive_avengers) == 1:
            self.last_standing_unit = alive_avengers[0]
        else:
            self.last_standing_unit = None

    def on_unit_death(self, unit):
        """Call when any Avenger dies to update last-standing logic."""
        if unit in self.avengers:
            print(f"⚔️ Avenger {unit.card.name} died, checking last-standing bonus.")
            self.update_last_standing()

    def get_damage_multiplier(self, unit):
        """Return damage multiplier for a given Avenger unit."""
        if "avenger" not in getattr(unit.card, "modifiers", []):
            return 1.0

        if unit == self.last_standing_unit:
            return 2.0  # double damage
        return 1.0 + self.active_bonus

class RangerSynergyManager:
    def __init__(self, owner):
        self.owner = owner                 # Reference to Player
        self.rangers = []                  # List of alive Ranger units
        self.active = False                # Whether synergy is active
        self.max_stacks = 15               # Maximum stacks per unit
        self.stack_bonus = 0.15            # 15% attack speed bonus per stack

    def setup_round(self):
        """Check if synergy is active at the start of combat and reset stacks."""
        # Reset
        self.active = False
        self.rangers.clear()

        # Find all unique alive Ranger units
        self.rangers = [u for u in getattr(self.owner, "field", [])
                        if u.alive and "ranger" in getattr(u.card, "modifiers", [])]
        unique_count = len(set(self.rangers))
        print(f"🏹 Ranger Synergy: {unique_count} unique Rangers on the field.")

        if unique_count >= 3:
            self.active = True
            print(f"🏹 Ranger Synergy active: Rangers gain +15% attack speed per attack, stacking up to {self.max_stacks}x.")
        else:
            self.active = False
            print(f"🏹 Ranger Synergy inactive, less than 3 Rangers.")

    def on_attack(self, unit):
        """Call this whenever a Ranger attacks to increment its stack."""
        if not self.active:
            return

        if "ranger" in getattr(unit.card, "modifiers", []):
            current_stacks = getattr(unit, "_ranger_stacks", 0)
            if current_stacks < self.max_stacks:
                unit._ranger_stacks = current_stacks + 1
                print(f"🏹 {unit.card.name} attacks! Ranger stacks: {unit._ranger_stacks}/{self.max_stacks}")

    def get_attack_speed_multiplier(self, unit):
        """Return multiplier for unit attack speed based on current stacks (exponential)."""
        if not self.active or "ranger" not in getattr(unit.card, "modifiers", []):
            return 1.0
        stacks = getattr(unit, "_ranger_stacks", 0)
        return (1.0 - self.stack_bonus) ** stacks

class AceSynergyManager:
    def __init__(self, owner):
        self.owner = owner
        self.captain = None
        self.unique_ace_units = []
        self.active = False
        self.team_hit_speed_bonus = 0.0  # temporary +20% on kills
        self.captain_damage_bonus = 0.0

    def setup_round(self):
        """Select Captain and apply damage bonuses based on number of Ace units."""
        # Reset
        self.active = False
        self.captain = None
        self.captain_damage_bonus = 0.0
        self.unique_ace_units = []

        # Find all alive Ace units
        self.unique_ace_units = [u for u in getattr(self.owner, "field", [])
                                 if u.alive and "ace" in getattr(u.card, "modifiers", [])]
        unique_count = len(set(self.unique_ace_units))
        print(f"🃏 Ace Synergy: {unique_count} unique Ace units on the field.")

        if unique_count < 2:
            self.active = False
            self.captain = None
            self.captain_damage_bonus = 0.0
            print("🃏 Ace Synergy inactive, less than 2 Ace units.")
            return

        self.active = True

        # --- Select Captain ---
        alive_units = [u for u in getattr(self.owner, "field", []) if u.alive]
        if not alive_units:
            self.captain = None
            return

        # Sort by highest star first, then highest elixir, then first added
        self.captain = sorted(alive_units, key=lambda u: (-u.card.star, -u.card.cost))[0]
        print(f"🃏 Captain selected: {self.captain.card.name} (Stars: {self.captain.card.star}, Cost: {self.captain.card.cost})")

        # --- Apply Captain damage bonus ---
        if unique_count >= 4:
            self.captain_damage_bonus = 0.6
            print("🃏 Captain gains +60% damage!")
        elif unique_count >= 2:
            self.captain_damage_bonus = 0.3
            print("🃏 Captain gains +30% damage!")

    def get_damage_multiplier(self, unit):
        """Return damage multiplier for a given unit."""
        if unit == self.captain:
            return 1.0 + self.captain_damage_bonus
        return 1.0

    def on_captain_deal_damage(self, damage_dealt):
        """Called whenever the Captain deals damage to an enemy."""
        if not self.active or self.captain is None:
            return

        # --- Heal Captain if 4+ Ace units ---
        if len(self.unique_ace_units) >= 4:
            heal_amount = 0.3 * damage_dealt
            self.captain.current_hp = min(self.captain.current_hp + heal_amount, self.captain.max_hp)
            print(f"🃏 Captain heals for {heal_amount} HP (30% of damage dealt)")

    def on_captain_kill(self, enemy):
        """Called whenever the Captain kills an enemy."""
        if not self.active or self.captain is None:
            return

        print(f"🃏 Captain killed {enemy.card.name}, team gains +20% attack speed for 4s")

        # Apply or refresh status effect on all alive team units
        for unit in getattr(self.owner, "field", []):
            if unit.alive:
                if not hasattr(unit, "status_effects"):
                    unit.status_effects = {}
                # Set or refresh duration (seconds)
                unit.status_effects["ace_hit_speed_bonus"] = 4.0

