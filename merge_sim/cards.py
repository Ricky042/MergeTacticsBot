# === CARD DATA ===
CARD_STATS = {
    "knight": 2,
    "archer": 2,
    "goblin": 2,
    "spear-goblin": 2,
    "bomber": 2,
    "barbarian": 2,
    "valkyrie": 3,
    "pekka": 3,
    "prince": 3,
    "giant-skeleton": 3,
    "dart-goblin": 3,
    "executioner": 3,
    "princess": 4,
    "mega-knight": 4,
    "royal-ghost": 4,
    "bandit": 4,
    "goblin-machine": 4,
    "skeleton-king": 5,
    "golden-knight": 5,
    "archer-queen": 5,
}

CUSTOM_ABBREVIATIONS = {
    "knight": "Kn",
    "archer": "Ar",
    "goblin": "Gb",
    "spear-goblin": "SG",
    "bomber": "Bm",
    "barbarian": "Br",
    "valkyrie": "Va",
    "pekka": "Pk",
    "prince": "Pr",
    "giant-skeleton": "GS",
    "dart-goblin": "DG",
    "executioner": "Ex",
    "princess": "Ps",
    "mega-knight": "MK",
    "royal-ghost": "RG",
    "bandit": "Bd",
    "goblin-machine": "GM",
    "skeleton-king": "SK",
    "golden-knight": "GK",
    "archer-queen": "AQ",
}

BASE_TROOP_STATS = {
    "knight": {"health": 1186, "damage": 59, "range": 1, "speed": 2, "attack_speed": 1.66},
    "archer": {"health": 474, "damage": 83, "range": 4, "speed": 2, "attack_speed": 1.0},
    "goblin": {"health": 498, "damage": 106, "range": 1, "speed": 2, "attack_speed": 0.66},
    "spear-goblin": {"health": 354, "damage": 153, "range": 3, "speed": 2, "attack_speed": 1.66},
    "bomber": {"health": 474, "damage": 106, "range": 3, "speed": 2, "attack_speed": 1.42},
    "barbarian": {"health": 830, "damage": 94, "range": 1, "speed": 2, "attack_speed": 1.0},
    "valkyrie": {"health": 1255, "damage": 125, "range": 1, "speed": 2, "attack_speed": 1.66},
    "pekka": {"health": 1293, "damage": 363, "range": 1, "speed": 1, "attack_speed": 2.5},
    "prince": {"health": 858, "damage": 118, "range": 1, "speed": 2, "attack_speed": 1.25},
    "giant-skeleton": {"health": 969, "damage": 53, "range": 1, "speed": 1, "attack_speed": 1.66},
    "dart-goblin": {"health": 627, "damage": 79, "range": 4, "speed": 2, "attack_speed": 0.83},
    "executioner": {"health": 757, "damage": 130, "range": 4, "speed": 2, "attack_speed": 2.0},
    "princess": {"health": 613, "damage": 163, "range": 6, "speed": 2, "attack_speed": 2.0},
    "mega-knight": {"health": 1527, "damage": 101, "range": 1, "speed": 1, "attack_speed": 1.66},
    "royal-ghost": {"health": 872, "damage": 133, "range": 1, "speed": 2, "attack_speed": 1.0},
    "bandit": {"health": 821, "damage": 82, "range": 1, "speed": 2, "attack_speed": 1.11},
    "goblin-machine": {"health": 1128, "damage": 82, "range": 1, "speed": 2, "attack_speed": 1},
    "skeleton-king": {"health": 1377, "damage": 177, "range": 1, "speed": 1, "attack_speed": 2},
    "golden-knight": {"health": 1191, "damage": 139, "range": 1, "speed": 2, "attack_speed": 1.25},
    "archer-queen": {"health": 840, "damage": 88, "range": 4, "speed": 2, "attack_speed": 1.25},
    "skeleton": {"health": 610, "damage": 73, "range": 1, "speed": 2, "attack_speed": 1.43},
}

# modifiers per card
CARD_MODIFIERS = {
    "archer": ["clan", "ranger"],
    "barbarian": ["clan", "brawler"],
    "valkyrie": ["clan", "avenger"],
    "archer-queen": ["clan", "avenger"],
    "giant-skeleton": ["brawler", "undead"],
    "mega-knight": ["brawler", "ace"],
    "prince": ["brawler", "noble"],
    "princess": ["ranger", "noble"],
    "golden-knight": ["assassin", "noble"],
    "knight": ["juggernaut", "noble"],
    # later: "royal-ghost": ["undead", "invisible"], etc.
}

class Card:
    def __init__(self, name, cost, star=1):
        self.name = name
        self.cost = cost
        self.star = star
        self.base_stats = BASE_TROOP_STATS.get(name, {})
        self.range = self.base_stats.get("range", 1)
        self.speed = self.base_stats.get("speed", 1.0)
        self.attack_speed = self.base_stats.get("attack_speed", 1.0)
        self.crit_chance = 0.15  # default crit chance
        self.modifiers = CARD_MODIFIERS.get(name, [])

    @property
    def health(self):
        return self._scaled_stat("health")

    @property
    def damage(self):
        return self._scaled_stat("damage")

    def _scaled_stat(self, key):
        base = self.base_stats.get(key, 0)
        multiplier = 2 ** (self.star - 1)
        return base * multiplier

    def __repr__(self):
        return f"{self.name} ({self.cost}💧, {self.star}✨)"

def card_to_symbol(card, team=None):
    base_name = card.name.lower()
    abbrev = CUSTOM_ABBREVIATIONS.get(base_name, ''.join(w[:2].capitalize() for w in base_name.split('-')))
    symbol = f"{abbrev}{card.star}"
    return symbol
