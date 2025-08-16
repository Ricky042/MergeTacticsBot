# --- Standard Libraries ---
from collections import deque

# --- Globals / Shared State ---
from .constants import BOARD_ROWS, BOARD_COLS

# --- Cards ---
from .cards import (
    Card
)

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