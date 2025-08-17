# --- Standard Libraries ---
import random
import time
from collections import deque

# --- Cards ---
from merge_sim.cards import (
    Card,
)

# --- Globals / Shared State ---
from .constants import BOARD_ROWS, BOARD_COLS, CRIT_CHANCE, CRIT_MULTIPLIER, bombs, reserved_positions

# --- Board / Hex Utilities ---
from .board_utils import (
    get_occupied_positions,
)
from .hex_utils import (
    hex_line,
    get_units_in_radius,
    hex_distance,
    hex_neighbors,
    find_path_bfs_to_range
)

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
    print(f"🪦 Attempting to spawn skeleton")

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
        self.noble_damage_taken_multiplier = 1.0
        self.noble_damage_dealt_multiplier = 1.0
        self._ranger_stacks = 0  # Ranger stacks for attack speed bonus
        self.crit_chance = 0.15
        self.crit_mult = 1.5

    def restore_full_health(self):
        self.current_hp = self.card.health
        self.max_hp = self.card.health
        self.alive = True
        self.status_effects.clear()
        self.move_cooldown = 0
        self.last_attack_time = 0
        self.current_target = None
        self.is_attacking = False
        self.invisible = False
        self.last_attack_target = None
        self.dash_pending = False
        self.killed_enemy_this_round = [] 
        self.last_update_time = 0
        self.attack_count = 0
        self.archer_queen_invis_triggered = False
        self.noble_damage_taken_multiplier = 1.0
        self.noble_damage_dealt_multiplier = 1.0
        self._ranger_stacks = 0  # Ranger stacks for attack speed bonus
        self.crit_chance = 0.15
        self.crit_mult = 1.5

    def take_damage(self, damage, grid=None, all_units=None, attacker=None):
        
        effective_damage = damage * getattr(self, "noble_damage_taken_multiplier", 1.0)
    
        self.current_hp -= effective_damage
        print(f"{self.card.name} (Owner: {self.owner.name}) takes {effective_damage} damage! HP: {self.current_hp}")

        # --- Notify Ace manager for damage dealt (heal) ---
        if attacker and hasattr(attacker.owner, "ace_manager"):
            ace_manager = attacker.owner.ace_manager
            if attacker == ace_manager.captain:
                ace_manager.on_captain_deal_damage(effective_damage)

        if self.current_hp <= 0 and self.alive:
            self.alive = False
            self.current_hp = 0
            print(f"💀 {self.card.name} (Owner: {self.owner.name}) has been eliminated!")

            # --- Trigger Undead synergy ---
            if getattr(self.owner.opponent, "undead_manager", None):
                self.owner.opponent.undead_manager.on_enemy_death(self)

            # --- Notify Skeleton King if attacker exists ---
            if attacker and attacker.card.name.lower() == "skeleton-king":
                if not hasattr(attacker, "killed_enemy_this_round"):
                    attacker.killed_enemy_this_round = []
                attacker.killed_enemy_this_round.append({
                    "pos": (self.row, self.col),
                    "level": getattr(attacker.card, "star", 1),
                    "owner": attacker.owner
                })
                print(f"🪦 Recorded kill for Skeleton King at {(self.row, self.col)}")

            # --- Notify Ace manager if attacker is Captain ---
            if attacker and hasattr(attacker.owner, "ace_manager"):
                ace_manager = attacker.owner.ace_manager
                if attacker == ace_manager.captain:
                    ace_manager.on_captain_kill(self)

            # --- Giant Skeleton bomb ---
            if self.card.name.lower() == "giant-skeleton" and bombs is not None:
                star = self.card.star
                damage_table = {1: 200, 2: 400, 3: 800, 4: 1600}
                bomb_damage = damage_table.get(star, 200)
                bomb_radius = 1 + star  # radius scales with star level

                bombs.append({
                    "pos": self.get_position(),
                    "damage": bomb_damage,
                    "stun": 1.0,
                    "timer": 1.0,   # seconds until explosion
                    "radius": bomb_radius - 1, # radius checker is 1 bigger than intended
                    "owner": self.owner  # store the Giant Skeleton's owner
                })
                print(f"💣 Giant Skeleton will drop a bomb "
                    f"for {bomb_damage} damage, radius {bomb_radius}, "
                    f"in 1s at {self.get_position()}")

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
    
    def get_damage(self, target=None):
        base = self.card.damage
        effective_damage = base * getattr(self, "noble_damage_dealt_multiplier", 1.0)

        # --- Thrower synergy ---
        if (
            hasattr(self.owner, "thrower_synergy")
            and self.owner.thrower_synergy.thrower_active
            and "thrower" in getattr(self.card, "modifiers", [])
            and target is not None
        ):
            distance = hex_distance(self.get_position(), target.get_position())
            bonus_mult = 1 + (0.1 * distance)
            effective_damage *= bonus_mult
            print(f"🏹 {self.card.name} deals {effective_damage:.1f} damage (distance {distance}, +{int(distance*10)}%)")

        # --- Undead synergy ---
        if (
            hasattr(self.owner, "undead_manager")
            and "undead" in getattr(self.card, "modifiers", [])
        ):
            undead_mult = self.owner.undead_manager.get_damage_multiplier(self)
            effective_damage *= undead_mult
            if undead_mult > 1.0:
                print(f"🦴 {self.card.name} damage boosted by Undead synergy x{undead_mult:.2f}")

        # --- Avenger synergy ---
        if hasattr(self.owner, "avenger_manager"):
            avenger_mult = self.owner.avenger_manager.get_damage_multiplier(self)
            effective_damage *= avenger_mult
            if avenger_mult != 1.0:
                print(f"🛡️ {self.card.name} Avenger bonus: x{avenger_mult:.2f}")

        # --- Ace synergy ---
        if hasattr(self.owner, "ace_manager"):
            ace_mult = self.owner.ace_manager.get_damage_multiplier(self)
            effective_damage *= ace_mult
            if ace_mult != 1.0:
                print(f"🃏 {self.card.name} Ace bonus: x{ace_mult:.2f}")

        return effective_damage

    def get_attack_speed(self):
        base = self.card.attack_speed
        mult = 1.0

        # --- Clan buff ---
        if "clan_buff" in self.status_effects:
            clan_manager = getattr(self.owner, "clan_manager", None)
            if clan_manager:
                if clan_manager.clan_count >= 4:
                    mult *= 0.4  # 60% faster
                elif clan_manager.clan_count >= 2:
                    mult *= 0.7  # 30% faster

        # --- Ranger synergy ---
        if "ranger" in getattr(self.card, "modifiers", []):
            ranger_manager = getattr(self.owner, "ranger_manager", None)
            if ranger_manager:
                ranger_mult = ranger_manager.get_attack_speed_multiplier(self)
                mult *= ranger_mult

        # --- Ace Captain hit speed bonus ---
        if "ace_hit_speed_bonus" in getattr(self, "status_effects", {}):
            mult *= 0.8  # +20% attack speed = attacks 20% faster (interval multiplied by 0.8)

        return base * mult

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
        if unit_name == "spear-goblin":
            return self._spear_goblin_attack(primary_target, all_units, combined_grid)
        elif unit_name == "bomber":
            return self._bomber_attack(primary_target, all_units, combined_grid)
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
            return self._executioner_attack(primary_target, all_units, combined_grid)
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

    def _spear_goblin_attack(self, target, all_units, combined_grid):
        """Spear Goblin throws a spear at a single target (ranged)."""
        base_damage = self.get_damage(target)   # ✅ synergy applies
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)

        print(f"🗡️ Spear Goblin throws spear at {target.card.name} for {damage:.1f} damage"
            + (" (CRIT!)" if is_crit else ""))

        target.take_damage(damage, combined_grid, all_units, attacker=self)
        return True

    def _bomber_attack(self, target, all_units, combined_grid):
        # --- MAIN ATTACK ---
        base_damage = self.get_damage(target)   # ✅ use synergy-aware damage
        is_crit_main = random.random() < CRIT_CHANCE
        damage = base_damage * (CRIT_MULTIPLIER if is_crit_main else 1)

        print(f"💣 {self.card.name} strikes {target.card.name} for {damage:.1f} damage"
            + (" (CRIT!)" if is_crit_main else ""))
        target.take_damage(damage, combined_grid, all_units, attacker=self)

        # --- SPLASH DAMAGE ---
        splash_targets = []
        for r, c in hex_neighbors(target.row, target.col):
            if 0 <= r < len(combined_grid) and 0 <= c < len(combined_grid[0]):
                unit = combined_grid[r][c]
                if unit and unit.owner != self.owner:
                    splash_targets.append(unit)

        for unit in splash_targets:
            splash_damage = self.get_damage(unit)   # ✅ synergy with each splash target
            is_crit_splash = random.random() < CRIT_CHANCE
            splash_damage *= CRIT_MULTIPLIER if is_crit_splash else 1
            print(f"💥 Splash hits {unit.card.name} for {splash_damage:.1f} damage"
                + (" (CRIT!)" if is_crit_splash else ""))
            unit.take_damage(splash_damage, combined_grid, all_units, attacker=self)

        return True

    def _valkyrie_attack(self, target, all_units, combined_grid, base_damage):
        # --- INITIAL TARGET ---
        is_crit_main = random.random() < CRIT_CHANCE
        damage_main = base_damage * (CRIT_MULTIPLIER if is_crit_main else 1)
        crit_text_main = "💥 CRIT! " if is_crit_main else ""
        print(f"{crit_text_main}{self.card.name} strikes initial target {target.card.name} for {damage_main} damage")
        target.take_damage(damage_main, combined_grid, all_units, attacker=self)

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
                    unit.take_damage(damage_splash, combined_grid, all_units, attacker=self)

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

    def _executioner_attack(self, target, all_units, combined_grid):
        """Executioner throws axe in straight line, pierces through target for star_level tiles, then returns."""
        star_level = getattr(self.card, 'star', 1)

        print(f"🪓 {self.card.name} throws axe at {target.card.name}!")

        exe_pos = self.get_position()
        target_pos = target.get_position()

        # Direction vector
        dx = target_pos[1] - exe_pos[1]
        dy = target_pos[0] - exe_pos[0]
        distance = max(abs(dx), abs(dy), 1)
        step_x = dx / distance if distance > 0 else 0
        step_y = dy / distance if distance > 0 else 0

        # Axe forward path
        forward_path = []
        for step in range(1, 10):
            next_row = exe_pos[0] + int(step_y * step)
            next_col = exe_pos[1] + int(step_x * step)
            if not (0 <= next_row < BOARD_ROWS and 0 <= next_col < BOARD_COLS):
                break
            forward_path.append((next_row, next_col))
            if (next_row, next_col) == target_pos:
                break

        # Continue past target for pierce
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
                units_hit.setdefault(unit.get_position(), []).append(unit)
                hit_count[unit] = 0

        # --- Forward pass ---
        print(f"🪓 Axe travels forward: {' → '.join([f'({r},{c})' for r, c in complete_forward])}")
        for pos in complete_forward:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        base_damage = self.get_damage(unit)  # ✅ synergy per unit
                        is_crit = random.random() < CRIT_CHANCE
                        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)
                        print(f"{'💥 CRIT! ' if is_crit else ''}Axe hits {unit.card.name} on forward pass for {damage:.1f}!")
                        unit.take_damage(damage, combined_grid, all_units, attacker=self)
                        hit_count[unit] += 1

        # --- Return pass ---
        print(f"🪓 Axe returns: {' → '.join([f'({r},{c})' for r, c in return_path])}")
        for pos in return_path:
            if pos in units_hit:
                for unit in units_hit[pos]:
                    if unit.alive:
                        base_damage = self.get_damage(unit)  # ✅ synergy per unit
                        is_crit = random.random() < CRIT_CHANCE
                        damage = base_damage * (CRIT_MULTIPLIER if is_crit else 1)
                        print(f"{'💥 CRIT! ' if is_crit else ''}Axe hits {unit.card.name} on return pass for {damage:.1f}!")
                        unit.take_damage(damage, combined_grid, all_units, attacker=self)
                        hit_count[unit] += 1

        total_hits = sum(hit_count.values())
        unique_targets = len([u for u in hit_count if hit_count[u] > 0])
        print(f"🪓 Executioner's axe dealt {total_hits} total hits to {unique_targets} enemies!")

        return True

    def _princess_attack(self, target, all_units, combined_grid, base_damage):
        # --- Main attack ---
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units, attacker=self)

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
                    unit.take_damage(splash_damage, combined_grid, all_units, attacker=self)

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
            target.take_damage(final_damage, combined_grid, all_units, attacker=self)
            return True

        return False

    def _royal_ghost_attack(self, target, combined_grid, base_damage, all_units):
        # Roll crit for this attack
        is_crit = random.random() < self.crit_chance
        damage = base_damage * self.crit_mult if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""

        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units, attacker=self)

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
                            unit.take_damage(bonus_damage, combined_grid, all_units, attacker=self)
                            unit.status_effects["stunned"] = 1.0
                            print(f"💥 {unit.card.name} is stunned and takes {bonus_damage:.1f} bonus damage!")

                if farthest_enemy.get_position() not in path:
                    bonus_damage = base_damage + (base_damage * dash_bonus[stars])
                    farthest_enemy.take_damage(bonus_damage, combined_grid, all_units, attacker=self)
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
            target.take_damage(damage, combined_grid, all_units, attacker=self)

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
                t.take_damage(base_damage * 1.5, combined_grid, all_units, attacker=self)       # 1.5x base damage
                t.status_effects['stunned'] = 1.5      # 1.5 seconds stun

            return True  # Special attack executed

        # Normal attack with crit chance
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""

        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units, attacker=self)
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
        
        if target.alive:
            target_pos = target.get_position()  # save before damage

        # --- PRIMARY ATTACK WITH CRIT ---
        is_crit = random.random() < CRIT_CHANCE
        damage = base_damage * CRIT_MULTIPLIER if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} strikes {target.card.name} for {damage} damage")
        target.take_damage(damage, combined_grid, all_units, attacker=self)

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
                        u.take_damage(splash_damage, combined_grid, all_units, attacker=self)

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
        is_crit = random.random() < self.crit_chance
        damage = base_damage * self.crit_mult if is_crit else base_damage
        crit_text = "💥 CRIT! " if is_crit else ""
        print(f"{crit_text}⚔️ {self.card.name} attacks {target.card.name} for {damage} damage")
        target.take_damage(damage, grid, all_units, attacker=self)

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
            next_target.take_damage(dash_damage, grid, all_units, attacker=self)

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
            target.take_damage(damage, grid, all_units, attacker=self)
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
                enemy.take_damage(damage, grid, all_units, attacker=self)
                targets_hit.append(enemy)
                total_targets += 1

        return True

    def _default_attack(self, target, grid, base_damage, all_units):
        """Default attack for unknown units."""
        damage = base_damage
        if random.random() < self.crit_chance:  # 15% crit chance
            damage = int(damage * self.crit_mult)
            print(f"💥 CRITICAL! {self.card.name} deals {damage} damage to {target.card.name}")
        else:
            print(f"⚔️ {self.card.name} attacks {target.card.name} for {damage} damage")
        target.take_damage(damage, grid, all_units, attacker=self)
        return True
    
    def update_status_effects(self, time_step):
        effects_to_remove = []

        # Handle stun logic
        if self.status_effects.get("stunned", 0) > 0:
            self.attack_count = 0
            self.dash_pending = False

        # Update all effects
        for effect in list(self.status_effects.keys()):
            value = self.status_effects[effect]

            if effect in ["stunned", "invisible", "clan_buff"]:
                new_time = value - time_step
                if new_time <= 0:
                    effects_to_remove.append(effect)
                else:
                    self.status_effects[effect] = new_time

            elif effect == "clan_heal":
                # Spread heal over duration
                heal_duration = self.status_effects.get("clan_heal_duration", 1)
                heal_amount = value * (time_step / heal_duration)
                self.current_hp = min(self.max_hp, self.current_hp + heal_amount)

                # Reduce remaining heal
                self.status_effects[effect] -= heal_amount
                self.status_effects["clan_heal_duration"] -= time_step

                if self.status_effects["clan_heal_duration"] <= 0:
                    effects_to_remove.append("clan_heal")
                    effects_to_remove.append("clan_heal_duration")

            elif effect == "ace_hit_speed_bonus":
                new_time = value - time_step
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
            elif effect == "clan_buff":
                print(f"✨ {self.card.name}'s Clan buff expired")
            elif effect == "ace_hit_speed_bonus":
                print(f"🃏 {self.card.name}'s temporary Ace attack speed bonus expired")

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
