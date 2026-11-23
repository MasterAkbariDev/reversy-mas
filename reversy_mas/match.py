"""Match runner shared by the tournament and graphical interface."""

from dataclasses import dataclass
from time import perf_counter

from .agents import Agent
from .environment import BLACK, WHITE, Color, Game, Move, Position, flips, opponent
from .messages import Adaptation, Decision, Outcome


@dataclass(frozen=True)
class Turn:
    actor: str
    outcome: Outcome
    decision: Decision | None
    decision_seconds: float | None
    invalid_move_attempts: int
    adaptations: tuple[Adaptation, ...]


class Match:
    def __init__(self, black: Agent | None, white: Agent | None, position: Position | None = None):
        if black is not None and black is white:
            raise ValueError("Both colors require separate agent instances")
        self.game = Game(position)
        self.players = {BLACK: black, WHITE: white}
        self.history: list[Turn] = []
        for color, agent in self.players.items():
            if agent is not None:
                agent.start_match(self.player_name(opponent(color)))

    @property
    def position(self) -> Position:
        return self.game.position

    def player_name(self, color: Color) -> str:
        agent = self.players[color]
        return agent.name if agent is not None else "Human"

    def advance(self, human_move: Move | None = None) -> Turn:
        before = self.position
        if before.finished:
            raise ValueError("Match has finished")
        agent = self.players[before.turn]
        decision = elapsed = None
        invalid = 0
        if human_move is not None and (agent is not None or not before.legal):
            raise ValueError("A human cannot submit a move on this turn")

        move = None
        if before.legal and agent is None:
            if human_move is None:
                raise ValueError("Choose a legal square")
            move = human_move
        elif before.legal and agent is not None:
            start = perf_counter()
            decision = agent.decide(before)
            elapsed = perf_counter() - start
            move = decision.move
            invalid = sum(exchange.invalid_move_attempts for exchange in decision.exchanges)
            if type(move) is not int or move not in before.legal:
                invalid += 1
                move = before.legal[0]

        after = self.game.submit(move)
        flip_count = len(flips(before.board, before.turn, move)) if move is not None else 0
        outcome = Outcome(before, after, move, flip_count)
        # Return the outcome to both sides. Only the opponent's choices inform its model.
        adaptations = tuple(
            event for color, observer in self.players.items() if observer is not None
            for event in observer.observe(outcome, color)
        )
        turn = Turn(self.player_name(before.turn), outcome, decision, elapsed, invalid, adaptations)
        self.history.append(turn)
        return turn

    def finish(self) -> None:
        if any(agent is None for agent in self.players.values()):
            raise ValueError("An automatic match requires two agents")
        while not self.position.finished:
            self.advance()
