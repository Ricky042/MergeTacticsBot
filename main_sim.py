import random
import copy
from collections import deque
from merge_sim.cards import Card, CARD_STATS, card_to_symbol, BASE_TROOP_STATS
from merge_sim.visualise import visualize_combat, draw_grid
import pygame

BOARD_ROWS = 8
BOARD_COLS = 5

class Player:
    def __init__(self, name, deck_manager, bot_logic):
        self.name = name
        self.deck_manager = deck_manager
        self.bot_logic = bot_logic
        self.hand = deck_manager.draw_hand()
        self.field = []
        self.bench = []
        self.elixir = 0
        self.hp = 10  # Player health
        self.grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
        self.opponent = None

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
                max_field = self.max_field_slots(round_number)

                if len(self.field) < max_field:
                    self.field.append(merged_card)
                    placed = self.place_on_grid_random(merged_card)
                    if placed:
                        print(f"{self.name} buys and places {merged_card} on the field at {placed}. Elixir left: {self.elixir}")
                    else:
                        print(f"{self.name} buys {merged_card} but no grid space found! Placed in field list only.")
                elif len(self.bench) < 5:
                    self.bench.append(merged_card)
                    print(f"{self.name} buys and places {merged_card} on the bench. Elixir left: {self.elixir}")
                else:
                    self.elixir += card.cost
                    self.deck_manager.return_cards([merged_card])
                    print(f"{self.name} cannot place {merged_card}, no space. Refunded elixir.")
                    return False
                return True
        return False

    def place_on_grid_random(self, card):
        positions = [(r, c) for r in range(4, 8) for c in range(BOARD_COLS) if self.grid[r][c] is None]
        if not positions:
            return None
        row, col = random.choice(positions)
        self.grid[row][col] = card
        return (row, col)
    
    def remove_card_from_grid(self, card):
        for r in range(BOARD_ROWS):
            for c in range(BOARD_COLS):
                if self.grid[r][c] == card:
                    self.grid[r][c] = None

    def try_merge(self, new_card):
        zones = [('field', self.field), ('bench', self.bench)]
        for zone_name, zone in zones:
            for i, card in enumerate(zone):
                if card.name == new_card.name and card.star == new_card.star:
                    removed_card = zone.pop(i)
                    self.remove_card_from_grid(removed_card)
                    refund = 1
                    upgraded = Card(new_card.name, new_card.cost, new_card.star + 1)
                    self.elixir += refund
                    print(f"⚠️  MERGE: {new_card.name} {new_card.star}✨ + {removed_card.star}✨ → {upgraded.star}✨! +{refund}💧")
                    return self.try_merge(upgraded) or upgraded
        return new_card

    def give_starting_unit(self):
        two_elixir_cards = [name for name, cost in CARD_STATS.items() if cost == 2]
        name = random.choice(two_elixir_cards)
        card = Card(name, 2, star=1)
        self.field.append(card)
        self.place_on_grid_random(card)
        print(f"{self.name} starts with {card}")

    def display_zone(self, round_number):
        hp_display = f"❤️{self.hp}"
        print(f"{self.name} {hp_display} FIELD ({len(self.field)}/{self.max_field_slots(round_number)}): " +
              ", ".join([f"{card.name} {card.star}✨" for card in self.field]))
        print(f"{self.name} BENCH ({len(self.bench)}/5): " +
              ", ".join([f"{card.name} {card.star}✨" for card in self.bench]))

    def take_damage(self, damage):
        self.hp -= damage
        print(f"💀 {self.name} takes {damage} damage! HP: {self.hp}")
        if self.hp <= 0:
            print(f"💀 {self.name} has been eliminated!")

    def act(self, round_number):
        return self.bot_logic(self, round_number)

