import random
import copy
from collections import deque
from merge_sim.cards import Card, CARD_STATS, card_to_symbol, BASE_TROOP_STATS
from merge_sim.visualise import draw_grid, hex_to_pixel, PLAYER_COLOURS
import pygame
from collections import deque
import time

BOARD_ROWS = 8
BOARD_COLS = 5
CRIT_CHANCE = 0.15
CRIT_MULTIPLIER = 1.5

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
        # Instead of random, always pick "Prince"
        name = "executioner"
        
        # Assuming Card constructor takes (name, cost, star)
        card = Card(name, 3, star=1)  # Prince costs 2 elixir, star 1
        
        unit = CombatUnit(None, None, card, owner=self)
        self.field.append(unit)
        self.place_on_grid_random(unit)
        print(f"{self.name} starts with {unit.card.name}")

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
    
def get_units_in_radius(center, radius, units):
        cr, cc = center
        return [u for u in units if u.alive and hex_distance((u.row, u.col), (cr, cc)) <= radius]

def combine_grids(p1, p2):
    combined_grid = [[None for _ in range(BOARD_COLS)] for _ in range(BOARD_ROWS)]

    # Player 1 units: direct copy
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            unit = p1.grid[r][c]
            if unit:
                combined_grid[r][c] = unit
                unit.row = r
                unit.col = c

    # Player 2 units: flipped copy
    for r in range(4, 8):
        for c in range(BOARD_COLS):
            unit = p2.grid[r][c]
            if unit:
                new_row = 7 - r
                new_col = BOARD_COLS - 1 - c
                combined_grid[new_row][new_col] = unit
                unit.row = new_row
                unit.col = new_col

    return combined_grid

def get_player_colour(player_name):
    """Return ANSI colour code based on player name."""
    colours = {
        "Greedy": "\033[94m",    # Blue
        "Efficient": "\033[92m", # Green
        "ComboSeeker": "\033[93m", # Yellow
        "Random": "\033[91m",    # Red
    }
    return colours.get(player_name, "\033[0m")  # Default no colour

