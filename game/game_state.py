"""
Holds the state for a single game: players, their assigned roles,
operation history, and the pass-around reveal/vote flow.
"""

import random

from game.roles import build_role_deck, TEAM_AGENTS, TEAM_MOLES


class Player:
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.has_seen_role = False
        self.is_imprisoned = False

        # Set by a Hidden Agenda operation. A tuple like:
        #   ("target_imprisoned", target_name)
        #   ("mirror", target_name)
        #   ("self_imprisoned", None)
        # None means "just use your role's team to decide win/lose".
        self.win_override = None

        # Set by operations that add/remove votes against this player
        # during the Incriminating Evidence operation.
        self.extra_votes_against = 0
        self.vote_shield = False

        self.has_had_operation = False
        self.cannot_vote = False

    def reported_team(self):
        """The team investigations report for this player (may be a lie)."""
        if self.role.fake_investigation_result is not None:
            return self.role.fake_investigation_result
        return self.role.team


class GameState:
    def __init__(self):
        self.players = []
        self.discussion_seconds = 120
        self.votes = {}
        self.enabled_operation_ids = []
        self.operation_history = []  # list of (operation_name, player_name)

    def start_new_game(self, player_names, enabled_special_roles,
                        discussion_seconds, enabled_operation_ids):
        deck = build_role_deck(len(player_names), enabled_special_roles)
        random.shuffle(deck)

        self.players = [
            Player(name, role) for name, role in zip(player_names, deck)
        ]
        self.discussion_seconds = discussion_seconds
        self.enabled_operation_ids = list(enabled_operation_ids)
        self.votes = {}
        self.operation_history = []

    # -- Role reveal ------------------------------------------------

    def next_unrevealed_player(self):
        for player in self.players:
            if not player.has_seen_role:
                return player
        return None

    def all_roles_revealed(self):
        return all(p.has_seen_role for p in self.players)

    def teammates_of(self, player):
        """
        Names of the player's fellow Moles, shown to regular Moles so
        they know who else is on their team. Rogue Agents are hidden
        even from other Moles. A Triple Agent is an Agent, but shows up
        on this list because the Moles have been fooled into trusting
        them.
        """
        if player.role.name == "Rogue Agent":
            return []
        if player.role.team != TEAM_MOLES:
            return []

        names = []
        for p in self.players:
            if p is player:
                continue
            if p.role.name == "Rogue Agent":
                continue
            if p.role.team == TEAM_MOLES or p.role.appears_as_mole_to_moles:
                names.append(p.name)
        return names

    # -- Operations ---------------------------------------------------

    def next_operation_player(self):
        for player in self.active_players():
            if not player.has_had_operation:
                return player
        return None

    def all_operations_done(self):
        return all(p.has_had_operation for p in self.active_players())

    def record_operation(self, operation_name, player_name):
        self.operation_history.append((operation_name, player_name))

    # -- Voting ---------------------------------------------------------

    def start_voting(self):
        self.votes = {}

    def voters(self):
        return [p for p in self.active_players() if not p.cannot_vote]

    def next_voter(self):
        for player in self.voters():
            if player.name not in self.votes:
                return player
        return None

    def cast_vote(self, voter_name, target_name):
        if voter_name == target_name:
           return False

        self.votes[voter_name] = target_name
        return True
    def all_voted(self):
        return len(self.votes) == len(self.voters())

    def tally_votes(self):
        """Return dict of target_name -> vote count, including operation
        effects (Incriminating Evidence extra votes / shields)."""
        counts = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1

        for p in self.active_players():
            if p.extra_votes_against:
                counts[p.name] = counts.get(p.name, 0) + p.extra_votes_against
            if p.vote_shield and p.name in counts:
                counts[p.name] = max(0, counts[p.name] - 1)

        return counts

    def resolve_vote(self):
        """
        Tally votes, imprison whoever has the most (ties = no one is
        imprisoned), then work out everyone's personal win/lose result.
        Returns (imprisoned_name_or_None, results_list) where
        results_list is a list of (player_name, "WINNER"/"LOSER").
        """
        counts = self.tally_votes()
        imprisoned_name = None

        if counts:
            max_votes = max(counts.values())
            top_targets = [name for name, c in counts.items() if c == max_votes]
            if len(top_targets) == 1 and max_votes > 0:
                imprisoned_name = top_targets[0]
                self.imprison(imprisoned_name)

        base_winning_team = self._base_winning_team()
        results = self._compute_personal_results(base_winning_team)
        return imprisoned_name, results

    def imprison(self, player_name):
        for p in self.players:
            if p.name == player_name:
                p.is_imprisoned = True

    def _base_winning_team(self):
        imprisoned = [p for p in self.players if p.is_imprisoned]
        if any(p.role.team == TEAM_MOLES for p in imprisoned):
            return TEAM_AGENTS
        return TEAM_MOLES

    def _player_base_outcome(self, player, base_winning_team):
        return "WINNER" if player.role.team == base_winning_team else "LOSER"

        def _compute_personal_results(self, base_winning_team):
        results = []
        for p in self.players:
            outcome = self._resolve_player_outcome(p, base_winning_team)
            reason = self._player_outcome_reason(p, base_winning_team, outcome)
            results.append((p.name, outcome, reason))
        return results

    def _player_outcome_reason(self, player, base_winning_team, outcome):
        """Explain why this player won or lost."""

        override = player.win_override

        # Normal Agent / Mole result
        if override is None:
            if base_winning_team == TEAM_AGENTS:
                if outcome == "WINNER":
                    return "A Mole was imprisoned, so the Agency won."
                return "A Mole was imprisoned, so the Moles lost."
            else:
                if outcome == "WINNER":
                    return "No Mole was imprisoned, so the Moles won."
                return "No Mole was imprisoned, so the Agency lost."

        kind = override[0]

        # Scapegoat
        if kind == "self_imprisoned":
            if outcome == "WINNER":
                return "You were imprisoned, which was your special objective."
            return "You were not imprisoned, so your special objective failed."

        # Grudge
        if kind == "target_imprisoned":
            target_name = override[1]
            target = self._find_player(target_name)

            if target is not None and target.is_imprisoned:
                return f"Your grudge target, {target_name}, was imprisoned."
            return f"Your grudge target, {target_name}, was not imprisoned."

        # Infatuation
        if kind == "mirror":
            target_name = override[1]
            target = self._find_player(target_name)

            if target is None:
                return "Your target could not be found, so your normal team result was used."

            target_base_outcome = self._player_base_outcome(
                target, base_winning_team
            )

            if target_base_outcome == "WINNER":
                return f"Your target, {target_name}, was on the winning team."
            return f"Your target, {target_name}, was on the losing team."

        # Fallback
        if outcome == "WINNER":
            return "You were on the winning team."
        return "You were on the losing team."
    def _resolve_player_outcome(self, player, base_winning_team):
        override = player.win_override
        if override is None:
            return self._player_base_outcome(player, base_winning_team)

        kind = override[0]
        if kind == "self_imprisoned":
            return "WINNER" if player.is_imprisoned else "LOSER"
        if kind == "target_imprisoned":
            target_name = override[1]
            target = self._find_player(target_name)
            if target is not None and target.is_imprisoned:
                return "WINNER"
            return "LOSER"
        if kind == "mirror":
            target_name = override[1]
            target = self._find_player(target_name)
            if target is None:
                return self._player_base_outcome(player, base_winning_team)
            # Use the target's own base-team outcome to avoid recursion.
            return self._player_base_outcome(target, base_winning_team)

        return self._player_base_outcome(player, base_winning_team)

    def _find_player(self, name):
        for p in self.players:
            if p.name == name:
                return p
        return None

    def active_players(self):
        return [p for p in self.players if not p.is_imprisoned]

    def other_active_players(self, player):
        return [p for p in self.active_players() if p is not player]
