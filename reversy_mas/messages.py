"""Typed in-process messages exchanged by agents and the match runner."""

from dataclasses import dataclass

from .environment import Color, Move, Position


@dataclass(frozen=True)
class Rating:
    move: Move
    score: float
    reason: str


@dataclass(frozen=True)
class Request:
    sender: str
    recipient: str
    position: Position

    @property
    def state_id(self) -> str:
        return self.position.identifier


@dataclass(frozen=True)
class Proposal:
    sender: str
    recipient: str
    state_id: str
    ratings: tuple[Rating, ...]

    @property
    def preferred(self) -> Rating:
        return max(self.ratings, key=lambda rating: (rating.score, -rating.move))


@dataclass(frozen=True)
class Exchange:
    request: Request
    proposal: Proposal
    accepted: bool
    rejection: str = ""
    invalid_move_attempts: int = 0


@dataclass(frozen=True)
class RankedMove:
    move: Move
    score: float
    supporters: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    move: Move
    reason: str
    selected_agent: str
    exchanges: tuple[Exchange, ...] = ()
    comparison: tuple[RankedMove, ...] = ()


@dataclass(frozen=True)
class Outcome:
    before: Position
    after: Position
    move: Move | None
    flips: int


@dataclass(frozen=True)
class Adaptation:
    agent: str
    opponent: str
    observed_color: Color
    feature: str
    previous_weight: float
    new_weight: float
    reason: str
