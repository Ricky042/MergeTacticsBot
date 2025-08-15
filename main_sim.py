import random
import copy
from collections import deque
from merge_sim.cards import Card, CARD_STATS, card_to_symbol, BASE_TROOP_STATS
from merge_sim.visualise import draw_grid, hex_to_pixel, PLAYER_COLOURS, HEX_SIZE
import pygame
from collections import deque
import time

BOARD_ROWS = 8
BOARD_COLS = 5
CRIT_CHANCE = 0.15
CRIT_MULTIPLIER = 1.5

# At the top, after combining units
reserved_positions = set()

def get_occupied_positions(units, reserved_positions=None, excluding_unit=None):
    """
    Returns a set of occupied positions on the board.

    Args:
        units (list): List of all units.
        reserved_positions (set, optional): Positions temporarily reserved (like jump targets).
        excluding_unit (unit, optional): Unit to ignore (usually the one currently moving).

    Returns:
        set of (row, col) tuples.
    """
    if reserved_positions is None:
        reserved_positions = set()

    occupied = set()
    for unit in units:
        if unit.alive and unit != excluding_unit:
            occupied.add((unit.row, unit.col))  # or unit.get_position() if you have that
    occupied.update(reserved_positions)
    return occupied

def hex_line(start, end):
    """Return the hexes from start to end inclusive using cube coords."""
    # Convert axial (q, r) to cube coords
    def axial_to_cube(q, r):
        x = q
        z = r
        y = -x - z
        return (x, y, z)

    def cube_to_axial(x, y, z):
        return (x, z)

    start_cube = axial_to_cube(*start)
    end_cube = axial_to_cube(*end)

    N = hex_distance(start, end)
    results = []
    for i in range(N + 1):
        t = i / max(1, N)
        # linear interpolate in cube space
        x = start_cube[0] + (end_cube[0] - start_cube[0]) * t
        y = start_cube[1] + (end_cube[1] - start_cube[1]) * t
        z = start_cube[2] + (end_cube[2] - start_cube[2]) * t
        # cube_round
        rx, ry, rz = round(x), round(y), round(z)
        dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry
        results.append(cube_to_axial(rx, ry, rz))
    return results

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
        name = "archer-queen"
        
        # Assuming Card constructor takes (name, cost, star)
        card = Card(name, 5, star=1)  # Prince costs 2 elixir, star 1
        
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
    # Skip invalid positions
    if row is None or col is None:
        return []

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

