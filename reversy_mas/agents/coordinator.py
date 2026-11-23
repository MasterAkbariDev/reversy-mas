"""A team policy that aggregates normalized ranks from independent proposals."""

from math import isfinite

from .base import Agent, Strategy
from ..environment import Color, Position, notation
from ..messages import Adaptation, Decision, Outcome, Proposal, RankedMove, Request, Exchange


def normalized_ranks(proposal: Proposal) -> dict[int, float]:
    """Fraction of alternatives beaten, with half credit for ties."""
    values = [rating.score for rating in proposal.ratings]
    if len(values) == 1:
        return {proposal.ratings[0].move: 1.0}
    return {
        rating.move: (values.count(rating.score) - 1 + 2 * sum(
            score < rating.score for score in values
        )) / (2 * (len(values) - 1))
        for rating in proposal.ratings
    }


class Coordinator(Agent):
    name = "Coordinator Team"

    def __init__(self, members: tuple[Strategy, ...]):
        if len(members) < 2 or len({member.name for member in members}) != len(members):
            raise ValueError("A team requires at least two uniquely named strategies")
        self.members = members

    def start_match(self, opponent_name: str) -> None:
        for member in self.members:
            member.start_match(opponent_name)

    def observe(self, outcome: Outcome, own_color: Color) -> tuple[Adaptation, ...]:
        return tuple(event for member in self.members for event in member.observe(outcome, own_color))

    def decide(self, position: Position) -> Decision:
        legal = set(position.legal)
        exchanges = []
        for member in self.members:
            request = Request(self.name, member.name, position)
            proposal = member.propose(request)
            moves = tuple(rating.move for rating in proposal.ratings)
            invalid = sum(type(move) is not int or move not in legal for move in moves)
            rejection = ""
            if (proposal.state_id, proposal.sender, proposal.recipient) != (
                request.state_id, member.name, self.name
            ):
                rejection = "State or message routing mismatch"
            elif invalid or len(moves) != len(legal) or set(moves) != legal:
                rejection = "Each legal move must appear exactly once"
            elif any(not isfinite(rating.score) for rating in proposal.ratings):
                rejection = "Scores must be finite"
            exchanges.append(Exchange(request, proposal, not rejection, rejection, invalid))

        proposals = [exchange.proposal for exchange in exchanges if exchange.accepted]
        if not proposals:
            return Decision(min(legal), "No valid proposals. Chose the first legal square.", self.name, tuple(exchanges))

        ranks = [normalized_ranks(proposal) for proposal in proposals]
        favorites = [(proposal.preferred.move, proposal.sender) for proposal in proposals]
        candidates = [
            RankedMove(
                move, round(sum(rank[move] for rank in ranks) / len(ranks), 12),
                tuple(sender for favorite, sender in favorites if favorite == move),
            )
            for move in sorted({favorite for favorite, _ in favorites})
        ]
        comparison = tuple(sorted(candidates, key=lambda item: (-item.score, -len(item.supporters), item.move)))
        choice = comparison[0]
        reason = (
            f"{notation(choice.move)} led the nominated moves with mean rank {choice.score:.3f}. "
            f"Recommended by {', '.join(choice.supporters)}."
        )
        return Decision(choice.move, reason, choice.supporters[0], tuple(exchanges), comparison)
