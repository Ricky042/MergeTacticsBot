# --- Standard Libraries ---
from collections import deque

# --- Globals / Shared State ---
from .constants import BOARD_ROWS, BOARD_COLS

# --- Projectiles ---
from .projectile import Projectile

# --- Bots ---
from .bot import *

EVEN_ROW_OFFSETS = [  # even row (0, 2, 4, ...)
    (-1, 0), (-1, +1), (0, +1),
    (+1, +1), (+1, 0), (0, -1)
]

ODD_ROW_OFFSETS = [  # odd row (1, 3, 5, ...)
    (-1, -1), (-1, 0), (0, +1),
    (+1, 0), (+1, -1), (0, -1)
]

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

def get_units_in_radius(center, radius, units):
        cr, cc = center
        return [u for u in units if u.alive and hex_distance((u.row, u.col), (cr, cc)) <= radius]

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