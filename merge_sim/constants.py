# Board dimensions
BOARD_ROWS = 8
BOARD_COLS = 5

# Combat constants
CRIT_CHANCE = 0.15
CRIT_MULTIPLIER = 1.5

# Shared dynamic state
bombs = []                 # Active bombs in combat
reserved_positions = set() # Positions reserved for movement/spawns
rn = 0          # Current round number
