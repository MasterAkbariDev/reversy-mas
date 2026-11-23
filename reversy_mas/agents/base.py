"""Autonomous strategy contract. Agents receive snapshots and observed outcomes."""

from abc import ABC, abstractmethod

from ..environment import Color, Position
from ..messages import Adaptation, Decision, Outcome, Proposal, Rating, Request


class Agent(ABC):
    name: str

    def start_match(self, opponent_name: str) -> None:
        """Set the opponent identity for the next match."""

    @abstractmethod
    def decide(self, position: Position) -> Decision:
        """Choose an action when the position contains legal moves."""

    def observe(self, outcome: Outcome, own_color: Color) -> tuple[Adaptation, ...]:
        return ()


class Strategy(Agent):
    @abstractmethod
    def rate(self, position: Position) -> tuple[Rating, ...]:
        """Score every legal move on the strategy's own scale."""

    def propose(self, request: Request) -> Proposal:
        return Proposal(self.name, request.sender, request.state_id, self.rate(request.position))

    def decide(self, position: Position) -> Decision:
        proposal = self.propose(Request("Environment", self.name, position))
        choice = proposal.preferred
        return Decision(choice.move, choice.reason, self.name)
