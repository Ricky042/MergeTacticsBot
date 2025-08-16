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