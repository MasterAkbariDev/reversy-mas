"""A bounded opponent model updated from observed decisions."""

from dataclasses import dataclass

from .base import Strategy
from .strategies import EDGES, corner_risk, stable_edges
from ..environment import CORNERS, Color, Position, flips, legal_moves, notation, opponent, play
from ..messages import Adaptation, Outcome, Rating


@dataclass
class OpponentProfile:
    capture_bias: float = 0.0
    edge_bias: float = 0.0


class Adaptive(Strategy):
    name = "Adaptive"
    learning_rate = 0.3

    def __init__(self) -> None:
        self.profiles: dict[str, OpponentProfile] = {}
        self.start_match("Unknown")

    def start_match(self, opponent_name: str) -> None:
        self.opponent_name = opponent_name
        self.profile = self.profiles.setdefault(opponent_name, OpponentProfile())

    @property
    def weights(self) -> tuple[float, float]:
        return 4 + 3 * self.profile.capture_bias, 3 + 2 * self.profile.edge_bias

    def observe(self, outcome: Outcome, own_color: Color) -> tuple[Adaptation, ...]:
        move = outcome.move
        legal = outcome.before.legal
        if outcome.before.turn == own_color or move is None or len(legal) < 2:
            return ()
        board, color = outcome.before.board, outcome.before.turn
        old_weights = self.weights
        captures = [len(flips(board, color, candidate)) for candidate in legal]
        edge_choices = [candidate in EDGES for candidate in legal]
        observations = []
        if max(captures) > min(captures):
            average = sum(captures) / len(legal)
            signal = (outcome.flips - average) / (max(captures) - min(captures))
            self.profile.capture_bias += self.learning_rate * (signal - self.profile.capture_bias)
            observations.append((0, "capture pressure", f"flipped {outcome.flips} vs legal mean {average:.2f}"))
        if any(edge_choices) and not all(edge_choices):
            average = sum(edge_choices) / len(legal)
            signal = (move in EDGES) - average
            self.profile.edge_bias += self.learning_rate * (signal - self.profile.edge_bias)
            location = "an edge" if move in EDGES else "an interior square"
            observations.append((1, "edge security", f"chose {location} with {average:.0%} edge options"))
        new_weights = self.weights
        return tuple(
            Adaptation(
                self.name, self.opponent_name, color, feature, old_weights[index],
                new_weights[index], f"{self.opponent_name} played {notation(move)} and {reason}."
            )
            for index, feature, reason in observations
            if abs(new_weights[index] - old_weights[index]) > 1e-9
        )

    def rate(self, position: Position) -> tuple[Rating, ...]:
        board, color = position.board, position.turn
        foe = opponent(color)
        capture_weight, edge_weight = self.weights
        ratings = []
        for move in position.legal:
            next_board = play(board, color, move)
            replies = legal_moves(next_board, foe)
            worst_capture = max(
                (len(flips(next_board, foe, reply)) for reply in replies), default=0
            )
            open_edges = sum(reply in EDGES for reply in replies)
            secure_edges = stable_edges(next_board, color) - stable_edges(next_board, foe)
            exposed_corners = sum(reply in CORNERS for reply in replies)
            endgame_weight = 3 if next_board.count(0) <= 12 else 0
            score = (
                55 * (move in CORNERS) - 36 * exposed_corners - 5 * len(replies)
                - capture_weight * worst_capture + edge_weight * (secure_edges - open_edges)
                - corner_risk(next_board, color)
                + endgame_weight * (next_board.count(color) - next_board.count(foe))
            )
            reason = (
                f"Against {self.opponent_name}, capture pressure {capture_weight:.2f} × worst reply "
                f"{worst_capture}. Edge security {edge_weight:.2f}, stable lead {secure_edges}, "
                f"opponent edge replies {open_edges}."
            )
            ratings.append(Rating(move, score, reason))
        return tuple(ratings)
