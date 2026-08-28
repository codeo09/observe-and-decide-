"""
Entry point for the app.

Screen flow:
    SetupScreen -> RoleRevealScreen (looped per player) -> OperationsScreen
    (looped per player, each op is a mini pass-around) -> DiscussionScreen
    (with a History log) -> VotingScreen (secret pass-around vote) ->
    ResultScreen -> back to SetupScreen
"""

from kivy.clock import Clock
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivymd.app import MDApp
from kivymd.uix.list import OneLineAvatarIconListItem, OneLineListItem
from kivymd.uix.button import MDRaisedButton

from game.game_state import GameState
from game.roles import ALL_SPECIAL_ROLES
from game.operations import (
    OPERATIONS_BY_ID, PRESETS, random_operation_id, start_operation,
)

MIN_PLAYERS = 5
MAX_PLAYERS = 20
DEFAULT_DISCUSSION_SECONDS = 120
PRESET_NAMES = ["Off", "Beginner Game", "Full Game", "No Swaps", "No Hidden Agendas"]


class SetupScreen(Screen):
    player_count_text = StringProperty(str(MIN_PLAYERS))
    selected_preset = StringProperty("Full Game")

    def on_pre_enter(self):
        self.refresh_name_fields()

    def refresh_name_fields(self):
        container = self.ids.name_fields_box
        container.clear_widgets()
        try:
            count = int(self.player_count_text)
        except ValueError:
            count = MIN_PLAYERS
        count = max(MIN_PLAYERS, min(MAX_PLAYERS, count))

        from kivymd.uix.textfield import MDTextField
        self.name_inputs = []
        for i in range(count):
            field = MDTextField(
                hint_text=f"Player {i + 1} name",
                text=f"Player {i + 1}",
            )
            container.add_widget(field)
            self.name_inputs.append(field)

    def change_player_count(self, delta):
        try:
            count = int(self.player_count_text)
        except ValueError:
            count = MIN_PLAYERS
        count = max(MIN_PLAYERS, min(MAX_PLAYERS, count + delta))
        self.player_count_text = str(count)
        self.refresh_name_fields()

    def select_preset(self, name):
        self.selected_preset = name

    def start_game(self):
        app = MDApp.get_running_app()
        names = [field.text.strip() or f"Player {i+1}"
                 for i, field in enumerate(self.name_inputs)]

        enabled_roles = []
        for role in ALL_SPECIAL_ROLES:
            checkbox_id = f"role_{role.name.replace(' ', '_')}"
            if checkbox_id in self.ids and self.ids[checkbox_id].active:
                enabled_roles.append(role)

        try:
            discussion_seconds = int(self.ids.timer_input.text)
        except (ValueError, KeyError):
            discussion_seconds = DEFAULT_DISCUSSION_SECONDS

        if self.selected_preset == "Off":
            enabled_operation_ids = []
        else:
            enabled_operation_ids = PRESETS.get(self.selected_preset, [])

        app.game_state.start_new_game(
            names, enabled_roles, discussion_seconds, enabled_operation_ids
        )
        app.root.current = "reveal"


class RoleRevealScreen(Screen):
    current_player_name = StringProperty("")
    role_visible = BooleanProperty(False)
    role_name_text = StringProperty("")
    role_desc_text = StringProperty("")
    team_text = StringProperty("")
    teammates_text = StringProperty("")

    def on_pre_enter(self):
        self.role_visible = False
        self.show_next_player()

    def show_next_player(self):
        app = MDApp.get_running_app()
        player = app.game_state.next_unrevealed_player()
        if player is None:
            app.root.current = "operations"
            return
        self.current_player_name = player.name
        self.role_name_text = player.role.name
        self.role_desc_text = player.role.description
        self.team_text = player.role.team

        teammates = app.game_state.teammates_of(player)
        if teammates:
            self.teammates_text = "Fellow Moles: " + ", ".join(teammates)
        else:
            self.teammates_text = ""

        self.role_visible = False

    def reveal_role(self):
        self.role_visible = True

    def confirm_and_pass(self):
        app = MDApp.get_running_app()
        player = app.game_state.next_unrevealed_player()
        if player:
            player.has_seen_role = True
        self.role_visible = False
        self.show_next_player()


class OperationsScreen(Screen):
    """
    Walks every active player through one random Operation each.
    phase is one of:
      "pass"    - "pass the device to X" confirmation
      "choose"  - showing a list of choice buttons
      "pass2"   - "pass the device to Y" confirmation for a second player
                  (used by operations like Incriminating Evidence)
      "done"    - showing the private result text
      "none"    - no operations are enabled at all; just a skip button
    """
    phase = StringProperty("pass")
    pass_target_name = StringProperty("")
    prompt_text = StringProperty("")
    done_text = StringProperty("")
    operation_title_text = StringProperty("")

    def on_pre_enter(self):
        self._gen = None
        self._current_player = None
        self._op_id = None
        self._op_name = None
        self.show_next_player_operation()

    def show_next_player_operation(self):
        app = MDApp.get_running_app()
        gs = app.game_state
        player = gs.next_operation_player()
        if player is None:
            app.root.current = "discussion"
            return

        if not gs.enabled_operation_ids:
            player.has_had_operation = True
            self.phase = "none"
            self.pass_target_name = player.name
            return

        op_id = random_operation_id(gs.enabled_operation_ids)
        self._current_player = player
        self._op_id = op_id
        self._op_name = OPERATIONS_BY_ID[op_id][0]
        self.operation_title_text = self._op_name
        self.phase = "pass"
        self.pass_target_name = player.name

    def confirm_pass(self):
        app = MDApp.get_running_app()
        gen, step = start_operation(self._op_id, app.game_state, self._current_player)
        self._gen = gen
        self._handle_step(step)

    def skip_no_operations(self):
        self.show_next_player_operation()

    def _handle_step(self, step):
        kind = step[0]
        if kind == "done":
            self.phase = "done"
            self.done_text = step[1]
        elif kind == "choose":
            _, prompt, options = step
            self.phase = "choose"
            self.prompt_text = prompt
            self._build_choice_buttons(options)
        elif kind == "pass_and_choose":
            _, other_name, prompt, options = step
            self._pending_prompt = prompt
            self._pending_options = options
            self.phase = "pass2"
            self.pass_target_name = other_name

    def confirm_pass2(self):
        self.phase = "choose"
        self.prompt_text = self._pending_prompt
        self._build_choice_buttons(self._pending_options)

    def _build_choice_buttons(self, options):
        box = self.ids.choice_box
        box.clear_widgets()
        for option in options:
            btn = MDRaisedButton(
                text=option,
                md_bg_color=(0.8, 0.1, 0.1, 1),
                size_hint_x=1,
            )
            btn.bind(on_release=lambda instance, o=option: self.make_choice(o))
            box.add_widget(btn)

    def make_choice(self, choice):
        step = self._gen.send(choice)
        self._handle_step(step)

    def finish_operation(self):
        app = MDApp.get_running_app()
        app.game_state.record_operation(self._op_name, self._current_player.name)
        self._current_player.has_had_operation = True
        self.show_next_player_operation()


