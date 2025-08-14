import pygame
import math

BOARD_ROWS = 8
BOARD_COLS = 5
HEX_SIZE = 40
WIDTH = 1200
HEIGHT = 1000
BG_colour = (30, 30, 30)

PLAYER_COLOURS = {
    "Greedy": (70, 130, 255),
    "Efficient": (60, 200, 60),
    "ComboSeeker": (255, 220, 60),
    "Random": (220, 60, 60),
}

def hex_to_pixel(row, col, size=HEX_SIZE):
    x = size * (math.sqrt(3) * col + (math.sqrt(3) / 2) * (1 - (row % 2)))
    y = size * (3 / 2 * row)
    return int(x + 60), int(y + 60)

def draw_hex(surface, x, y, size, colour, width=2):
    points = []
    for i in range(6):
        angle = math.pi / 3 * i - math.pi / 6  # rotate -30 degrees
        px = x + size * math.cos(angle)
        py = y + size * math.sin(angle)
        points.append((px, py))
    pygame.draw.polygon(surface, colour, points, width)

def draw_arrow(surface, start, end, colour=(255,255,255), width=3):
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    # Offset so arrow starts/ends at edge of troop circles
    offset = HEX_SIZE // 2
    sx += dx * offset / dist
    sy += dy * offset / dist
    ex -= dx * offset / dist
    ey -= dy * offset / dist
    pygame.draw.line(surface, colour, (sx, sy), (ex, ey), width)
    # Draw arrowhead
    angle = math.atan2(ey - sy, ex - sx)
    length = 15
    for side in (-1, 1):
        x = ex - length * math.cos(angle + side * math.pi / 6)
        y = ey - length * math.sin(angle + side * math.pi / 6)
        pygame.draw.line(surface, colour, (ex, ey), (x, y), width)

def draw_grid(surface, grid, units=None):
    # Create fonts for drawing unit names and HP text
    font = pygame.font.SysFont(None, 20, bold=True)
    hp_font = pygame.font.SysFont(None, 18, bold=True)
    coord_font = pygame.font.SysFont(None, 14)  # Smaller font for coordinates

    # Build a lookup dictionary for units' current HP keyed by their grid position
    unit_hp_lookup = {}
    if units:
        for u in units:
            if u.alive:
                unit_hp_lookup[(u.row, u.col)] = u.current_hp

    for r in range(BOARD_ROWS):
        for c in range(BOARD_COLS):
            x, y = hex_to_pixel(r, c)

            draw_hex(surface, x, y, HEX_SIZE, (80, 80, 80))

            coord_text = coord_font.render(f"{r},{c}", True, (150, 150, 150))
            coord_rect = coord_text.get_rect(center=(x, y - HEX_SIZE // 2 + 10))
            surface.blit(coord_text, coord_rect)

            cell = grid[r][c]
            if cell:
                unit = cell
                card = unit.card
                owner = unit.owner
                colour = PLAYER_COLOURS.get(owner.name, (200, 200, 200))

                cx, cy = x, y

                # --- INVIS EFFECT ---
                if getattr(unit, "invisible", False):
                    ghost_colour = (colour[0], colour[1], colour[2], 120)  # semi-transparent
                    ghost_surface = pygame.Surface((HEX_SIZE, HEX_SIZE), pygame.SRCALPHA)
                    pygame.draw.circle(ghost_surface, ghost_colour, (HEX_SIZE//2, HEX_SIZE//2), HEX_SIZE//2)
                    surface.blit(ghost_surface, (cx - HEX_SIZE//2, cy - HEX_SIZE//2))

                    # Glow outline
                    pygame.draw.circle(surface, (180, 220, 255), (int(cx), int(cy)), HEX_SIZE // 2, 2)

                    # Skip name/HP if you want invisibility to hide details
                    continue

                # Draw visible unit
                pygame.draw.circle(surface, colour, (int(cx), int(cy)), HEX_SIZE // 2)

                # --- STUNNED EFFECT ---
                if hasattr(unit, 'status_effects') and 'stunned' in unit.status_effects:
                    # Draw red circle outline to indicate stunned
                    pygame.draw.circle(surface, (255, 0, 255), (int(cx), int(cy)), HEX_SIZE // 2, 3)

                # Draw name (wrapped every 8 chars)
                name = card.name
                name_lines = [name[i:i+8] for i in range(0, len(name), 8)]
                for i, line in enumerate(name_lines):
                    text = font.render(line, True, (0, 0, 0))
                    rect = text.get_rect(center=(cx, cy + i*18 - (len(name_lines)-1)*9))
                    surface.blit(text, rect)

                # Draw HP
                hp = unit_hp_lookup.get((r, c), getattr(card, "health", 1))
                hp_text = hp_font.render(str(hp), True, (255, 255, 255))
                hp_rect = hp_text.get_rect(center=(cx, cy - HEX_SIZE // 2 - 10))
                surface.blit(hp_text, hp_rect)