def find_path_bfs_to_range(start_pos, target_pos, attack_range, occupied_positions):
    """
    BFS to find the shortest path from start_pos to any hex within attack_range
    of target_pos, avoiding occupied_positions.

    Args:
        start_pos (tuple): (row, col) starting position
        target_pos (tuple): (row, col) target's position
        attack_range (int): how far this unit can attack
        occupied_positions (set): set of (row, col) to avoid

    Returns:
        list of (row, col) positions forming the path, including start and final tile,
        or None if no path exists.
    """

    queue = deque()
    queue.append((start_pos, [start_pos]))  # (current_pos, path_so_far)
    visited = set()
    visited.add(start_pos)

    while queue:
        current_pos, path = queue.popleft()
        row, col = current_pos

        # Check if within attack range
        distance_to_target = hex_distance(current_pos, target_pos)
        if distance_to_target <= attack_range:
            return path

        # Explore neighbors
        for neighbor in hex_neighbors(row, col):
            if neighbor in visited or neighbor in occupied_positions:
                continue
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))

    # No path found
    return None

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
        self.last_attack_time = None      # Time since last attack
        self.move_cooldown = 0         # Movement cooldown based on speed
        self.status_effects = {}       # Status effects like stun, poison, etc.
        self.ability_cooldown = 0      # Cooldown for special abilities
        self.last_update_time = 0  # Last time this unit was updated
        self.invisible = False  # If the unit is invisible (e.g. Royal Ghost)
        self.attack_count = 0
        self.pending_dash_path = []
        self.last_attack_target = None  # Last target attacked, used for dash attacks
        self.dash_pending = False  # If a dash attack is pending
        self.killed_enemy_this_round = []  # Track if this unit killed an enemy this round
        self.archer_queen_invis_triggered = False

    def restore_full_health(self):
        self.current_hp = self.card.health
        self.alive = True
        self.status_effects.clear()
        self.move_cooldown = 0
        self.last_attack_time = 0
        self.current_target = None
        self.is_attacking = False
        self.invisible = False
        self.last_attack_target = None
        self.dash_pending = False
        self.last_update_time = 0
        self.attack_count = 0
        self.archer_queen_invis_triggered = False

    def take_damage(self, damage, grid=None, all_units=None):
        self.current_hp -= damage
        print(f"{self.card.name} (Owner: {self.owner.name}) takes {damage} damage! HP: {self.current_hp}")

        if self.current_hp <= 0 and self.alive:
            self.alive = False
            self.current_hp = 0
            print(f"💀 {self.card.name} (Owner: {self.owner.name}) has been eliminated!")

            # --- CLEAR CURRENT_TARGET REFERENCES IN OTHER UNITS ---
            if all_units is not None:
                for unit in all_units:
                    if getattr(unit, 'current_target', None) == self:
                        unit.current_target = None
                        print(f"🔹 Removed {self.card.name} (Owner: {self.owner.name}) "
                            f"as current_target from {unit.card.name} (Owner: {unit.owner.name})")

            # --- CLEAR GRID POSITION ---
            if grid is not None and self.row is not None and self.col is not None:
                grid[self.row][self.col] = None
                self.row, self.col = None, None

    def get_position(self):
        if getattr(self, "row", None) is None or getattr(self, "col", None) is None:
            return None
        return (self.row, self.col)

    
    def move_to(self, new_row, new_col, grid):
        rows = len(grid)
        cols = len(grid[0]) if rows > 0 else 0

        # Check if new position is within bounds
        if not (0 <= new_row < rows and 0 <= new_col < cols):
            print(f"❌ ERROR: Attempt to move {self.card.name} to out-of-bounds position ({new_row}, {new_col})")
            return False

        # Check if the target cell is already occupied by a different unit
        occupant = grid[new_row][new_col]
        if occupant is not None and occupant != self:
            print(f"❌ ERROR: Attempt to move {self.card.name} to occupied cell ({new_row}, {new_col}) by {occupant.card.name}")
            return False

        # Remove unit from old grid position if valid
        if self.row is not None and self.col is not None:
            # Sanity check: ensure the grid cell contains this unit before clearing
            if grid[self.row][self.col] == self:
                grid[self.row][self.col] = None
            else:
                print(f"⚠️ WARNING: Grid mismatch on clearing old position ({self.row}, {self.col}) for {self.card.name}")

        # Update unit's internal position
        self.row = new_row
        self.col = new_col

        # Place unit in new position on the grid
        grid[new_row][new_col] = self

        print(f"DEBUG: Placed {self.card.name} at ({self.row}, {self.col})")

        return True

    def get_range(self):
        return getattr(self.card, 'range', 1)
    
    def get_damage(self):
        return getattr(self.card, 'damage', 50)
    
    def get_attack_speed(self):
        return getattr(self.card, 'attack_speed', 1.0)
    
    def get_move_speed(self):
        return getattr(self.card, 'speed', 1.0)
    
    def can_attack(self, current_time):        
        attack_interval = self.get_attack_speed()  # seconds per attack
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
        elif unit_name == "mega-knight":
            return self._mega_knight_attack(primary_target, all_units, combined_grid, base_damage, reserved_positions)
        elif unit_name == "royal-ghost":
            return self._royal_ghost_attack(primary_target, combined_grid, base_damage, all_units)
        elif unit_name == "bandit":
            return self._bandit_attack(primary_target, all_units, combined_grid, base_damage)
        elif unit_name == "goblin-machine":
            return self._goblin_machine_attack(primary_target, all_units, combined_grid, base_damage)
        elif unit_name == "skeleton-king":
            return self._skeleton_king_attack(primary_target, all_units, combined_grid, base_damage)
        elif unit_name == "golden-knight":
            return self._golden_knight_attack(primary_target, all_units, base_damage, combined_grid)
        elif unit_name == "archer-queen":
            return self._archer_queen_attack(primary_target, all_units, combined_grid, base_damage)
        else:
            #Default attack
            return self._default_attack(primary_target, combined_grid,  base_damage, all_units)
    
    # === UNIQUE ATTACK IMPLEMENTATIONS ===
    
    def _bomber_attack(self, target, all_units, combined_grid, base_damage):
        # --- MAIN ATTACK ---
        is_crit_main = random.random() < CRIT_CHANCE
        damage = base_damage * (CRIT_MULTIPLIER if is_crit_main else 1)

        print(f"💣 {self.card.name} strikes {target.card.name} for {damage} damage"
            + (" (CRIT!)" if is_crit_main else ""))
        target.take_damage(damage, combined_grid, all_units)

        # --- SPLASH DAMAGE ---
        splash_targets = []
        for r, c in hex_neighbors(target.row, target.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                if unit and unit.owner != self.owner:
                    splash_targets.append(unit)

        for unit in splash_targets:
            # Each splash target rolls its own crit chance
            is_crit_splash = random.random() < CRIT_CHANCE
            splash_damage = base_damage * (CRIT_MULTIPLIER if is_crit_splash else 1)
            print(f"💥 Splash hits {unit.card.name} for {splash_damage} damage"
                + (" (CRIT!)" if is_crit_splash else ""))
            unit.take_damage(splash_damage, combined_grid, all_units)

        return True

    def _valkyrie_attack(self, target, all_units, combined_grid, base_damage):
        # --- INITIAL TARGET ---
        is_crit_main = random.random() < CRIT_CHANCE
        damage_main = base_damage * (CRIT_MULTIPLIER if is_crit_main else 1)
        crit_text_main = "💥 CRIT! " if is_crit_main else ""
        print(f"{crit_text_main}{self.card.name} strikes initial target {target.card.name} for {damage_main} damage")
        target.take_damage(damage_main, combined_grid, all_units)

        # --- SPLASH TARGETS ---
        for r, c in hex_neighbors(self.row, self.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                # Check unit exists, is an enemy, and is not the initial target
                if unit and unit.owner != self.owner and unit != target:
                    # Roll crit separately for each splash target
                    is_crit_splash = random.random() < CRIT_CHANCE
                    damage_splash = base_damage * (CRIT_MULTIPLIER if is_crit_splash else 1)
                    crit_text_splash = "💥 CRIT! " if is_crit_splash else ""
                    print(f"{crit_text_splash}{self.card.name} hits splash target {unit.card.name} for {damage_splash} damage")
                    unit.take_damage(damage_splash, combined_grid, all_units)

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
        self.move_to(er, ec, combined_grid)

        # Place enemy
        closest_enemy.move_to(fling_r, fling_c, combined_grid)

        # Apply stun
        closest_enemy.status_effects['stunned'] = 2.0

        # Debug prints
        print(f"🏇 {self.card.name} dashes from {prince_old} to {prince_dest}")
        print(f"👊 {closest_enemy.card.name} flung from {enemy_old} to {(fling_r, fling_c)} and stunned for 2s")

        return True

    def _executioner_attack(self, target, all_units, combined_grid, base_damage):
        """Executioner throws axe in straight line, pierces through target for star_level tiles, then returns."""
        star_level = getattr(self.card, 'star', 1)
        
        print(f"🪓 {self.card.name} throws axe at {target.card.name}!")
        
        # Get positions
        exe_pos = self.get_position()
        target_pos = target.get_position()
        
        # Calculate direction vector
        dx = target_pos[1] - exe_pos[1]  # col difference
        dy = target_pos[0] - exe_pos[0]  # row difference
        distance = max(abs(dx), abs(dy), 1)  # Prevent division by zero
        step_x = dx / distance if distance > 0 else 0
        step_y = dy / distance if distance > 0 else 0
        
        # Trace the axe path - forward journey to target
        forward_path = []
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
        full_path = complete_forward + return_path
        self.pending_dash_path = full_path 
        
        # Map positions to units
        units_hit = {}
        hit_count = {}
        for unit in all_units:
            if unit.alive and unit.owner != self.owner:
                unit_pos = unit.get_position()
                units_hit[unit_pos] = units_hit.get(unit_pos, []) + [unit]
                hit_count[unit] = 0
        
        # --- Forward pass ---
        print(f"🪓 Axe travels forward: {' → '.join([f'({r},{c})' for r, c in complete_forward])}")
        for pos in complete_forward:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        # Roll crit per unit
                        is_crit = random.random() < CRIT_CHANCE
                        damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                        crit_text = "💥 CRIT! " if is_crit else ""
                        print(f"{crit_text}Axe hits {unit.card.name} on forward pass for {damage} damage!")
                        unit.take_damage(damage, combined_grid, all_units)
                        hit_count[unit] += 1
        
        # --- Return pass ---
        print(f"🪓 Axe returns: {' → '.join([f'({r},{c})' for r, c in return_path])}")
        for pos in return_path:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        # Roll crit per unit
                        is_crit = random.random() < CRIT_CHANCE
                        damage = int(base_damage * CRIT_MULTIPLIER) if is_crit else base_damage
                        crit_text = "💥 CRIT! " if is_crit else ""
                        print(f"{crit_text}Axe hits {unit.card.name} on return pass for {damage} damage!")
                        unit.take_damage(damage, combined_grid, all_units)
                        hit_count[unit] += 1
        
        total_hits = sum(hit_count.values())
        unique_targets = len([u for u in hit_count.keys() if hit_count[u] > 0])
        print(f"🪓 Executioner's axe dealt {total_hits} total hits to {unique_targets} enemies!")
        
        return True

    def _princess_attack(self, target, all_units, combined_grid, base_damage):
        # --- Main attack ---
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units)

        # --- Splash damage to adjacent enemies ---
        for r, c in hex_neighbors(target.row, target.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                if unit and unit.owner != self.owner:
                    # Roll crit per splash unit
                    unit_crit = random.random() < CRIT_CHANCE
                    splash_damage = base_damage * CRIT_MULTIPLIER if unit_crit else base_damage
                    crit_text = "💥 CRIT! " if unit_crit else ""
                    print(f"{crit_text}💥 {self.card.name} splash hits {unit.card.name} for {splash_damage} damage")
                    unit.take_damage(splash_damage, combined_grid, all_units)

        return True

    def _mega_knight_attack(self, target, all_units, combined_grid, base_damage, reserved_positions):

        current_time = time.time()
        damage = base_damage

        star_level = getattr(self.card, "star", 1)

        # Map star level to stun radius and jump cooldown (seconds)
        stun_radius_by_star = {1: 2, 2: 2, 3: 3, 4: 4}
        jump_cooldown_by_star = {1: 6, 2: 5, 3: 4, 4: 3}

        stun_radius = stun_radius_by_star.get(star_level, 2)
        jump_cooldown = jump_cooldown_by_star.get(star_level, 6)

        jump_travel_time = 1  # seconds fixed for jump animation

        # Initialize last_jump_time if not set
        if not hasattr(self, 'last_jump_time'):
            self.last_jump_time = 0

        # Initialize jump state attributes if missing
        if not hasattr(self, 'is_jumping'):
            self.is_jumping = False
        if not hasattr(self, 'jump_start_time'):
            self.jump_start_time = 0
        if not hasattr(self, 'jump_target_pos'):
            self.jump_target_pos = None

        # Helper: roll crit
        def roll_crit():
            return random.random() < CRIT_CHANCE

        # If currently jumping, handle jump progress
        if self.is_jumping:
            elapsed = current_time - self.jump_start_time
            if elapsed >= jump_travel_time:
                # Finish jump: use move_to() to update position and grid
                old_pos = (self.row, self.col)
                new_r, new_c = self.jump_target_pos
                self.move_to(new_r, new_c, combined_grid)
                print(f"🚀 {self.card.name} [{self.owner.name}] finishes jump from {old_pos} to {self.jump_target_pos}!")

                # Find the new target on the tile just landed on
                new_target = None
                for unit in all_units:
                    if unit.alive and (unit.row, unit.col) == (new_r, new_c) and unit.owner != self.owner:
                        new_target = unit
                        break

                if new_target:
                    self.current_target = new_target
                    self.last_attack_time = None
                    print(f"[DEBUG] {self.card.name} retargeted to {new_target.card.name} after jump.")

                # Stun enemies in radius stun_radius (fixed 2 seconds)
                stunned_units = get_units_in_radius(self.jump_target_pos, stun_radius - 1, all_units)
                for u in stunned_units:
                    if u.alive and u.owner != self.owner:
                        u.status_effects['stunned'] = 2.0
                        print(f"💫 {u.card.name} [{u.owner.name}] is stunned for 2 seconds by {self.card.name} [{self.owner.name}]!")

                # Release reservation of the jump target tile
                if self.jump_target_pos in reserved_positions:
                    reserved_positions.remove(self.jump_target_pos)

                self.is_jumping = False
                self.last_jump_time = current_time
                self.jump_target_pos = None
                return True  # Jump completed, turn ends here

            else:
                # Still mid-jump, skip attack and movement
                return False

        # Not jumping: check if it's time to start a new jump
        if current_time - self.last_jump_time >= jump_cooldown:
            max_neighbors = -1
            best_hex = None

            # Search hexes within range 3 for max neighbors AND free hex (no unit occupying, no reservation)
            for r in range(max(0, self.row - 3), min(BOARD_ROWS, self.row + 4)):
                for c in range(max(0, self.col - 3), min(BOARD_COLS, self.col + 4)):
                    if hex_distance((self.row, self.col), (r, c)) <= 3:
                        # Check if hex is free and not reserved
                        if combined_grid[r][c] is not None or (r, c) in reserved_positions:
                            continue  # Occupied or reserved, skip

                        neighbors = 0
                        for u in all_units:
                            if u.alive and (u.row, u.col) != (r, c):
                                if hex_distance((u.row, u.col), (r, c)) == 1:
                                    neighbors += 1
                        if neighbors > max_neighbors:
                            max_neighbors = neighbors
                            best_hex = (r, c)

            if best_hex:
                # Reserve target hex
                reserved_positions.add(best_hex)

                # Start jump: mark state and time
                self.is_jumping = True
                self.jump_start_time = current_time
                self.jump_target_pos = best_hex
                print(f"🚀 {self.card.name} [{self.owner.name}] starts jumping towards {best_hex}!")
                return False  # Skip attack during jump start

        # Normal melee attack if no jump this turn
        if target and target.alive:
            crit = roll_crit()
            final_damage = damage * CRIT_MULTIPLIER if crit else damage
            if crit:
                print(f"🔥 CRITICAL HIT! Damage multiplied to {final_damage}!")
            print(f"⚔️ {self.card.name} [{self.owner.name}] strikes {target.card.name} [{target.owner.name}] for {final_damage} damage")
            target.take_damage(final_damage, combined_grid, all_units)
            return True

        return False

    def _royal_ghost_attack(self, target, combined_grid, base_damage, all_units):
        # Roll crit for this attack
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""

        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units)

        # Track attack count for invisibility
        self.attack_count += 1
        if self.attack_count >= 3:
            self.trigger_invisibility()
            self.attack_count = 0  # reset for next cycle

        return True
 
    def trigger_invisibility(self):
        star_durations = {1: 1.5, 2: 2.0, 3: 2.5, 4: 3.5}
        duration = star_durations.get(self.card.star, 1.5)
        self.status_effects["invisible"] = duration
        self.invisible = True
        print(f"👻 {self.card.name} turns invisible for {duration} seconds!")
    
    def _bandit_attack(self, target, all_units, combined_grid, base_damage):
        if not hasattr(self, "last_attack_target"):
            self.last_attack_target = None
            self.attack_count = 0
            self.dash_pending = False

        dash_thresholds = {1: 3, 2: 2, 3: 1, 4: 1}
        dash_bonus = {1: 0.5, 2: 0.5, 3: 0.8, 4: 1.5}
        stars = self.card.star

        if self.dash_pending:
            # Perform dash instead of attack damage, then clear flag
            self.dash_pending = False

            occupied_positions = get_occupied_positions(all_units, excluding_unit=self)
            start_pos = self.get_position()

            farthest_enemy = None
            max_dist = -1
            landing_spot = None

            # Find farthest enemy within 3 tiles with empty neighbor within dash range
            for enemy in all_units:
                if enemy.alive and enemy.owner != self.owner:
                    dist_to_enemy = hex_distance(start_pos, enemy.get_position())
                    if dist_to_enemy <= 3:
                        empty_neighbors = [
                            pos for pos in hex_neighbors(*enemy.get_position())
                            if pos not in occupied_positions and hex_distance(start_pos, pos) <= 3
                        ]
                        if not empty_neighbors:
                            continue

                        farthest_neighbor = max(empty_neighbors, key=lambda pos: hex_distance(start_pos, pos))
                        dist_to_neighbor = hex_distance(start_pos, farthest_neighbor)

                        if dist_to_neighbor > max_dist:
                            max_dist = dist_to_neighbor
                            farthest_enemy = enemy
                            landing_spot = farthest_neighbor

            if farthest_enemy and landing_spot:
                path = hex_line(start_pos, landing_spot)

                print(f"🏃‍♀️  {self.card.name} dashes along path: {path} to {landing_spot}")

                for hex_pos in path:
                    for unit in all_units:
                        if unit.alive and unit.owner != self.owner and unit.get_position() == hex_pos:
                            bonus_damage = base_damage + (base_damage * dash_bonus[stars])
                            unit.take_damage(bonus_damage, combined_grid, all_units)
                            unit.status_effects["stunned"] = 1.0
                            print(f"💥 {unit.card.name} is stunned and takes {bonus_damage:.1f} bonus damage!")

                if farthest_enemy.get_position() not in path:
                    bonus_damage = base_damage + (base_damage * dash_bonus[stars])
                    farthest_enemy.take_damage(bonus_damage, combined_grid, all_units)
                    farthest_enemy.status_effects["stunned"] = 1.0
                    print(f"💥 {farthest_enemy.card.name} (final target) is stunned and takes {bonus_damage:.1f} bonus damage!")

                self.move_to(*landing_spot, combined_grid)
                print(f"🏃‍♀️  {self.card.name} finishes dash at {landing_spot}!")

            return True

        else:
            # Normal attack flow with crit chance
            is_crit = random.random() < CRIT_CHANCE
            damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
            crit_text = "💥 CRIT! " if is_crit else ""

            print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
            target.take_damage(damage, combined_grid, all_units)

            if self.last_attack_target == target:
                self.attack_count += 1
            else:
                self.last_attack_target = target
                self.attack_count = 1

            # If threshold reached, set dash pending flag to True
            if self.attack_count >= dash_thresholds[stars]:
                print(f"⚡ {self.card.name} prepares to dash on next attack!")
                self.dash_pending = True
                self.attack_count = 0
                self.last_attack_target = None

            return True

    def _goblin_machine_attack(self, target, all_units, combined_grid, base_damage):
        """
        Goblin Machine attack:
        - Normal attack: strikes the target for base_damage.
        - Special rocket attack triggers after attacking the SAME target N times (scales by level):
            Level 1: 3 attacks → special
            Level 2: 2 attacks → special
            Level 3: 1 attack → special
            Level 4+: 1 attack → special
        - Special rockets:
            Level 1 → 1 rocket
            Level 2 → 2 rockets
            Level 3 → 3 rockets
            Level 4 → 6 rockets
        Each rocket deals 1.5x base damage and stuns for 1.5 seconds.
        """

        # Initialize attack tracking if missing
        if not hasattr(self, 'attack_count'):
            self.attack_count = 0
        if not hasattr(self, 'last_attack_target'):
            self.last_attack_target = None

        # Determine card level
        level = getattr(self.card, "star", 1)

        # Scaling tables
        attacks_to_trigger = {1: 3, 2: 2, 3: 1, 4: 1}
        rockets_per_level   = {1: 1, 2: 2, 3: 3, 4: 6}

        trigger_count = attacks_to_trigger.get(level, 1)
        rocket_count = rockets_per_level.get(level, 1)

        # Reset counter if switching targets
        if target != self.last_attack_target:
            self.attack_count = 0
            self.last_attack_target = target

        # Check if special rocket attack should trigger
        if self.attack_count >= trigger_count:
            self.attack_count = 0  # Reset counter after special attack

            # Get all alive enemies
            enemies = [u for u in all_units if u.alive and u.owner != self.owner]
            # Sort by distance from self (furthest first)
            enemies.sort(key=lambda u: hex_distance(self.get_position(), u.get_position()), reverse=True)
            # Select up to rocket_count enemies
            targets = enemies[:rocket_count]

            for t in targets:
                print(f"💥 {self.card.name} fires rocket at {t.card.name}!")
                t.take_damage(base_damage * 1.5, combined_grid, all_units)       # 1.5x base damage
                t.status_effects['stunned'] = 1.5      # 1.5 seconds stun

            return True  # Special attack executed

        # Normal attack with crit chance
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""

        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units)
        self.attack_count += 1
        return True
    
    def _skeleton_king_attack(self, target, all_units, combined_grid, base_damage):
        """
        Skeleton King attack:
        - Deals base damage to primary target (can crit individually).
        - Applies cone splash damage to tiles behind the target (each unit rolls crit individually).
        - Spawns a skeleton at target's position if target dies.
        - Skeleton star/level matches the Skeleton King card level.
        """
        if not target.alive:
            return False

        # --- PRIMARY ATTACK WITH CRIT ---
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units)

        # --- CONE SPLASH DAMAGE ---
        sr, sc = self.get_position()
        tr, tc = target.get_position()
        dr = tr - sr
        dc = tc - sc
        step_r = 0 if dr == 0 else (dr // abs(dr))
        step_c = 0 if dc == 0 else (dc // abs(dc))

        for nr, nc in hex_neighbors(tr, tc):
            # Only hit tiles roughly in the direction behind the target
            if (nr - tr == step_r or nc - tc == step_c):
                for u in all_units:
                    if u.alive and u.get_position() == (nr, nc) and u != target:
                        # Each splash unit rolls crit independently
                        splash_crit = random.random() < CRIT_CHANCE
                        splash_damage = base_damage * CRIT_MULTIPLIER if splash_crit else base_damage
                        splash_crit_text = "💥 CRIT! " if splash_crit else ""
                        print(f"{splash_crit_text}{self.card.name} hits {u.card.name} in cone for {splash_damage} damage!")
                        u.take_damage(splash_damage, combined_grid, all_units)

        # Track killed enemy for skeleton spawn
        if not target.alive:
            if not hasattr(self, "killed_enemy_this_round"):
                self.killed_enemy_this_round = []
            self.killed_enemy_this_round.append({
                "pos": target.get_position(),
                "level": getattr(self.card, "star", 1),
                "owner": self.owner
            })

        return True

    def _golden_knight_attack(self, target, all_units, base_damage, grid):
        """
        Golden Knight attack:
        - Normal attack can crit individually.
        - If the target dies, dashes to the lowest HP enemy adjacent, dealing scaled dash damage.
        - Dash damage scales with level:
            Level 1: 50%, Level 2: 80%, Level 3: 150%, Level 4: 500%
        - Dash only damages the final target, not units along the path.
        - Continues chaining if each new target dies.
        """
        # --- NORMAL ATTACK WITH CRIT ---
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} attacks {target.card.name} for {damage} damage")
        target.take_damage(damage, grid, all_units)

        # --- DASH DAMAGE MULTIPLIER BASED ON LEVEL ---
        level = getattr(self.card, "star", 1)
        dash_multiplier = {1: 1.5, 2: 1.8, 3: 2.5, 4: 6.0}.get(level, 1.5)
        dash_damage = base_damage * dash_multiplier

        current_target = target
        dash_count = 0

        while True:
            # Stop if the current target survives
            if current_target.alive:
                break

            dash_count += 1
            print(f"\n🔄 DASH CHAIN STEP {dash_count}: {self.card.name} is chaining...")

            # Find next lowest HP enemy excluding dead ones
            living_enemies = [u for u in all_units if u.alive and u.owner != self.owner]
            print(f"🧮 Living enemies: {[f'{u.card.name}({u.current_hp} HP)' for u in living_enemies]}")

            if not living_enemies:
                print("❌ No living enemies left — stopping chain.")
                break

            # Pick enemy with lowest current HP
            next_target = min(living_enemies, key=lambda u: u.current_hp)
            print(f"🎯 Next target: {next_target.card.name} with {next_target.current_hp} HP")

            # Find available adjacent tiles
            adj_tiles = hex_neighbors(*next_target.get_position())
            occupied = {(u.row, u.col) for u in all_units if u.alive and u != self}
            adj_free = [pos for pos in adj_tiles if pos not in occupied]

            if not adj_free:
                print(f"⚠️ {self.card.name} cannot dash: no free adjacent tiles to {next_target.card.name}")
                break

            # Move to first free adjacent tile
            new_pos = adj_free[0]
            print(f"💨 {self.card.name} dashes to {new_pos} adjacent to {next_target.card.name}")
            moved = self.move_to(new_pos[0], new_pos[1], grid)
            if not moved:
                print(f"❌ Failed to move {self.card.name} to {new_pos}")
                break

            # Update simulation position tracking
            self.last_position = new_pos
            self.current_target = next_target

            # Deal dash damage (unchanged, no crit)
            print(f"💥 {self.card.name} deals {dash_damage} dash damage to {next_target.card.name}")
            next_target.take_damage(dash_damage, grid, all_units)

            # Prepare for next chain
            current_target = next_target

        return True

    def _archer_queen_attack(self, target, all_units, grid, base_damage):
        """
        Archer Queen attack:
        - Main attack on primary target.
        - Can hit additional units based on star level if within range.
        - Becomes invisible for 2.5s and gains a damage bonus when at <=50% HP.
        - Star level determines max targets and damage boost.
        - Each hit rolls crit independently.
        """

        # --- STAR LEVEL SETTINGS ---
        star_level = getattr(self.card, "star", 1)
        level_settings = {
            1: {"max_targets": 2, "damage_bonus": 0.5},
            2: {"max_targets": 3, "damage_bonus": 0.8},
            3: {"max_targets": 4, "damage_bonus": 1.5},
            4: {"max_targets": 6, "damage_bonus": 5.0},
        }
        settings = level_settings.get(star_level, {"max_targets": 2, "damage_bonus": 0.5})

        max_targets = settings["max_targets"]
        damage_multiplier = settings["damage_bonus"]

        # --- CHECK FOR INVISIBILITY TRIGGER ---
        if not getattr(self, 'archer_queen_invis_triggered', False) and self.current_hp <= 0.5 * self.max_hp:
            self.status_effects["invisible"] = 2.5
            self.invisible = True
            self.archer_queen_invis_triggered = True
            print(f"🕵️ {self.card.name} becomes invisible for 2.5 seconds!")

        # --- MAIN ATTACK ---
        total_targets = 0
        targets_hit = []

        if target.alive and self.is_in_range_of(target):
            # Roll crit for main target
            is_crit = random.random() < CRIT_CHANCE
            damage = base_damage * (1 + damage_multiplier if self.invisible else 1)
            if is_crit:
                damage *= CRIT_MULTIPLIER
            crit_text = "💥 CRIT! " if is_crit else ""
            print(f"{crit_text}⚔️ {self.card.name} hits {target.card.name} for {damage} damage")
            target.take_damage(damage, grid, all_units)
            targets_hit.append(target)
            total_targets += 1

        # --- ADDITIONAL TARGETS ---
        # Only consider living, visible units that are not the main target
        living_enemies = [
            u for u in all_units
            if u.alive and not getattr(u, 'invisible', False) and u not in targets_hit
        ]

        for enemy in living_enemies:
            if total_targets >= max_targets:
                break
            if self.is_in_range_of(enemy):
                # Roll crit per bonus target
                is_crit = random.random() < CRIT_CHANCE
                damage = base_damage * (1 + damage_multiplier if self.invisible else 1)
                if is_crit:
                    damage *= CRIT_MULTIPLIER
                crit_text = "💥 CRIT! " if is_crit else ""
                print(f"{crit_text}⚔️ {self.card.name} hits {enemy.card.name} for {damage} damage (bonus target)")
                enemy.take_damage(damage, grid, all_units)
                targets_hit.append(enemy)
                total_targets += 1

        return True

    def _default_attack(self, target, grid, base_damage, all_units):
        """Default attack for unknown units."""
        damage = base_damage
        if random.random() < 0.15:  # 15% crit chance
            damage = int(damage * 1.5)
            print(f"💥 CRITICAL! {self.card.name} deals {damage} damage to {target.card.name}")
        else:
            print(f"⚔️ {self.card.name} attacks {target.card.name} for {damage} damage")
        target.take_damage(damage, grid, all_units)
        return True
    
    def update_status_effects(self, time_step):
        effects_to_remove = []
        # Handle stun logic
        if self.status_effects.get("stunned", 0) > 0:
            self.attack_count = 0
            self.dash_pending = False
            remaining_stun = self.status_effects["stunned"]

        # Update all effects
        for effect, remaining_time in list(self.status_effects.items()):
            new_time = remaining_time - time_step
            if new_time <= 0:
                effects_to_remove.append(effect)
            else:
                self.status_effects[effect] = new_time

        # Remove expired effects
        for effect in effects_to_remove:
            del self.status_effects[effect]
            if effect == "stunned":
                print(f"😵 {self.card.name} recovers from stun!")
            elif effect == "invisible":
                self.invisible = False
                print(f"👀 {self.card.name} becomes visible again!")

    def can_act(self):
        if 'stunned' in self.status_effects:
            return False
        # other conditions...
        return True

    def find_closest_enemy(self, all_units):
        """Find the closest living enemy unit, ignoring invisible Royal Ghosts."""
        min_dist = float('inf')
        closest_enemy = None
        
        for unit in all_units:
            if not unit.alive or unit.owner == self.owner:
                continue  # Skip dead or allied units
            
            # Ignore invisible Royal Ghosts
            if 'invisible' in getattr(unit, 'status_effects', {}):
                continue
            
            dist = hex_distance(self.get_position(), unit.get_position())
            if dist < min_dist:
                min_dist = dist
                closest_enemy = unit
        
        return closest_enemy, min_dist

    def is_in_range_of(self, target):
        """Check if target is within attack range based on movement steps."""
        if not target or not target.alive:
            return False
        
        if self.row is None or self.col is None or target.row is None or target.col is None:
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
    
    def should_retarget(self, all_units, grid):
        """
        Determines the best target for this unit to attack.
        Returns:
            CombatUnit: the unit to target, or None if no enemies alive.
        Retarget if:
            - Current target is dead
            - Or another enemy can be reached faster based on THIS unit's attack range
        """
        living_enemies = [u for u in all_units if u.alive and u.owner != self.owner]
        if not living_enemies:
            return None

        occupied = get_occupied_positions(all_units, excluding_unit=self)

        # Distance to current target (steps needed to enter attack range)
        current_target = self.current_target if self.current_target and self.current_target.alive else None
        current_dist = float('inf')
        if current_target:
            current_path = find_path_bfs_to_range(self.get_position(), current_target.get_position(), self.card.range, occupied)
            current_dist = len(current_path) - 1 if current_path else float('inf')

        # Find enemy reachable in fewest steps
        nearest_enemy = current_target
        shortest_dist = current_dist

        for enemy in living_enemies:
            path = find_path_bfs_to_range(self.get_position(), enemy.get_position(), self.card.range, occupied)
            dist = len(path) - 1 if path else float('inf')
            if dist < shortest_dist:
                shortest_dist = dist
                nearest_enemy = enemy

        return nearest_enemy

def spawn_skeleton(pos, level, owner, all_units, combined):
    """
    Spawn a skeleton at the given position.

    Args:
        pos (tuple): (row, col) position to spawn at.
        level (int): Skeleton star/level (matches Skeleton King).
        owner (Player): Owner of the Skeleton.
        all_units (list): List of all units currently in the battle.

    Returns:
        CombatUnit or None: The spawned skeleton, or None if blocked.
    """
    row, col = pos

    # Check if tile is free
    occupied = {(u.row, u.col) for u in all_units if u.alive}
    if (row, col) in occupied:
        print(f"⚠️ Cannot spawn skeleton at {pos}, tile is occupied!")
        return None

    # Create skeleton card and unit
    skeleton_card = Card(name="skeleton", cost=0, star=level)  # cost can be 0 or default
    skeleton_unit = CombatUnit(row=row, col=col, card=skeleton_card, owner=owner)

    # Add to units list
    all_units.append(skeleton_unit)
    combined[pos[0]][pos[1]] = skeleton_unit  # <-- add this
    print(f"☠️ Spawned skeleton at {pos} for {owner.name} with level {level}")

    return skeleton_unit

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
    """
    Simulates a live combat round between two players and visualizes it using pygame.
    Restores all units to full HP before starting, places missing-position units,
    and shows debug information throughout the battle.

    Args:
        players (list): A list containing the two players.
    
    Returns:
        tuple: ([], winner_player_object_or_None, remaining_units_count_or_None)
    """

    if not players or len(players) < 2 or not players[0].opponent:
        return [], None, None

    # --- INITIAL UNIT RESET & PLACEMENT ---
    for player in players:
        for unit in player.field:
            unit.restore_full_health()
            if unit.row is None or unit.col is None:
                player.place_on_grid_random(unit)

    # --- COMBINE PLAYER GRIDS ---
    p1, p2 = players[0], players[0].opponent
    combined = combine_grids(p1, p2)

    # Gather all units into a flat list
    units = []
    seen_units = set()
    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            unit = combined[r][c]
            if unit and unit not in seen_units:
                units.append(unit)
                seen_units.add(unit)

    if not units:
        return [], None, None

    # --- PYGAME INITIALIZATION ---
    pygame.init()
    screen = pygame.display.set_mode((1200, 1000))
    pygame.display.set_caption("MergeTacticsBot Combat Visualization (Live)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('Arial', 30)
    FPS = 60
    projectiles = []

    start_ticks = pygame.time.get_ticks()
    total_paused_time = 0
    paused = False

    round_count = 0
    winner = None
    remaining_units = None

    for unit in units:
        if getattr(unit.card, "name", "").lower() == "prince":
            unit.prince_combat_start_ability([u for u in units if u.alive], combined)


    # --- MAIN SIMULATION LOOP ---
    while True:
        round_count += 1

        # Update living units
        living_units = [u for u in units if u.alive]
        if not living_units:
            break

        # Check if both players still have alive units
        p1_alive = any(u.alive and u.owner == p1 for u in units)
        p2_alive = any(u.alive and u.owner == p2 for u in units)
        if not p1_alive or not p2_alive:
            break

        # --- HANDLE PYGAME EVENTS ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return [], None, None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return [], None, None
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                    if paused:
                        pause_start_time = pygame.time.get_ticks()
                    else:
                        pause_end_time = pygame.time.get_ticks()
                        total_paused_time += (pause_end_time - pause_start_time)

        # --- TIME CALCULATIONS ---
        current_ticks = pygame.time.get_ticks()
        if paused:
            current_time = (pause_start_time - start_ticks - total_paused_time) / 1000.0
        else:
            current_time = (current_ticks - start_ticks - total_paused_time) / 1000.0

        dt = clock.get_time() / 1000.0

        # --- UNIT LOGIC LOOP (handle newly spawned units dynamically) ---
        i = 0
        while i < len(units):
            unit = units[i]

            if not unit.alive:
                i += 1
                continue

            # Update status effects
            time_step = current_time - getattr(unit, 'last_update_time', current_time)
            unit.update_status_effects(time_step)
            unit.last_update_time = current_time

            if not unit.can_act():
                i += 1
                continue

            # Target acquisition
            if not unit.current_target or not unit.current_target.alive or getattr(unit.current_target, 'invisible', False):
                # Only consider alive and visible enemies
                visible_enemies = [u for u in units if u.alive and not getattr(u, 'invisible', False) and u.owner != unit.owner]
                if visible_enemies:
                    closest_enemy, _ = unit.find_closest_enemy(visible_enemies)
                    unit.current_target = closest_enemy
                    unit.is_attacking = False
                    unit.last_attack_time = None

            # Retargeting
            else:
                new_target = unit.should_retarget(units, combined)
                if new_target and new_target != unit.current_target and not getattr(new_target, 'invisible', False):
                    print(f"🔄 {unit.card.name} is retargeting from {unit.current_target.card.name} to {new_target.card.name}")
                    unit.current_target = new_target
                    unit.last_attack_time = None

            # ATTACK LOGIC
            if unit.current_target and unit.is_in_range_of(unit.current_target):
                unit.is_attacking = True
                if unit.last_attack_time is None:
                    unit.last_attack_time = current_time
                elif unit.can_attack(current_time):
                    if unit and unit.current_target and unit.alive and unit.current_target.alive and not getattr(unit.current_target, 'invisible', False):
                        # safe to attack
                        # Perform unit-specific attack
                        try:
                            attacker_pos = hex_to_pixel(*unit.get_position())
                            target_pos = hex_to_pixel(*unit.current_target.get_position())
                            attack_result = unit.attack(unit.current_target, current_time, units, combined)
                            if attack_result:
                                unit.last_attack_time = current_time
                                print(f"Position of {unit.card.name} [{unit.owner.name}]: {unit.get_position()}")
                                colour = PLAYER_COLOURS.get(unit.owner.name, (255, 255, 255))
                                projectiles.append(Projectile(attacker_pos, target_pos, colour))

                        except Exception as e:
                            attacker_name = getattr(unit.card, 'name', 'Unknown')
                            target_name = getattr(unit.current_target.card, 'name', 'Unknown') if unit.current_target else 'None'
                            attacker_pos = unit.get_position() if hasattr(unit, 'get_position') else ('?', '?')
                            target_pos = unit.current_target.get_position() if unit.current_target and hasattr(unit.current_target, 'get_position') else ('?', '?')
                            attacker_owner = getattr(unit.owner, 'name', 'Unknown')
                            target_owner = getattr(unit.current_target.owner, 'name', 'Unknown') if unit.current_target else 'None'
                            attacker_hp = getattr(unit, 'current_hp', 'Unknown')
                            target_hp = getattr(unit.current_target, 'current_hp', 'Unknown') if unit.current_target else 'None'

                            print("⚠️ Attack error:", e)
                            print(f"Attacker: {attacker_name} (Owner: {attacker_owner}, HP: {attacker_hp}, Pos: {attacker_pos})")
                            print(f"Target: {target_name} (Owner: {target_owner}, HP: {target_hp}, Pos: {target_pos})")

                            # Optional: prevent further crashing by only calling take_damage if current_target is valid
                            if unit.current_target and getattr(unit.current_target, 'alive', False):
                                unit.current_target.take_damage(unit.get_damage(), combined, all_units=units)
          
                    unit.last_attack_time = current_time

            else:
                unit.is_attacking = False

            # MOVEMENT LOGIC
            if unit.current_target and unit.current_target.alive and unit.alive:
                target_pos = unit.current_target.get_position()
                if target_pos is None:
                    continue
                if not unit.is_in_range_of(unit.current_target) and unit.can_move(current_time):
                    
                    current_pos = unit.get_position()
                    occupied = get_occupied_positions(units, reserved_positions=None, excluding_unit=unit)

                    best_move = None
                    best_dist = float('inf')
                    for move_pos in hex_neighbors(current_pos[0], current_pos[1]):
                        
                        if move_pos not in occupied:
                            path = find_path_bfs_to_range(move_pos, target_pos, unit.card.range, occupied_positions=occupied)
                            if path:
                                dist = len(path) - 1
                            else:
                                dist = float('inf')
                            if dist < best_dist:
                                best_dist = dist
                                best_move = move_pos
                
                    if best_move:
                        unit.move_to(*best_move, combined)
                        unit.move_cooldown = current_time
                        unit.last_move_time = current_time
                        unit.last_position = best_move

            # AFTER ATTACK/MOVE: newly spawned units are already in 'units', so they'll be processed in subsequent iterations
            i += 1  # increment manually to include new units

        # Spawn skeletons for positions recorded by Skeleton King
        for unit in units:
            if unit.card.name.lower() == "skeleton-king" and hasattr(unit, "killed_enemy_this_round"):
                for killed_info in unit.killed_enemy_this_round:
                    killed_unit = killed_info.get("unit")
                    if killed_unit and killed_unit.owner != unit.owner and killed_unit.card.name.lower() != "skeleton":
                        spawn_skeleton(
                            killed_info["pos"], 
                            killed_info["level"], 
                            killed_info["owner"], 
                            units,
                            combined
                        )
                # Reset for next round
                unit.killed_enemy_this_round = []

        # --- UPDATE PROJECTILES ---
        for projectile in projectiles[:]:
            projectile.update(dt)
            if projectile.is_finished():
                projectiles.remove(projectile)

        # --- RENDER FRAME ---
        screen.fill((30, 30, 30))
        draw_grid(screen, combined, units=units)
        for projectile in projectiles:
            pos = projectile.get_position()
            pygame.draw.circle(screen, projectile.colour, (int(pos[0]), int(pos[1])), 8)

        pygame.display.flip()
        clock.tick(FPS)

        # --- CHECK FOR END CONDITION ---
        p1_alive = any(u.alive and u.owner == p1 for u in units)
        p2_alive = any(u.alive and u.owner == p2 for u in units)
        if not p1_alive and not p2_alive:
            winner = None
            remaining_units = None
            break
        elif not p1_alive:
            winner = p2
            remaining_units = len([u for u in units if u.alive and u.owner == p2])
            break
        elif not p2_alive:
            winner = p1
            remaining_units = len([u for u in units if u.alive and u.owner == p1])
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
            
            # Only count original units for end-of-round damage
            original_units_remaining = [
                u for u in (p.field + opponent.field)
                if u.alive and u.card.name.lower() != "skeleton"
            ]
            remaining_units_count = len(original_units_remaining)

            # Apply damage based on original units only
            if winner == p:
                opponent.take_damage(remaining_units_count + 1)
            elif winner == opponent:
                p.take_damage(remaining_units_count + 1)
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