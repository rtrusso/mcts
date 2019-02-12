from __future__ import division

import time
from math import log, sqrt
from random import choice


class Stat(object):
    __slots__ = ('value', 'visits')

    def __init__(self, value=0.0, visits=0):
        self.value = value
        self.visits = visits

    def __repr__(self):
        return u"Stat(value={}, visits={})".format(self.value, self.visits)


class UCT(object):
    def __init__(self, board, **kwargs):
        self.board = board
        self.history = []
        self.stats = {}

        self.max_depth = 0
        self.data = {}

        self.calculation_time = float(kwargs.get('time', 30))
        self.max_actions = int(kwargs.get('max_actions', 1000))

        # Exploration constant, increase for more exploratory actions,
        # decrease to prefer actions with known higher win rates.
        self.C = float(kwargs.get('C', 1.4))

    def update(self, state):
        self.history.append(self.board.to_compact_state(state))

    def display(self, state, action):
        return self.board.display(state, action)

    def winner_message(self, winners):
        return self.board.winner_message(winners)

    def get_action(self):
        # Causes the AI to calculate the best action from the
        # current game state and return it.

        self.max_depth = 0
        self.data = {'C': self.C, 'max_actions': self.max_actions, 'name': self.name}
        self.stats.clear()

        state = self.history[-1]
        player = self.board.current_player(state)
        legal = self.board.legal_actions(self.history[:])

        # Bail out early if there is no real choice to be made.
        if not legal:
            return {'type': 'action', 'message': None, 'extras': self.data.copy()}
        if len(legal) == 1:
            return {
                'type': 'action',
                'message': self.board.to_json_action(legal[0]),
                'extras': self.data.copy(),
            }

        games = 0
        begin = time.time()
        while time.time() - begin < self.calculation_time:
            self.run_simulation()
            games += 1

        # Display the number of calls of `run_simulation` and the
        # time elapsed.
        self.data.update(games=games, max_depth=self.max_depth,
                         time=str(time.time() - begin))
        print (self.data['games'], self.data['time'])
        print ("Maximum depth searched:", self.max_depth)

        # Store and display the stats for each possible action.
        self.data['actions'] = self.calculate_action_values(self.history, player, legal)
        for m in self.data['actions']:
            print (self.action_template.format(**m))

        # Return the action with the highest average value.
        return {
            'type': 'action',
            'message': self.board.to_json_action(self.data['actions'][0]['action']),
            'extras': self.data.copy(),
        }

    def run_simulation(self):
        # Plays out a "random" game from the current position,
        # then updates the statistics tables with the result.

        # A bit of an optimization here, so we have a local
        # variable lookup instead of an attribute access each loop.
        stats = self.stats

        visited_states = []
        history_copy = self.history[:]
        state = history_copy[-1]
        player = self.board.current_player(state)

        expand = True
        for t in range(1, self.max_actions + 1):
            legal = self.board.legal_actions(history_copy)
            actions_states = [(a, self.board.next_state(history_copy, a)) for a in legal]

            if expand:
                if not all((player, S) in stats for a, S in actions_states):
                    # `player` here and below refers to the player who
                    # moved into that particular state.
                    stats.update(((player, S), Stat()) for a, S in actions_states
                                 if (player, S) not in stats)
                    expand = False
                    if t > self.max_depth:
                        self.max_depth = t

                # If we have stats on all of the legal actions here, use UCB1.
                log_total = log(
                    sum(stats[(player, S)].visits for a, S in actions_states) or 1)
                values_actions = [
                    (a, S, (e.value / (e.visits or 1)) + self.C * sqrt(log_total / (e.visits or 1)))
                    for a, S, e in ((a, S, stats[(player, S)]) for a, S in actions_states)
                ]
                max_value = max(v for _, _, v in values_actions)
                # Filter down to only those actions with maximum value under UCB1.
                actions_states = [(a, S) for a, S, v in values_actions if v == max_value]

            action, state = choice(actions_states)
            visited_states.append((player, state))
            history_copy.append(state)
            # Who is the next player to take an action?
            player = self.board.current_player(state)

            if self.board.is_ended(history_copy):
                break

        # Back-propagation
        end_values = self.end_values(history_copy)
        for player, state in visited_states:
            if (player, state) not in stats:
                continue
            S = stats[(player, state)]
            S.visits += 1
            S.value += end_values[player]


class UCTWins(UCT):
    name = "jrb.mcts.uct"
    action_template = "{action}: {percent:.2f}% ({wins} / {plays})"

    def __init__(self, board, **kwargs):
        super(UCTWins, self).__init__(board, **kwargs)
        self.end_values = board.win_values

    def calculate_action_values(self, history, player, legal):
        actions_states = ((a, self.board.next_state(history, a)) for a in legal)
        return sorted(
            ({'action': a,
              'percent': 100 * self.stats[(player, S)].value / (self.stats[(player, S)].visits or 1),
              'wins': self.stats[(player, S)].value,
              'plays': self.stats[(player, S)].visits}
             for a, S in actions_states),
            key=lambda x: (x['percent'], x['plays']),
            reverse=True
        )


class UCTValues(UCT):
    name = "jrb.mcts.uctv"
    action_template = "{action}: {average:.1f} ({sum} / {plays})"

    def __init__(self, board, **kwargs):
        super(UCTValues, self).__init__(board, **kwargs)
        self.end_values = board.points_values

    def calculate_action_values(self, history, player, legal):
        actions_states = ((a, self.board.next_state(history, a)) for a in legal)
        return sorted(
            ({'action': a,
              'average': self.stats[(player, S)].value / (self.stats[(player, S)].visits or 1),
              'sum': self.stats[(player, S)].value,
              'plays': self.stats[(player, S)].visits}
             for a, S in actions_states),
            key=lambda x: (x['average'], x['plays']),
            reverse=True
        )