def combine_grids(p1, p2):
    combined_grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            card = p1.grid[r][c]
            if card:
                combined_grid[r][c] = (card, p1)
    for r in range(4, 8):
        for c in range(BOARD_COLS):
            card = p2.grid[r][c]
            if card:
                new_row = 7 - r
                new_col = BOARD_COLS - 1 - c
                combined_grid[new_row][new_col] = (card, p2)
    return combined_grid

def get_player_color(player_name):
    """Return ANSI color code based on player name."""
    colors = {
        "Greedy": "\033[94m",    # Blue
        "Efficient": "\033[92m", # Green
        "ComboSeeker": "\033[93m", # Yellow
        "Random": "\033[91m",    # Red
    }
    return colors.get(player_name, "\033[0m")  # Default no color

def print_combined_grid(grid):
    print("Combined Combat Grid (5 cols x 8 rows, hex style):")
    for r in range(BOARD_ROWS):
        # Indent every odd row for hex effect
        row_str = "  " if r % 2 == 0 else ""
        for c in range(BOARD_COLS):
            cell = grid[r][c]
            if cell:
                card, owner = cell
                symbol = card_to_symbol(card).ljust(3)
                color_code = get_player_color(owner.name)
                row_str += f"{color_code}{symbol}\033[0m "
            else:
                row_str += "--- "
        print(row_str)
    print()

EVEN_ROW_OFFSETS = [  # even row (0, 2, 4, ...)
    (-1, 0), (-1, +1), (0, +1),
    (+1, +1), (+1, 0), (0, -1)
]

ODD_ROW_OFFSETS = [  # odd row (1, 3, 5, ...)
    (-1, -1), (-1, 0), (0, +1),
    (+1, 0), (+1, -1), (0, -1)
]

def hex_neighbors(row, col):
    if row % 2 == 0:
        directions = EVEN_ROW_OFFSETS
    else:
        directions = ODD_ROW_OFFSETS

    results = []
    for dr, dc in directions:
        r, c = row + dr, col + dc
        if 0 <= r < BOARD_ROWS and 0 <= c < BOARD_COLS:
            results.append((r, c))
    return results

def hex_distance(a, b):
    """Compute hex distance based on movement steps (BFS distance)."""
    if a == b:
        return 0
    
    from collections import deque
    queue = deque([(a, 0)])
    visited = {a}
    
    while queue:
        (r, c), dist = queue.popleft()
        
        for nr, nc in hex_neighbors(r, c):
            if (nr, nc) == b:
                return dist + 1
            
            if (nr, nc) not in visited and 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                visited.add((nr, nc))
                queue.append(((nr, nc), dist + 1))
    
    return float('inf')  # No path found

def find_path_bfs(start, goal, occupied_positions, exclude_goal=False):
    """Find shortest path using BFS, avoiding occupied positions."""
    if start == goal:
        return [start]
    
    queue = deque([(start, [start])])
    visited = {start}
    
    while queue:
        (r, c), path = queue.popleft()
        
        for nr, nc in hex_neighbors(r, c):
            if (nr, nc) in visited:
                continue
            if 0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS:
                # Allow moving to goal even if occupied (for attacking)
                if (nr, nc) == goal:
                    return path + [(nr, nc)]
                # Skip occupied positions unless it's the goal
                elif (nr, nc) not in occupied_positions:
                    visited.add((nr, nc))
                    queue.append(((nr, nc), path + [(nr, nc)]))
    
    return None  # No path found