class HistoryScreen(Screen):
    def on_pre_enter(self):
        app = MDApp.get_running_app()
        box = self.ids.history_box
        box.clear_widgets()
        history = app.game_state.operation_history
        if not history:
            box.add_widget(OneLineListItem(text="No operations happened this round."))
            return
        for i, (op_name, player_name) in enumerate(history, start=1):
            box.add_widget(OneLineListItem(text=f"{i}. {op_name} - {player_name}"))

    def go_back(self):
        app = MDApp.get_running_app()
        app.root.current = "discussion"


class DiscussionScreen(Screen):
    time_left_text = StringProperty("")
    _seconds_remaining = NumericProperty(0)
    _timer_event = None

    def on_pre_enter(self):
        app = MDApp.get_running_app()
        self._seconds_remaining = app.game_state.discussion_seconds
        self._update_label()
        self._timer_event = Clock.schedule_interval(self._tick, 1)

    def on_leave(self):
        if self._timer_event:
            self._timer_event.cancel()
            self._timer_event = None

    def _tick(self, dt):
        self._seconds_remaining -= 1
        self._update_label()
        if self._seconds_remaining <= 0:
            self.go_to_vote()

    def _update_label(self):
        minutes = max(0, self._seconds_remaining) // 60
        seconds = max(0, self._seconds_remaining) % 60
        self.time_left_text = f"{minutes:02d}:{seconds:02d}"

    def view_history(self):
        app = MDApp.get_running_app()
        app.root.current = "history"

    def go_to_vote(self):
        if self._timer_event:
            self._timer_event.cancel()
            self._timer_event = None
        app = MDApp.get_running_app()
        app.root.current = "voting"


class VotingScreen(Screen):
    current_voter_name = StringProperty("")
    voter_ready = BooleanProperty(False)

    def on_pre_enter(self):
        app = MDApp.get_running_app()
        app.game_state.start_voting()
        self.voter_ready = False
        self.show_next_voter()

    def show_next_voter(self):
        app = MDApp.get_running_app()
        voter = app.game_state.next_voter()
        if voter is None:
            self._finish_voting()
            return
        self.current_voter_name = voter.name
        self.voter_ready = False

    def confirm_identity(self):
        self.voter_ready = True
        app = MDApp.get_running_app()
        vote_list = self.ids.vote_list
        vote_list.clear_widgets()
        for player in app.game_state.active_players():
    if player.name == self.current_voter_name:
        continue

    item = OneLineAvatarIconListItem(text=player.name)
    item.bind(on_release=lambda instance, name=player.name: self.cast_vote(name))
    vote_list.add_widget(item)

    def cast_vote(self, target_name):
        app = MDApp.get_running_app()
        app.game_state.cast_vote(self.current_voter_name, target_name)
        self.voter_ready = False
        self.show_next_voter()

    def _finish_voting(self):
        app = MDApp.get_running_app()
        imprisoned_name, results = app.game_state.resolve_vote()

        result_screen = app.root.get_screen("result")
        if imprisoned_name:
            result_screen.imprisoned_text = f"{imprisoned_name} was imprisoned."
        else:
            result_screen.imprisoned_text = "Nobody was imprisoned."

        winners = [name for name, outcome in results if outcome == "WINNER"]
        losers = [name for name, outcome in results if outcome == "LOSER"]
        result_screen.winners_text = ", ".join(winners) if winners else "No one"
        result_screen.losers_text = ", ".join(losers) if losers else "No one"

        app.root.current = "result"


class ResultScreen(Screen):
    imprisoned_text = StringProperty("")
    winners_text = StringProperty("")
    losers_text = StringProperty("")

    def play_again(self):
        app = MDApp.get_running_app()
        app.root.current = "setup"


class SpyGameApp(MDApp):
    def build(self):
        self.game_state = GameState()
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Red"
        self.theme_cls.accent_palette = "Amber"

        sm = ScreenManager()
        sm.add_widget(SetupScreen(name="setup"))
        sm.add_widget(RoleRevealScreen(name="reveal"))
        sm.add_widget(OperationsScreen(name="operations"))
        sm.add_widget(HistoryScreen(name="history"))
        sm.add_widget(DiscussionScreen(name="discussion"))
        sm.add_widget(VotingScreen(name="voting"))
        sm.add_widget(ResultScreen(name="result"))
        return sm


if __name__ == "__main__":
    SpyGameApp().run()
