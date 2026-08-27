"""
Operations are secret event cards dealt to each player during the
Operations Phase. Each one is a generator function so it can pause and
ask the active player (or, for a couple of operations, a second player)
for input before continuing.

Step types yielded by an operation generator:
    ("choose", prompt_text, [option_labels])
        Caller collects a choice from option_labels and resumes the
        generator with gen.send(choice).

    ("pass_and_choose", other_player_name, prompt_text, [option_labels])
        Same as "choose", but the device must first be handed to
        other_player_name before they make the choice.

    ("done", result_text)
        Final step. No further input needed; the operation is over
        once this is shown.
"""

import random

from game.roles import TEAM_AGENTS, TEAM_MOLES, AGENT, MOLE


def _team_label(team):
    return "Agency" if team == TEAM_AGENTS else "Moles"


# -- Hidden Agenda operations --------------------------------------------

def op_grudge(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one else here to hold a grudge against.")
        return
    target = random.choice(others)
    player.win_override = ("target_imprisoned", target.name)
    yield ("done", f"You've developed a grudge against {target.name}. "
                   f"From now on, you win only if {target.name} ends up "
                   f"imprisoned.")


def op_infatuation(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one around to fall for.")
        return
    target = random.choice(others)
    player.win_override = ("mirror", target.name)
    yield ("done", f"You've fallen for {target.name}. From now on, you "
                   f"win only if {target.name} wins.")


def op_scapegoat(gs, player):
    player.win_override = ("self_imprisoned", None)
    yield ("done", "You've received new orders from the top. From now "
                   "on, you win only if YOU are imprisoned this round - "
                   "regardless of which team you're on.")


# -- Info operations ------------------------------------------------------

def op_confession(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one else here to confess to.")
        return
    names = [p.name for p in others]
    choice = yield ("choose",
                     "Pick exactly one other agent. You must honestly "
                     "reveal your true team to them, and only them.",
                     names)
    yield ("done", f"Show this line to {choice} only, then hide the "
                   f"screen again:\n\nYou work for the "
                   f"{_team_label(player.role.team)}.")


def op_secret_intel(gs, player):
    others = gs.other_active_players(player)
    if len(others) < 2:
        yield ("done", "There aren't enough other players for an intel "
                       "check.")
        return
    names = [p.name for p in others]
    first = yield ("choose", "Choose the first agent to investigate.", names)
    remaining = [n for n in names if n != first]
    second = yield ("choose", "Choose the second agent to investigate.",
                     remaining)
    t1 = gs._find_player(first).reported_team()
    t2 = gs._find_player(second).reported_team()
    is_mole = (t1 == TEAM_MOLES) or (t2 == TEAM_MOLES)
    verdict = ("At least one of them is a Mole." if is_mole
               else "Neither of them is a Mole.")
    yield ("done", f"Intel on {first} and {second}:\n{verdict}")


def op_secret_tip(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "Your source has nothing for you this time.")
        return
    target = random.choice(others)
    label = ("a Mole" if target.reported_team() == TEAM_MOLES
              else "not a Mole")
    yield ("done", f"Your source tells you: {target.name} is {label}.")


def op_anonymous_tip(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "The call drops before your source can say "
                       "anything useful.")
        return
    target = random.choice(others)
    label = ("a Mole" if target.reported_team() == TEAM_MOLES
              else "not a Mole")
    yield ("done", f"An anonymous caller tells you: {target.name} is "
                   f"{label}.")


def op_old_photographs(gs, player):
    by_team = {}
    for p in gs.players:
        by_team.setdefault(p.role.team, []).append(p.name)
    same_team_groups = [names for names in by_team.values() if len(names) >= 2]
    if not same_team_groups:
        yield ("done", "The photographs are too blurry to make anything "
                       "out.")
        return
    group = random.choice(same_team_groups)
    pair = random.sample(group, 2)
    yield ("done", f"Old photographs show {pair[0]} and {pair[1]} started "
                   f"this mission on the same team.")


def op_danish_intelligence(gs, player):
    others = gs.other_active_players(player)
    moles = [p for p in others if p.role.team == TEAM_MOLES]
    agents = [p for p in others if p.role.team == TEAM_AGENTS]
    if not moles or not agents:
        yield ("done", "The transmission is too garbled to make out any "
                       "names.")
        return
    m = random.choice(moles)
    a = random.choice(agents)
    names = [m.name, a.name]
    random.shuffle(names)
    yield ("done", f"Intercepted transmission names {names[0]} and "
                   f"{names[1]}. One of them is a Mole, the other isn't - "
                   f"but it doesn't say which.")


def op_unfortunate_encounter(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "You don't run into anyone.")
        return
    names = [p.name for p in others]
    choice = yield ("choose",
                     "Pick one agent. You'll both quietly learn whether "
                     "either of you is a Mole.",
                     names)
    target = gs._find_player(choice)
    is_mole = (player.reported_team() == TEAM_MOLES
               or target.reported_team() == TEAM_MOLES)
    verdict = ("At least one of you is a Mole." if is_mole
               else "Neither of you is a Mole.")
    yield ("done", f"You and {choice} compare notes:\n{verdict}\n\n(Show "
                   f"this result to {choice} as well before moving on.)")


# -- Team-shift operations --------------------------------------------

def op_sleeper_agent(gs, player):
    if player.role.locks_team:
        yield ("done", "Your unshakeable loyalty cancels this operation. "
                       "Nothing happens.")
        return
    new_team = TEAM_MOLES if player.role.team == TEAM_AGENTS else TEAM_AGENTS
    player.role = AGENT if new_team == TEAM_AGENTS else MOLE
    yield ("done", "Turns out you were secretly working for the other "
                   f"side all along. You now work for the "
                   f"{_team_label(player.role.team)}.")


def op_defector(gs, player):
    if player.role.locks_team:
        yield ("done", "Your unshakeable loyalty cancels this operation. "
                       "Nothing happens.")
        return
    choice = yield ("choose",
                     "You may defect and join the other side. Defecting "
                     "costs you your vote this round.",
                     ["Defect", "Stay the same"])
    if choice == "Defect":
        new_team = TEAM_MOLES if player.role.team == TEAM_AGENTS else TEAM_AGENTS
        player.role = AGENT if new_team == TEAM_AGENTS else MOLE
        player.cannot_vote = True
        yield ("done", f"You've defected. You now work for the "
                       f"{_team_label(player.role.team)}, but you can't "
                       f"vote this round.")
    else:
        yield ("done", "You chose to stay exactly where you are.")


def op_deep_undercover(gs, player):
    if player.role.locks_team:
        yield ("done", "Your unshakeable loyalty cancels this operation. "
                       "Nothing happens.")
        return
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one else to investigate.")
        return
    names = [p.name for p in others]
    choice = yield ("choose",
                     "Pick one agent to secretly investigate. If they "
                     "turn out to be a Mole, you'll join their side.",
                     names)
    target = gs._find_player(choice)
    if target.reported_team() == TEAM_MOLES:
        player.role = MOLE
        yield ("done", f"{choice} turns out to be a Mole. You've joined "
                       f"their cause and now work for the Moles.")
    else:
        yield ("done", f"{choice} checks out clean. You remain exactly "
                       f"where you were.")


def op_spy_transfer(gs, player):
    if player.role.locks_team:
        yield ("done", "Your unshakeable loyalty cancels this operation. "
                       "Nothing happens.")
        return
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one else to swap with.")
        return
    names = [p.name for p in others]
    choice = yield ("choose",
                     "Pick one agent to secretly swap teams with.",
                     names)
    target = gs._find_player(choice)
    if target.role.locks_team:
        yield ("done", f"{choice}'s loyalty can't be shaken. The swap "
                       f"fails.")
        return
    player_team, target_team = player.role.team, target.role.team
    player.role = AGENT if target_team == TEAM_AGENTS else MOLE
    target.role = AGENT if player_team == TEAM_AGENTS else MOLE
    yield ("done", f"You and {choice} have secretly swapped teams. You "
                   f"now work for the {_team_label(player.role.team)}.")


# -- Vote operations --------------------------------------------------

def op_incriminating_evidence(gs, player):
    others = gs.other_active_players(player)
    if not others:
        yield ("done", "There's no one to hand this evidence to.")
        return
    names = [p.name for p in others]
    choice = yield ("choose",
                     "Pick one other agent to hand this evidence to.",
                     names)
    decision = yield ("pass_and_choose", choice,
                       f"{choice}: you've been handed evidence about "
                       f"{player.name}. Choose what to do with it.",
                       ["Shield them from a vote",
                        "Add a vote against them"])
    if decision == "Shield them from a vote":
        player.vote_shield = True
        yield ("done", f"{choice} chose to shield {player.name} from a "
                       f"vote this round.")
    else:
        player.extra_votes_against += 1
        yield ("done", f"{choice} chose to add a vote against "
                       f"{player.name} this round.")


# -- Registry -----------------------------------------------------------

OPERATIONS = [
    ("grudge", "Grudge", "Hidden Agenda", op_grudge),
    ("infatuation", "Infatuation", "Hidden Agenda", op_infatuation),
    ("scapegoat", "Operation: Scapegoat", "Hidden Agenda", op_scapegoat),
    ("confession", "Confession", "Info", op_confession),
    ("secret_intel", "Secret Intel", "Info", op_secret_intel),
    ("secret_tip", "Secret Tip", "Info", op_secret_tip),
    ("anonymous_tip", "Anonymous Tip", "Info", op_anonymous_tip),
    ("old_photographs", "Old Photographs", "Info", op_old_photographs),
    ("danish_intelligence", "Danish Intelligence", "Info", op_danish_intelligence),
    ("unfortunate_encounter", "Unfortunate Encounter", "Info", op_unfortunate_encounter),
    ("sleeper_agent", "Sleeper Agent", "Team Shift", op_sleeper_agent),
    ("defector", "Defector", "Team Shift", op_defector),
    ("deep_undercover", "Deep Undercover", "Team Shift", op_deep_undercover),
    ("spy_transfer", "Spy Transfer", "Team Shift", op_spy_transfer),
    ("incriminating_evidence", "Incriminating Evidence", "Vote", op_incriminating_evidence),
]

OPERATIONS_BY_ID = {op_id: (name, category, func) for op_id, name, category, func in OPERATIONS}

PRESETS = {
    "Beginner Game": ["confession", "secret_tip", "anonymous_tip"],
    "Full Game": [op_id for op_id, _, _, _ in OPERATIONS],
    "No Swaps": [op_id for op_id, _, cat, _ in OPERATIONS if cat != "Team Shift"],
    "No Hidden Agendas": [op_id for op_id, _, cat, _ in OPERATIONS if cat != "Hidden Agenda"],
}


def random_operation_id(enabled_ids):
    if not enabled_ids:
        return None
    return random.choice(enabled_ids)


def start_operation(operation_id, game_state, player):
    """Create and start a generator for the given operation id.
    Returns (generator, first_step)."""
    _, _, func = OPERATIONS_BY_ID[operation_id]
    gen = func(game_state, player)
    first_step = gen.send(None)
    return gen, first_step
