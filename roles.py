"""
Role definitions for the game.

Each role belongs to a team ("AGENTS" or "MOLES"). Special roles add a
deception trick on top of the base role - things like being hidden from
your own team, or always lying to investigations about your allegiance.
"""

TEAM_AGENTS = "AGENTS"
TEAM_MOLES = "MOLES"


class Role:
    def __init__(self, name, team, description, is_special=False,
                 fake_investigation_result=None,
                 appears_as_mole_to_moles=False,
                 locks_team=False):
        self.name = name
        self.team = team
        self.description = description
        self.is_special = is_special

        # If set, any operation that investigates this player's loyalty
        # reports this team instead of their real one.
        self.fake_investigation_result = fake_investigation_result

        # If True, regular Moles are told this player is one of their
        # teammates during role reveal, even though their real team may
        # differ (used by Triple Agent).
        self.appears_as_mole_to_moles = appears_as_mole_to_moles

        # If True, operations that try to switch this player's team
        # have no effect on them.
        self.locks_team = locks_team

    def __repr__(self):
        return f"Role({self.name})"


# Base roles -----------------------------------------------------------

AGENT = Role(
    name="Agent",
    team=TEAM_AGENTS,
    description="You work for the Agency. Find the Moles before they "
                 "compromise the mission.",
)

MOLE = Role(
    name="Mole",
    team=TEAM_MOLES,
    description="You secretly work against the Agency. Blend in and "
                 "steer suspicion away from yourself and your fellow Moles.",
)

# Special roles ----------------------------------------------------------

ROGUE_AGENT = Role(
    name="Rogue Agent",
    team=TEAM_MOLES,
    description="You're a Mole, but a lone wolf. The other Moles don't "
                 "know you're one of them, and you don't know who they are.",
    is_special=True,
)

TRIPLE_AGENT = Role(
    name="Triple Agent",
    team=TEAM_AGENTS,
    description="You secretly work for the Agency, but the Moles believe "
                 "you're one of them and will treat you as a teammate.",
    is_special=True,
    appears_as_mole_to_moles=True,
    fake_investigation_result=TEAM_MOLES,
)

DEEP_COVER_AGENT = Role(
    name="Deep Cover Agent",
    team=TEAM_MOLES,
    description="Your cover is airtight. Any operation that investigates "
                 "your loyalty will report you as an innocent Agent.",
    is_special=True,
    fake_investigation_result=TEAM_AGENTS,
)

SUSPICIOUS_AGENT = Role(
    name="Suspicious Agent",
    team=TEAM_AGENTS,
    description="You have a shady past. Any operation that investigates "
                 "your loyalty will report you as a Mole, even though "
                 "you're not.",
    is_special=True,
    fake_investigation_result=TEAM_MOLES,
)

SERVICE_LOYALIST = Role(
    name="Service Loyalist",
    team=TEAM_AGENTS,
    description="You are unshakeably loyal to the Agency. Any operation "
                 "that tries to move you to the Moles' side simply fails.",
    is_special=True,
    locks_team=True,
)

VIRUS_LOYALIST = Role(
    name="Virus Loyalist",
    team=TEAM_MOLES,
    description="You are unshakeably loyal to the Moles. Any operation "
                 "that tries to move you to the Agency's side simply fails.",
    is_special=True,
    locks_team=True,
)

ALL_SPECIAL_ROLES = [
    ROGUE_AGENT, TRIPLE_AGENT, DEEP_COVER_AGENT,
    SUSPICIOUS_AGENT, SERVICE_LOYALIST, VIRUS_LOYALIST,
]


def build_role_deck(num_players, enabled_special_roles):
    """
    Build the list of Role objects to deal out for a game.

    num_players: total player count
    enabled_special_roles: list of Role objects (from ALL_SPECIAL_ROLES)
        the host has turned on
    """
    if num_players < 5:
        raise ValueError("Need at least 5 players")

    num_moles = max(1, num_players // 3)  # roughly 1/3 are moles
    num_agents = num_players - num_moles

    deck = []
    remaining_agent_slots = num_agents
    remaining_mole_slots = num_moles

    for role in enabled_special_roles:
        if role.team == TEAM_AGENTS and remaining_agent_slots > 0:
            deck.append(role)
            remaining_agent_slots -= 1
        elif role.team == TEAM_MOLES and remaining_mole_slots > 0:
            deck.append(role)
            remaining_mole_slots -= 1

    deck.extend([AGENT] * remaining_agent_slots)
    deck.extend([MOLE] * remaining_mole_slots)

    return deck