def print_combined_grid(combined_grid):
    for r in range(BOARD_ROWS):
        row_str = ""
        for c in range(BOARD_COLS):
            cell = combined_grid[r][c]
            if cell is None:
                row_str += "[    ] "
            else:
                # cell is a CombatUnit
                unit = cell
                # Access card info inside CombatUnit, e.g. unit.card.name or unit.card shorthand
                name = unit.card.name if hasattr(unit, "card") else "UNK"
                star = getattr(unit.card, "star", "?")
                team = getattr(unit.owner, "name", "Unknown") if hasattr(unit, "owner") else "?"
                row_str += f"[{name[:3]}{star}T{team[0]}] "
        print(row_str)

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
        self.last_update_time = 0  # Last time this unit was updated
    
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
        if unit_name == "bomber":
            return self._bomber_attack(primary_target, all_units, combined_grid, base_damage)
        #elif unit_name == "barbarian":
        #    return self._barbarian_attack(primary_target, base_damage)
        elif unit_name == "valkyrie":
            return self._valkyrie_attack(primary_target, all_units, combined_grid, base_damage)
        #elif unit_name == "pekka":
        #    return self._pekka_attack(primary_target, base_damage)
        #elif unit_name == "prince":
        #    return self._prince_attack(primary_target, all_units, base_damage)
        #elif unit_name == "giant-skeleton":
        #    return self._giant_skeleton_attack(primary_target, all_units, base_damage)
        #elif unit_name == "dart-goblin":
        #    return self._dart_goblin_attack(primary_target, all_units, base_damage)
        elif unit_name == "executioner":
            return self._executioner_attack(primary_target, all_units, combined_grid, base_damage)
        elif unit_name == "princess":
            return self._princess_attack(primary_target, all_units, combined_grid, base_damage)
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
        else:
            #Default attack
            return self._default_attack(primary_target, base_damage)
    
    # === UNIQUE ATTACK IMPLEMENTATIONS ===
    
    def _bomber_attack(self, target, all_units, combined_grid, base_damage):
        is_crit = random.random() < CRIT_CHANCE

        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)

        print(f"💣 {self.card.name} strikes {target.card.name} for {damage} damage"
            + (" (CRIT!)" if is_crit else ""))
        target.take_damage(damage)

        # Splash damage to adjacent enemies only
        splash_targets = []
        for r, c in hex_neighbors(target.row, target.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                if unit and unit.owner != self.owner:
                    splash_targets.append(unit)

        for unit in splash_targets:
            splash_damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)
            print(f"💥 Splash hits {unit.card.name} for {splash_damage} damage"
                + (" (CRIT!)" if is_crit else ""))
            unit.take_damage(splash_damage)

        return True

    def _valkyrie_attack(self, target, all_units, combined_grid, base_damage):
        # Roll crit once per attack
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)

        crit_text = "💥 CRIT! " if is_crit else ""

        # Damage the initial target first
        print(f"{crit_text}{self.card.name} strikes initial target {target.card.name} for {damage} damage")
        target.take_damage(damage)

        # Damage splash targets around self (excluding initial target)
        for r, c in hex_neighbors(self.row, self.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                # Check unit exists, is an enemy, and is not the initial target
                if unit and unit.owner != self.owner and unit != target:
                    print(f"{crit_text}{self.card.name} hits splash target {unit.card.name} for {damage} damage")
                    unit.take_damage(damage)

        return True

    def prince_combat_start_ability(self, all_units, combined_grid):
        # Find nearest enemy unit
        enemies = [u for u in all_units if u.alive and u.owner != self.owner]
        if not enemies:
            return False

        closest_enemy = None
        min_dist = float('inf')
        for enemy in enemies:
            dist = hex_distance(self.get_position(), enemy.get_position())
            if dist < min_dist:
                min_dist = dist
                closest_enemy = enemy

        if not closest_enemy:
            return False

        star_level = getattr(self.card, "star", 1)

        # Positions and direction
        pr, pc = self.get_position()
        er, ec = closest_enemy.get_position()
        dr = er - pr
        dc = ec - pc

        # Simple step direction (approximate for your grid)
        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        step_c = 0 if dc == 0 else (1 if dc > 0 else -1)

        rows = len(combined_grid)
        cols = len(combined_grid[0])

        def in_bounds(r, c):
            return 0 <= r < rows and 0 <= c < cols

        prince_dest = (er, ec)
        enemy_old = (closest_enemy.row, closest_enemy.col)
        prince_old = (self.row, self.col)

        print("Prince star level:", getattr(self.card, "star", "NOT FOUND"), type(self.card))

        # Build list of preferred fling targets along the throw direction (farthest first)
        preferred = []
        for d in range(star_level, 0, -1):
            rr = er + step_r * d
            cc = ec + step_c * d
            if in_bounds(rr, cc):
                preferred.append((rr, cc))

        # Temporarily clear old positions so they are considered free for the search (but exclude prince_dest)
        saved_pr_cell = combined_grid[prince_old[0]][prince_old[1]] if in_bounds(*prince_old) else None
        saved_en_cell = combined_grid[enemy_old[0]][enemy_old[1]] if in_bounds(*enemy_old) else None

        # Clear them for the search
        if in_bounds(*prince_old):
            combined_grid[prince_old[0]][prince_old[1]] = None
        if in_bounds(*enemy_old):
            combined_grid[enemy_old[0]][enemy_old[1]] = None

        # Helper to check a free candidate (must not be prince_dest)
        def is_free_candidate(pos):
            r, c = pos
            return in_bounds(r, c) and pos != prince_dest and combined_grid[r][c] is None

        fling_pos = None

        # 1) Try preferred positions first (farthest preferred)
        for pos in preferred:
            if is_free_candidate(pos):
                fling_pos = pos
                break

        # 2) If none, BFS outward from enemy original to find nearest free tile excluding prince_dest
        if fling_pos is None:
            visited = set()
            q = deque()
            # start from neighbors of (er,ec) so we don't pick (er,ec) itself
            for nbr in hex_neighbors(er, ec):
                if in_bounds(*nbr):
                    q.append(nbr)
                    visited.add(nbr)

            while q and fling_pos is None:
                r, c = q.popleft()
                if (r, c) in visited:
                    pass
                # Check candidate
                if is_free_candidate((r, c)):
                    fling_pos = (r, c)
                    break
                # enqueue neighbors
                for nbr in hex_neighbors(r, c):
                    if in_bounds(*nbr) and nbr not in visited and nbr != prince_dest:
                        visited.add(nbr)
                        q.append(nbr)

        # If still none found, revert grid and abort dash (safer than overlapping)
        if fling_pos is None:
            # restore saved cells
            if in_bounds(*prince_old):
                combined_grid[prince_old[0]][prince_old[1]] = saved_pr_cell
            if in_bounds(*enemy_old):
                combined_grid[enemy_old[0]][enemy_old[1]] = saved_en_cell
            print(f"⚠️ Prince dash cancelled: no valid fling destination found for {closest_enemy.card.name}.")
            return False

        fling_r, fling_c = fling_pos

        # Now perform the atomic moves: place prince into enemy original, place enemy into fling_pos
        # Clear old positions (they were already cleared for the search)
        # Place prince
        combined_grid[er][ec] = self
        self.move_to(er, ec)

        # Place enemy
        combined_grid[fling_r][fling_c] = closest_enemy
        closest_enemy.move_to(fling_r, fling_c)

        # Apply stun
        closest_enemy.status_effects['stunned'] = 2.0

        # Debug prints
        print(f"🏇 {self.card.name} dashes from {prince_old} to {prince_dest}")
        print(f"👊 {closest_enemy.card.name} flung from {enemy_old} to {(fling_r, fling_c)} and stunned for 2s")

        return True

    def _executioner_attack(self, target, all_units, combined_grid, base_damage):
        """Executioner throws axe in straight line, pierces through target for star_level tiles, then returns."""
        damage = base_damage
        star_level = getattr(self.card, 'star', 1)
        
        print(f"🪓 {self.card.name} throws axe at {target.card.name}!")
        
        # Determine if this attack crits
        crit_chance = CRIT_CHANCE
        crit_multiplier = CRIT_MULTIPLIER
        is_crit = random.random() < crit_chance
        
        if is_crit:
            damage = int(damage * crit_multiplier)
        
        # Get positions
        exe_pos = self.get_position()
        target_pos = target.get_position()
        
        # Calculate direction vector
        dx = target_pos[1] - exe_pos[1]  # col difference
        dy = target_pos[0] - exe_pos[0]  # row difference
        
        # Normalize direction to get unit vector
        distance = max(abs(dx), abs(dy), 1)  # Prevent division by zero
        step_x = dx / distance if distance > 0 else 0
        step_y = dy / distance if distance > 0 else 0
        
        # Trace the axe path - forward journey to target
        forward_path = []
        current_row, current_col = exe_pos
        
        # Move towards target until we reach it
        for step in range(1, 10):  # Max 10 steps to prevent infinite loops
            next_row = exe_pos[0] + int(step_y * step)
            next_col = exe_pos[1] + int(step_x * step)
            
            if not (0 <= next_row < BOARD_ROWS and 0 <= next_col < BOARD_COLS):
                break
                
            forward_path.append((next_row, next_col))
            
            if (next_row, next_col) == target_pos:
                break
        
        # Continue past target for star_level additional tiles
        pierce_path = []
        if forward_path:
            last_pos = forward_path[-1]
            for extra_step in range(1, star_level + 1):
                pierce_row = last_pos[0] + int(step_y * extra_step)
                pierce_col = last_pos[1] + int(step_x * extra_step)
                
                if not (0 <= pierce_row < BOARD_ROWS and 0 <= pierce_col < BOARD_COLS):
                    break
                    
                pierce_path.append((pierce_row, pierce_col))
        
        complete_forward = forward_path + pierce_path
        return_path = list(reversed(complete_forward))
        
        units_hit = {}
        hit_count = {}
        
        for unit in all_units:
            if unit.alive and unit.owner != self.owner:
                unit_pos = unit.get_position()
                units_hit[unit_pos] = units_hit.get(unit_pos, []) + [unit]
                hit_count[unit] = 0
        
        print(f"🪓 Axe travels forward: {' → '.join([f'({r},{c})' for r, c in complete_forward])}")
        for pos in complete_forward:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        print(f"💥 Axe hits {unit.card.name} on forward pass for {damage} damage!")
                        unit.take_damage(damage)
                        hit_count[unit] += 1
        
        print(f"🪓 Axe returns: {' → '.join([f'({r},{c})' for r, c in return_path])}")
        for pos in return_path:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        print(f"💥 Axe hits {unit.card.name} on return pass for {damage} damage!")
                        unit.take_damage(damage)
                        hit_count[unit] += 1
        
        total_hits = sum(hit_count.values())
        unique_targets = len([u for u in hit_count.keys() if hit_count[u] > 0])
        print(f"🪓 Executioner's axe dealt {total_hits} total hits to {unique_targets} enemies!")
        
        return True

    def _princess_attack(self, target, all_units, combined_grid, base_damage):
        # Roll crit once for entire attack
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)
        crit_text = "💥 CRIT! " if is_crit else ""

        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage)

        # Splash damage to enemies adjacent to the target
        for r, c in hex_neighbors(target.row, target.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                if unit and unit.owner != self.owner:
                    print(f"{crit_text}💥 {self.card.name} splash hits {unit.card.name} for {damage} damage")
                    unit.take_damage(damage)

        return True

    def _mega_knight_attack(self, target, all_units, base_damage):
        current_time = time.time()
        damage = base_damage

        if not hasattr(self, 'last_jump_time'):
            self.last_jump_time = 0

        # Check if currently jumping
        if getattr(self, 'is_jumping', False):
            # Check if 1 second elapsed since jump started
            if current_time - self.jump_start_time >= 1:
                # Finish jump: move to target, stun enemies
                new_r, new_c = self.jump_target_pos
                old_pos = (self.row, self.col)
                self.move_to(new_r, new_c)
                print(f"🚀 {self.card.name} finishes jump from {old_pos} to {self.jump_target_pos}!")

                stunned_units = get_units_in_radius(self.jump_target_pos, 2, all_units)
                for u in stunned_units:
                    if u.owner != self.owner:
                        u.status_effects['stunned'] = 2.0
                        print(f"💫 {u.card.name} is stunned for 2 seconds by {self.card.name}!")

                self.is_jumping = False
                self.last_jump_time = current_time
                return True
            else:
                # Still mid-jump: skip normal attack, maybe print or animate jump progress
                return False

        # Not currently jumping, check if time to start jump
        if current_time - self.last_jump_time >= 6:
            # Find jump target with max neighbors within range 3 (same as before)
            max_neighbors = -1
            best_hex = None

            for r in range(max(0, self.row - 3), min(BOARD_ROWS, self.row + 4)):
                for c in range(max(0, self.col - 3), min(BOARD_COLS, self.col + 4)):
                    if hex_distance((self.row, self.col), (r, c)) <= 3:
                        neighbors = 0
                        for u in all_units:
                            if u.alive and (u.row, u.col) != (r, c):
                                if hex_distance((u.row, u.col), (r, c)) == 1:
                                    neighbors += 1
                        if neighbors > max_neighbors:
                            max_neighbors = neighbors
                            best_hex = (r, c)

            if best_hex:
                # Start jump animation/state
                self.is_jumping = True
                self.jump_start_time = current_time
                self.jump_target_pos = best_hex
                print(f"🚀 {self.card.name} starts jumping towards {best_hex}!")

                # Skip normal attack this turn while jumping
                return False

        # Normal melee attack if no jump
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
        effects_to_remove = []
        
        for effect, remaining_time in self.status_effects.items():
            # Decrease timer for all effects
            new_time = remaining_time - time_step
            
            if new_time <= 0:
                effects_to_remove.append(effect)
            else:
                self.status_effects[effect] = new_time

        # Remove expired effects and print messages
        for effect in effects_to_remove:
            del self.status_effects[effect]
            if effect == 'stunned':
                print(f"😵 {self.card.name} recovers from stun!")

    def can_act(self):
        if 'stunned' in self.status_effects:
            return False
        # other conditions...
        return True

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

class Projectile:
    def __init__(self, start_pos, end_pos, colour, speed=300.0):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.speed = speed  # pixels per second
        self.progress = 0.0  # 0.0 to 1.0
        self.colour = colour  # Store colour here

    def update(self, dt):
        dist = ((self.end_pos[0] - self.start_pos[0])**2 + (self.end_pos[1] - self.start_pos[1])**2)**0.5
        if dist == 0:
            self.progress = 1.0
            return
        self.progress += (self.speed * dt) / dist
        if self.progress > 1.0:
            self.progress = 1.0

    def get_position(self):
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * self.progress
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * self.progress
        return (x, y)

    def is_finished(self):
        return self.progress >= 1.0

def simulate_and_visualize_combat_live(players):
    # Early exit if no players or no opponent
    if not players or len(players) < 2 or not players[0].opponent:
        return [], None, None

    p1, p2 = players[0], players[0].opponent
    combined = combine_grids(p1, p2)

    units = []
    seen_units = set()
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            unit = combined[r][c]
            if unit and unit not in seen_units:
                units.append(unit)
                seen_units.add(unit)

    # Debug consistency check here
    print("DEBUG: Checking unit positions in combined grid:")
    for unit in units:
        r, c = unit.row, unit.col
        if combined[r][c] != unit:
            print(f"⚠️ Position mismatch: unit {unit.card.name} at ({r},{c}) but combined_grid[{r}][{c}] = {combined[r][c]}")

    if not units:
        return [], None, None

    pygame.init()
    screen = pygame.display.set_mode((1200, 1000))
    pygame.display.set_caption("MergeTacticsBot Combat Visualization (Live)")
    clock = pygame.time.Clock()
    pygame.font.init()
    font = pygame.font.SysFont('Arial', 30)

    FPS = 60
    winner = None
    remaining_units = None
    round_count = 0
    start_ticks = pygame.time.get_ticks()

    projectiles = []  # List to hold active projectiles

    # after units initialized and combined grid ready
    for unit in units:
        if unit.card.name == "prince":
            unit.prince_combat_start_ability(units, combined)

    # Debug consistency check here
    print("DEBUG: Checking unit positions in combined grid:")
    for unit in units:
        r, c = unit.row, unit.col
        if combined[r][c] != unit:
            print(f"⚠️ Position mismatch: unit {unit.card.name} at ({r},{c}) but combined_grid[{r}][{c}] = {combined[r][c]}")

    while True:
        round_count += 1
        current_time = (pygame.time.get_ticks() - start_ticks) / 1000.0

        # Calculate delta time for smooth projectile movement
        dt = clock.get_time() / 1000.0

        moved_this_round = False
        attacked_this_round = False

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

            time_step = current_time - getattr(unit, 'last_update_time', current_time)
            unit.update_status_effects(time_step)
            unit.last_update_time = current_time

            if not unit.alive:
                continue

            if not unit.can_act():
                continue

            if unit.should_retarget(living_units):
                closest_enemy, _ = unit.find_closest_enemy(living_units)
                unit.current_target = closest_enemy
                unit.is_attacking = False
                if not unit.current_target:
                    continue

            if not unit.current_target or not unit.current_target.alive:
                continue

            if unit.is_in_range_of(unit.current_target):
                unit.is_attacking = True

                if unit.can_attack(current_time):
                    try:
                        if unit.attack(unit.current_target, current_time, living_units, combined):
                            attacked_this_round = True

                            # Spawn a projectile from attacker to target
                            attacker_pos = hex_to_pixel(*unit.get_position())
                            target_pos = hex_to_pixel(*unit.current_target.get_position())
                            colour = PLAYER_COLOURS.get(unit.owner.name, (255, 255, 255))
                            projectiles.append(Projectile(attacker_pos, target_pos, colour))

                    except Exception as e:
                        print(f"⚠️ Attack error: {e}")
                        if unit.current_target.alive:
                            damage = unit.get_damage()
                            unit.current_target.take_damage(damage)
                            attacked_this_round = True
                continue  # After attacking, do not move
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
                combined[next_r][next_c] = unit
                unit.move_to(next_r, next_c)
                unit.move_cooldown = current_time
                moved_this_round = True

        # Clear dead units from combined grid
        for unit in units:
            if not unit.alive and unit.row is not None and unit.col is not None:
                combined[unit.row][unit.col] = None

        # Update and remove finished projectiles
        for projectile in projectiles[:]:
            projectile.update(dt)
            if projectile.is_finished():
                projectiles.remove(projectile)

        screen.fill((30, 30, 30))
        draw_grid(screen, combined, units=units)

        # Draw projectiles as small circles traveling between attacker and target
        for projectile in projectiles:
            pos = projectile.get_position()
            pygame.draw.circle(screen, projectile.colour, (int(pos[0]), int(pos[1])), 8)

        elapsed_seconds = current_time
        minutes = int(elapsed_seconds // 60)
        seconds = elapsed_seconds % 60
        time_text = f"Time: {minutes:02d}:{seconds:05.2f}"
        text_surface = font.render(time_text, True, (255, 255, 255))
        screen.blit(text_surface, (10, 10))

        pygame.display.flip()
        clock.tick(FPS)

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
    owned_names = [c.card.name for c in player.field + player.bench]
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
            p_colour = get_player_colour(p.name)
            o_colour = get_player_colour(opponent.name)
            print(f"\nMatchup: {p_colour}{p.name} ❤️{p.hp}\033[0m VS {o_colour}{opponent.name} ❤️{opponent.hp}\033[0m")
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
        player.give_starting_exe()

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