class CombatUnit:
    def __init__(self, row, col, card, owner):
        self.row = row
        self.col = col
        self.card = card
        self.owner = owner
        self.current_target = None
        self.is_attacking = False
        self.alive = True
        self.current_hp = card.health  # Current health
        self.max_hp = card.health      # Maximum health
        self.last_attack_time = 0      # Time since last attack
        self.move_cooldown = 0         # Movement cooldown based on speed
        self.status_effects = {}       # Status effects like stun, poison, etc.
        self.ability_cooldown = 0      # Cooldown for special abilities
    
    def get_position(self):
        return (self.row, self.col)
    
    def move_to(self, new_row, new_col):
        self.row = new_row
        self.col = new_col
    
    def get_range(self):
        return getattr(self.card, 'range', 1)
    
    def get_damage(self):
        return getattr(self.card, 'damage', 50)
    
    def get_attack_speed(self):
        return getattr(self.card, 'attack_speed', 1.0)
    
    def get_move_speed(self):
        return getattr(self.card, 'speed', 1.0)
    
    def can_attack(self, current_time):
        attack_interval = self.get_attack_speed()  # This is actually seconds per attack!
        return current_time - self.last_attack_time >= attack_interval
    
    def can_move(self, current_time):
        """Check if unit can move based on movement speed."""
        move_interval = 1.0 / self.get_move_speed()  # Time between moves
        return current_time - self.move_cooldown >= move_interval
    
    def attack(self, target, current_time, all_units, combined_grid):
        """Attack a target unit using unit-specific attack pattern."""
        if not self.can_attack(current_time) or not target.alive:
            return False
        
        # Use unit-specific attack based on card name
        attack_result = self.execute_unique_attack(target, all_units, combined_grid, current_time)
        
        if attack_result:
            self.last_attack_time = current_time
        
        return attack_result
    
    def execute_unique_attack(self, primary_target, all_units, combined_grid, current_time):
        """Execute unit-specific attack patterns."""
        unit_name = self.card.name.lower()
        base_damage = self.get_damage()
        
        #if unit_name == "knight":
        #    return self._knight_attack(primary_target, base_damage)
        #elif unit_name == "archer":
        #    return self._archer_attack(primary_target, base_damage)
        #elif unit_name == "goblin":
        #    return self._goblin_attack(primary_target, base_damage)
        #elif unit_name == "spear-goblin":
        #    return self._spear_goblin_attack(primary_target, all_units, base_damage)
        #elif unit_name == "bomber":
        #    return self._bomber_attack(primary_target, all_units, combined_grid, base_damage)
        #elif unit_name == "barbarian":
        #    return self._barbarian_attack(primary_target, base_damage)
        #elif unit_name == "valkyrie":
        #    return self._valkyrie_attack(primary_target, all_units, base_damage)
        #elif unit_name == "pekka":
        #    return self._pekka_attack(primary_target, base_damage)
        #elif unit_name == "prince":
        #    return self._prince_attack(primary_target, all_units, base_damage)
        #elif unit_name == "giant-skeleton":
        #    return self._giant_skeleton_attack(primary_target, all_units, base_damage)
        #elif unit_name == "dart-goblin":
        #    return self._dart_goblin_attack(primary_target, all_units, base_damage)
        #elif unit_name == "executioner":
        #    return self._executioner_attack(primary_target, all_units, base_damage)
        #elif unit_name == "princess":
        #    return self._princess_attack(primary_target, all_units, combined_grid, base_damage)
        #elif unit_name == "mega-knight":
        #    return self._mega_knight_attack(primary_target, all_units, base_damage)
        #elif unit_name == "royal-ghost":
        #    return self._royal_ghost_attack(primary_target, base_damage)
        #elif unit_name == "bandit":
        #    return self._bandit_attack(primary_target, all_units, base_damage)
        #elif unit_name == "goblin-machine":
        #    return self._goblin_machine_attack(primary_target, all_units, base_damage)
        #elif unit_name == "skeleton-king":
        #    return self._skeleton_king_attack(primary_target, base_damage)
        #elif unit_name == "golden-knight":
        #    return self._golden_knight_attack(primary_target, base_damage)
        #elif unit_name == "archer-queen":
        #    return self._archer_queen_attack(primary_target, all_units, base_damage)
        #else:
            # Default attack
        return self._default_attack(primary_target, base_damage)
    
    # === UNIQUE ATTACK IMPLEMENTATIONS ===
    
    def _knight_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _archer_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _goblin_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _spear_goblin_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _bomber_attack(self, target, all_units, combined_grid, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _barbarian_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _valkyrie_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _pekka_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _prince_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _giant_skeleton_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _dart_goblin_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _executioner_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _princess_attack(self, target, all_units, combined_grid, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _mega_knight_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _royal_ghost_attack(self, target, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _bandit_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _goblin_machine_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _skeleton_king_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _golden_knight_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _archer_queen_attack(self, target, all_units, base_damage):
        damage = base_damage
        print(f"⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def _default_attack(self, target, base_damage):
        """Default attack for unknown units."""
        damage = base_damage
        if random.random() < 0.15:  # 15% crit chance
            damage = int(damage * 1.5)
            print(f"💥 CRITICAL! {self.card.name} deals {damage} damage to {target.card.name}")
        else:
            print(f"⚔️ {self.card.name} attacks {target.card.name} for {damage} damage")
        target.take_damage(damage)
        return True
    
    def take_damage(self, damage):
        """Take damage and check if unit dies."""        
        self.current_hp -= damage
        if self.current_hp <= 0:
            self.current_hp = 0
            self.alive = False
            print(f"💀 {self.card.name} has been defeated!")
    
    def update_status_effects(self, time_step):
        """Update status effects each time step."""
        effects_to_remove = []
        
        for effect, remaining_time in self.status_effects.items():
            if effect == 'poisoned':
                # Take poison damage
                poison_damage = 10  # Fixed poison damage per tick
                self.current_hp -= poison_damage
                print(f"☠️ {self.card.name} takes {poison_damage} poison damage!")
                if self.current_hp <= 0:
                    self.current_hp = 0
                    self.alive = False
                    print(f"💀 {self.card.name} dies from poison!")
            
            # Decrease effect timer
            new_time = remaining_time - time_step
            if new_time <= 0:
                effects_to_remove.append(effect)
            else:
                self.status_effects[effect] = new_time
        
        # Remove expired effects
        for effect in effects_to_remove:
            del self.status_effects[effect]
            if effect == 'stunned':
                print(f"😵 {self.card.name} recovers from stun!")
            elif effect == 'invisible':
                print(f"👁️ {self.card.name} becomes visible again!")
        
        # Update ability cooldowns
        if self.ability_cooldown > 0:
            self.ability_cooldown = max(0, self.ability_cooldown - time_step)
    
    def can_act(self):
        """Check if unit can move or attack (not stunned)."""
        return not self.status_effects.get('stunned', 0) > 0
    
    def find_closest_enemy(self, all_units):
        """Find the closest living enemy unit."""
        min_dist = float('inf')
        closest_enemy = None
        
        for unit in all_units:
            if unit.alive and unit.owner != self.owner:
                dist = hex_distance(self.get_position(), unit.get_position())
                if dist < min_dist:
                    min_dist = dist
                    closest_enemy = unit
        
        return closest_enemy, min_dist
    
    def is_in_range_of(self, target):
        """Check if target is within attack range based on movement steps."""
        if not target or not target.alive:
            return False
        
        start_pos = self.get_position()
        target_pos = target.get_position()
        attack_range = self.get_range()
        
        if start_pos == target_pos:
            return True
        
        # BFS to find minimum movement distance
        queue = deque([(start_pos, 0)])
        visited = {start_pos}
        
        while queue:
            (r, c), moves = queue.popleft()
            
            if moves >= attack_range:
                continue
            
            for nr, nc in hex_neighbors(r, c):
                if (nr, nc) == target_pos:
                    return True
                
                if ((nr, nc) not in visited and 
                    0 <= nr < BOARD_ROWS and 0 <= nc < BOARD_COLS):
                    visited.add((nr, nc))
                    queue.append(((nr, nc), moves + 1))
        
        return False
    
    def should_retarget(self, all_units):
        """Check if we should switch to a closer target that's now in range."""
        if not self.current_target or not self.current_target.alive:
            return True
        
        if self.is_attacking and self.is_in_range_of(self.current_target):
            return False
        
        if not self.is_in_range_of(self.current_target):
            return True
        
        # Check if there's a closer enemy now in range
        for unit in all_units:
            if (unit.alive and unit.owner != self.owner and 
                unit != self.current_target and self.is_in_range_of(unit)):
                current_dist = hex_distance(self.get_position(), self.current_target.get_position())
                new_dist = hex_distance(self.get_position(), unit.get_position())
                if new_dist < current_dist:
                    return True
        
        return False

def simulate_and_visualize_combat_live(players):
    """Simulate combat and visualize it live in a Pygame window."""
    if not players or len(players) < 2 or not players[0].opponent:
        return [], None, None

    p1, p2 = players[0], players[0].opponent
    combined = combine_grids(p1, p2)

    # Create combat units
    units = []
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            cell = combined[r][c]
            if cell:
                card, owner = cell
                units.append(CombatUnit(r, c, card, owner))

    if not units:
        return [], None, None

    # Setup Pygame window
    pygame.init()
    screen = pygame.display.set_mode((1200, 1000))
    pygame.display.set_caption("MergeTacticsBot Combat Visualization (Live)")
    clock = pygame.time.Clock()

    max_rounds = 50
    current_time = 0.0
    time_step = 0.2

    winner = None
    remaining_units = None

    round_count = 0
    while True:
        round_count += 1
        current_time += time_step
        moved_this_round = False
        attacked_this_round = False
        arrows = {}

        # Get current occupied positions
        def get_occupied_positions(excluding_unit=None):
            occupied = set()
            for unit in units:
                if unit.alive and unit != excluding_unit:
                    occupied.add(unit.get_position())
            return occupied

        living_units = [u for u in units if u.alive]
        if not living_units:
            break

        p1_alive = any(u.alive and u.owner == p1 for u in units)
        p2_alive = any(u.alive and u.owner == p2 for u in units)
        if not p1_alive or not p2_alive:
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return [], None, None
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                return [], None, None

        for unit in living_units:
            if not unit.alive:
                continue
            unit.update_status_effects(time_step)
            if not unit.alive:
                continue
            if not unit.can_act():
                continue
            if unit.should_retarget(living_units):
                closest_enemy, min_dist = unit.find_closest_enemy(living_units)
                unit.current_target = closest_enemy
                unit.is_attacking = False
                if not unit.current_target:
                    continue
            if not unit.current_target or not unit.current_target.alive:
                continue
            if unit.is_in_range_of(unit.current_target):
                unit.is_attacking = True
                arrows[unit.get_position()] = unit.current_target.get_position()
                if unit.can_attack(current_time):
                    try:
                        if unit.attack(unit.current_target, current_time, living_units, combined):
                            attacked_this_round = True
                    except Exception as e:
                        print(f"⚠️ Attack error: {e}")
                        if unit.current_target.alive:
                            unit.current_target.take_damage(unit.get_damage())
                            attacked_this_round = True
                continue
            else:
                unit.is_attacking = False
            if not unit.can_move(current_time):
                continue
            target_pos = unit.current_target.get_position()
            current_pos = unit.get_position()
            occupied = get_occupied_positions(excluding_unit=unit)
            best_move = None
            best_dist = float('inf')
            for move_pos in hex_neighbors(current_pos[0], current_pos[1]):
                if move_pos not in occupied:
                    dist_to_target = hex_distance(move_pos, target_pos)
                    if dist_to_target < best_dist:
                        best_dist = dist_to_target
                        best_move = move_pos
            if best_move:
                next_r, next_c = best_move
                combined[unit.row][unit.col] = None
                combined[next_r][next_c] = (unit.card, unit.owner)
                unit.move_to(next_r, next_c)
                unit.move_cooldown = current_time
                moved_this_round = True
            if unit.current_target and unit.current_target.alive:
                arrows[unit.get_position()] = unit.current_target.get_position()

        # Handle death explosions (Giant Skeleton) - simplified
        explosion_units = [u for u in units if not u.alive and u.status_effects.get('death_explosion', False)]
        for unit in explosion_units:
            explosion_pos = unit.get_position()
            explosion_damage = unit.get_damage()
            print(f"💀💥 Giant Skeleton explodes for {explosion_damage} area damage!")
            for other_unit in units:
                if (other_unit.alive and other_unit != unit 
                    and hex_distance(explosion_pos, other_unit.get_position()) <= 2):
                    print(f"💥 Explosion hits {other_unit.card.name} for {explosion_damage} damage!")
                    other_unit.take_damage(explosion_damage)
            unit.status_effects['death_explosion'] = False

        for unit in units:
            if not unit.alive:
                combined[unit.row][unit.col] = None

        # Draw the current state live
        screen.fill((30, 30, 30))
        draw_grid(screen, combined, units=units, arrows=arrows)
        pygame.display.flip()
        clock.tick(1)  # Adjust for speed (frames per second)

        # Early victory check
        p1_alive = any(u.alive and u.owner == p1 for u in units)
        p2_alive = any(u.alive and u.owner == p2 for u in units)
        if not p1_alive and not p2_alive:
            print("🤝 DRAW: Both armies destroyed!")
            winner = None
            remaining_units = None
            break
        elif not p1_alive:
            remaining = len([u for u in units if u.alive and u.owner == p2])
            print(f"🏆 {p2.name} WINS with {remaining} units remaining!")
            winner = p2
            remaining_units = remaining
            break
        elif not p2_alive:
            remaining = len([u for u in units if u.alive and u.owner == p1])
            print(f"🏆 {p1.name} WINS with {remaining} units remaining!")
            winner = p1
            remaining_units = remaining
            break

    pygame.quit()
    return [], winner, remaining_units

# Bot logic functions remain the same
def greedy_bot_logic(player, round_number):
    for card in player.hand:
        if card.cost <= player.elixir:
            return player.buy_card(card.name, round_number)
    return False

def efficient_bot_logic(player, round_number):
    best = None
    for card in player.hand:
        if card.cost <= player.elixir:
            if best is None or card.cost > best.cost:
                best = card
    if best:
        return player.buy_card(best.name, round_number)
    return False

def combo_seeker_bot_logic(player, round_number):
    owned_names = [c.name for c in player.field + player.bench]
    priority = None
    for card in player.hand:
        if card.name in owned_names and card.cost <= player.elixir:
            priority = card
            break
    if not priority:
        for card in player.hand:
            if card.cost <= player.elixir:
                priority = card
                break
    if priority:
        return player.buy_card(priority.name, round_number)
    return False

def random_bot_logic(player, round_number):
    action = random.choice(["buy", "wait", "skip"])
    if action == "wait" or action == "skip":
        return False
    affordable = [card for card in player.hand if card.cost <= player.elixir]
    if affordable:
        card = random.choice(affordable)
        return player.buy_card(card.name, round_number)
    return False

def assign_opponents(players):
    alive_players = [p for p in players if p.hp > 0]
    players_shuffled = alive_players[:]
    random.shuffle(players_shuffled)
    for p in players_shuffled:
        p.opponent = None
    for i in range(0, len(players_shuffled) - 1, 2):
        p1 = players_shuffled[i]
        p2 = players_shuffled[i + 1]
        p1.opponent = p2
        p2.opponent = p1
        print(f"{p1.name} ❤️{p1.hp} will fight {p2.name} ❤️{p2.hp} in combat phase.")
    if len(players_shuffled) % 2 == 1:
        last_player = players_shuffled[-1]
        last_player.opponent = None
        print(f"{last_player.name} ❤️{last_player.hp} has no opponent this round.")

def play_round(players, round_number):
    print(f"\n=== ROUND {round_number} ===")
    alive_players = [p for p in players if p.hp > 0]
    if len(alive_players) <= 1:
        if len(alive_players) == 1:
            print(f"🏆 GAME OVER: {alive_players[0].name} is the last player standing!")
        else:
            print("🏆 GAME OVER: No players remaining!")
        return False
    
    assign_opponents(alive_players)
    for p in alive_players:
        p.elixir += 4
    turn_order = alive_players[:]
    random.shuffle(turn_order)
    passes_in_a_row = 0
    total_players = len(alive_players)
    
    while passes_in_a_row < total_players:
        for player in turn_order:
            if player.hp <= 0:
                continue
            acted = player.act(round_number)
            if acted and player.has_space(round_number):
                passes_in_a_row = 0
                print(f"{player.name} acted and has {player.elixir}💧 left.")
            else:
                print(f"{player.name} passes.")
                passes_in_a_row += 1
            if passes_in_a_row >= total_players:
                break
    
    print(f"\n--- Round {round_number} Combat Phase ---")
    matched_pairs = set()
    
    for p in alive_players:
        opponent = p.opponent
        if opponent and opponent.hp > 0 and (p, opponent) not in matched_pairs and (opponent, p) not in matched_pairs:
            combined = combine_grids(p, opponent)
            p_color = get_player_color(p.name)
            o_color = get_player_color(opponent.name)
            print(f"\nMatchup: {p_color}{p.name} ❤️{p.hp}\033[0m VS {o_color}{opponent.name} ❤️{opponent.hp}\033[0m")
            print_combined_grid(combined)
            matched_pairs.add((p, opponent))
            
            # Run combat simulation
            combat_grids_and_arrows, winner, remaining_units = simulate_and_visualize_combat_live([p, opponent])
            
            # Apply damage to loser
            if winner == p:
                damage = remaining_units + 1
                opponent.take_damage(damage)
            elif winner == opponent:
                damage = remaining_units + 1
                p.take_damage(damage)
            else:  # Draw
                print("🤝 No damage dealt due to draw!")
            
    
    print(f"\n--- Round {round_number} Summary ---")
    for player in alive_players:
        if player.hp > 0:
            player.display_zone(round_number)
    
    return True

if __name__ == '__main__':
    class DeckManager:
        def __init__(self):
            self.card_pool = [Card(name, cost) for name, cost in CARD_STATS.items() for _ in range(4)]
            random.shuffle(self.card_pool)

        def draw_hand(self, n=3):
            hand = []
            used_names = set()
            i = 0
            while len(hand) < n and i < len(self.card_pool):
                card = self.card_pool[i]
                if card.name not in used_names:
                    hand.append(card)
                    used_names.add(card.name)
                    self.card_pool.pop(i)
                else:
                    i += 1
            return hand

        def return_cards(self, cards):
            self.card_pool.extend(cards)
            random.shuffle(self.card_pool)

        def deal_hand(self, n=3):
            return self.draw_hand(n)

    deck = DeckManager()
    players = [
        Player("Greedy", deck, greedy_bot_logic),
        Player("Efficient", deck, efficient_bot_logic),
        Player("ComboSeeker", deck, combo_seeker_bot_logic),
        Player("Random", deck, random_bot_logic)
    ]

    for player in players:
        player.give_starting_unit()

    round_num = 1
    while round_num <= 10:  # Max 10 rounds
        if not play_round(players, round_num):
            break
        round_num += 1
    
    # Final standings
    alive_players = [p for p in players if p.hp > 0]
    alive_players.sort(key=lambda p: p.hp, reverse=True)
    
    print(f"\n🏆 FINAL STANDINGS:")
    for i, player in enumerate(alive_players, 1):
        print(f"{i}. {player.name} - ❤️{player.hp} HP")
    
    dead_players = [p for p in players if p.hp <= 0]
    if dead_players:
        print(f"\n💀 ELIMINATED:")
        for player in dead_players:
            print(f"   {player.name} - ❤️{player.hp} HP")