# --- Standard Libraries ---
import random
from collections import deque

# --- Globals / Shared State ---
from .constants import BOARD_ROWS, BOARD_COLS

# --- Cards ---
from .cards import (
    Card,
    CARD_STATS
)

# --- Combat / Player Units ---
from .combat_unit import CombatUnit

# --- Bots ---
from .bot import *

def get_player_colour(player_name):
    """Return ANSI colour code based on player name."""
    colours = {
        "Greedy": "\033[94m",    # Blue
        "Efficient": "\033[92m", # Green
        "ComboSeeker": "\033[93m", # Yellow
        "Random": "\033[91m",    # Red
    }
    return colours.get(player_name, "\033[0m")  # Default no colour

class Player:
    def __init__(self, name, deck_manager, bot_logic):
        self.name = name
        self.deck_manager = deck_manager
        self.bot_logic = bot_logic
        self.hand = deck_manager.draw_hand()
        self.field = []      # List of CombatUnit instances on the field
        self.bench = []      # List of CombatUnit instances on the bench
        self.elixir = 0
        self.hp = 10
        self.grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
        self.opponent = None
        self.team_id = None  # Add a team ID or number if needed

    def max_field_slots(self, round_number):
        return min(round_number + 1, 6)

    def has_space(self, round_number):
        return len(self.field) < self.max_field_slots(round_number) or len(self.bench) < 5

    def buy_card(self, card_name, round_number):
        for card in self.hand:
            if card.name == card_name and card.cost <= self.elixir:
                self.elixir -= card.cost
                self.deck_manager.return_cards(self.hand)
                self.hand = self.deck_manager.draw_hand()
                merged_card = self.try_merge(card)
                
                # Create CombatUnit instance
                new_unit = CombatUnit(None, None, merged_card, owner=self)

                max_field = self.max_field_slots(round_number)

                if len(self.field) < max_field:
                    self.field.append(new_unit)
                    placed = self.place_on_grid_random(new_unit)
                    if placed:
                        print(f"{self.name} buys and places {new_unit.card.name} on the field at {placed}. Elixir left: {self.elixir}")
                    else:
                        print(f"{self.name} buys {new_unit.card.name} but no grid space found! Placed in field list only.")
                elif len(self.bench) < 5:
                    self.bench.append(new_unit)
                    print(f"{self.name} buys and places {new_unit.card.name} on the bench. Elixir left: {self.elixir}")
                else:
                    self.elixir += card.cost
                    self.deck_manager.return_cards([merged_card])
                    print(f"{self.name} cannot place {new_unit.card.name}, no space. Refunded elixir.")
                    return False
                return True
        return False

    def place_on_grid_random(self, unit):
        positions = [(r, c) for r in range(4, 8) for c in range(BOARD_COLS) if self.grid[r][c] is None]
        if not positions:
            return None
        row, col = random.choice(positions)
        self.grid[row][col] = unit
        unit.row = row
        unit.col = col
        print(f"DEBUG: Placed {unit.card.name} at ({unit.row}, {unit.col}) on grid. Grid cell contains: {self.grid[row][col].card.name}")
        return (row, col)
    
    def remove_unit_from_grid(self, unit):
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                if self.grid[r][c] == unit:
                    self.grid[r][c] = None
                    unit.row = None
                    unit.col = None

    def try_merge(self, new_card):
        zones = [('field', self.field), ('bench', self.bench)]
        for zone_name, zone in zones:
            for i, unit in enumerate(zone):
                if unit.card.name == new_card.name and unit.card.star == new_card.star:
                    removed_unit = zone.pop(i)
                    self.remove_unit_from_grid(removed_unit)
                    refund = 1
                    upgraded_card = Card(new_card.name, new_card.cost, new_card.star + 1)
                    self.elixir += refund
                    print(f"⚠️  MERGE: {new_card.name} {new_card.star}✨ + {removed_unit.card.star}✨ → {upgraded_card.star}✨! +{refund}💧")
                    # recursively try to merge upgraded card again
                    return self.try_merge(upgraded_card) or upgraded_card
        return new_card

    def give_starting_unit(self):
        two_elixir_cards = [name for name, cost in CARD_STATS.items() if cost == 2]
        name = random.choice(two_elixir_cards)
        card = Card(name, 2, star=1)
        unit = CombatUnit(None, None, card, owner=self)
        self.field.append(unit)
        self.place_on_grid_random(unit)
        print(f"{self.name} starts with {unit.card.name}")

    def give_starting_exe(self):
        starting_units = [
            {"name": "pekka", "cost": 3, "star": 1},
            {"name": "mega-knight", "cost": 4, "star": 1},
            {"name": "bandit", "cost": 4, "star": 1},
            {"name": "executioner", "cost": 3, "star": 2},
        ]

        for unit_info in starting_units:
            card = Card(unit_info["name"], unit_info["cost"], star=unit_info["star"])
            unit = CombatUnit(None, None, card, owner=self)
            self.field.append(unit)
            placed = self.place_on_grid_random(unit)
            print(f"{self.name} starts with {unit.card.name} placed at {placed}")


    def display_zone(self, round_number):
        hp_display = f"❤️{self.hp}"
        print(f"{self.name} {hp_display} FIELD ({len(self.field)}/{self.max_field_slots(round_number)}): " +
              ", ".join([f"{unit.card.name} {unit.card.star}✨ (HP: {unit.current_hp})" for unit in self.field]))
        print(f"{self.name} BENCH ({len(self.bench)}/5): " +
              ", ".join([f"{unit.card.name} {unit.card.star}✨ (HP: {unit.max_hp})" for unit in self.bench]))

    def take_damage(self, damage):
        self.hp -= damage
        print(f"💀 {self.name} takes {damage} damage! HP: {self.hp}")
        if self.hp <= 0:
            print(f"💀 {self.name} has been eliminated!")

    def act(self, round_number):
        return self.bot_logic(self, round_number)