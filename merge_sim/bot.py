import random

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
