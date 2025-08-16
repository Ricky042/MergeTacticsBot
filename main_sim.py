# --- Standard Libraries ---
import random

# --- Pygame ---
import pygame

# --- Globals / Shared State ---
from merge_sim.constants import BOARD_ROWS, BOARD_COLS, bombs, rn

# --- Cards ---
from merge_sim.cards import (
    Card,
    CARD_STATS
)

# --- Modifiers / Synergies ---
from merge_sim.modifiers import (
    ClanSynergyManager,
    BrawlerSynergyManager,
    NobleSynergyManager,
    GoblinSynergyManager
)

# --- Visualisation / Graphics ---
from merge_sim.visualise import draw_grid, hex_to_pixel, PLAYER_COLOURS

# --- Combat / Player Units ---
from merge_sim.combat_unit import spawn_skeleton
from merge_sim.player import Player

# --- Board / Hex Utilities ---
from merge_sim.board_utils import (
    get_occupied_positions,
    combine_grids,
    print_combined_grid
)
from merge_sim.hex_utils import (
    hex_neighbors,
    hex_distance,
    find_path_bfs_to_range,
)

# --- Projectiles ---
from merge_sim.projectile import Projectile

# --- Bots ---
from merge_sim.player import get_player_colour
from merge_sim.bot import *


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
    
    p1.clan_manager = ClanSynergyManager(p1)  # pass all units on the board
    p2.clan_manager = ClanSynergyManager(p2)  # pass all units on the board
    p1.clan_manager.setup_round()  # counts Clan cards at start of round
    p2.clan_manager.setup_round()  # counts Clan cards at start of round
    p1.brawler_manager = BrawlerSynergyManager(p1)
    p2.brawler_manager = BrawlerSynergyManager(p2)
    p1.brawler_manager.setup_round()
    p2.brawler_manager.setup_round()
    p1.noble_manager = NobleSynergyManager(p1, False)
    p2.noble_manager = NobleSynergyManager(p2, True)
    p1.noble_manager.setup_round()
    p2.noble_manager.setup_round()
    p1.goblin_manager = GoblinSynergyManager(p1)
    p2.goblin_manager = GoblinSynergyManager(p2)
    p1.goblin_manager.setup_round()
    p2.goblin_manager.setup_round()
    
    # --- CLEAR ANY EXISTING BOMBS AT ROUND START ---
    bombs.clear()

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

            # ✅ Clan synergy check  
            unit.owner.clan_manager.trigger(unit)

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

            # --- inside the main loop, after unit actions ---
            for bomb in bombs[:]:  # iterate over a copy
                bomb["timer"] -= dt  # dt = time step per frame

                # Print countdown (rounded to 2 decimals for readability)
                print(f"⏳ Bomb at {bomb['pos']} exploding in {bomb['timer']:.2f}s")

                if bomb["timer"] <= 0:
                    # Trigger explosion
                    bomb_pos = bomb["pos"]
                    radius = bomb["radius"]
                    damage = bomb["damage"]
                    stun_duration = bomb["stun"]

                    for unit in units:
                        if unit.alive and unit.owner != bomb["owner"] and hex_distance(unit.get_position(), bomb_pos) <= radius:
                            unit.take_damage(damage, combined, units)
                            unit.status_effects["stunned"] = max(unit.status_effects.get("stunned", 0), stun_duration)
                            print(f"💥 Bomb hits {unit.card.name} (Owner: {unit.owner.name}) for {damage} damage and {stun_duration}s stun!")


                    bombs.remove(bomb)
       

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

    p1.goblin_manager.on_buy_phase_start(rn)
    p2.goblin_manager.on_buy_phase_start(rn) 
    pygame.quit()
    return [], winner, remaining_units

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

    rn = 1
    round_num = 1
    while round_num <= 10:  # Max 10 rounds
        if not play_round(players, round_num):
            break
        round_num += 1
        rn += 1
    
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