from dataclasses import replace
from math import inf

import pytest

from reversy_mas.agents import NAMES, Adaptive, Coordinator, Greedy, Strategic, create_agent
from reversy_mas.agents.base import Strategy
from reversy_mas.agents.coordinator import normalized_ranks
from reversy_mas.agents.strategies import search
from reversy_mas.environment import BLACK, WHITE, Position, flips, opponent, play
from reversy_mas.match import Match
from reversy_mas.messages import Outcome, Proposal, Rating, Request
from reversy_mas.tournament import openings


@pytest.mark.parametrize("name", NAMES)
def test_every_agent_chooses_legally_and_deterministically(name):
    agent = create_agent(name)
    for position in [Position(), *openings(7, 3)]:
        first = agent.decide(position)
        assert first.move in position.legal
        assert agent.decide(position) == first


def exhaustive_margin(position, root):
    if position.finished:
        return position.board.count(root) - position.board.count(opponent(root))
    if not position.legal:
        return exhaustive_margin(Position(position.board, opponent(position.turn)), root)
    scores = [
        exhaustive_margin(Position(play(position.board, position.turn, move), opponent(position.turn)), root)
        for move in position.legal
    ]
    return (max if position.turn == root else min)(scores)


def test_minimax_known_endgame_prefers_winning_square():
    rows = (
        "WBBBBBW.", "WBBBBBWB", "WWWBBWBB", "WWWBWBWB",
        "WWBWBWBB", "BBWWWWWB", "BWWWWWWW", "..W.BWWB",
    )
    board = tuple({"B": BLACK, "W": WHITE, ".": 0}[cell] for row in rows for cell in row)
    position = Position(board, WHITE)
    assert len(position.legal) > 1
    margins = {
        move: exhaustive_margin(Position(play(board, WHITE, move), BLACK), WHITE)
        for move in position.legal
    }
    ratings = Strategic(depth=1, exact_endgame=5).rate(position)
    assert margins == {7: 4, 56: -8, 59: -8}
    assert {rating.move: rating.score for rating in ratings} == {
        move: difference + (100_000 if difference > 0 else -100_000 if difference < 0 else 0)
        for move, difference in margins.items()
    }
    assert Strategic().decide(position).move == 7


def test_minimax_forced_pass_does_not_consume_placement_depth():
    position = Position((0, BLACK, WHITE) + (WHITE,) * 61, BLACK)
    assert search(position, 1, -inf, inf, WHITE) == 100_064


class Ballot(Strategy):
    def __init__(self, name, scores, defect=None):
        self.name, self.scores, self.defect = name, scores, defect
        self.feedback = []

    def rate(self, position):
        return tuple(Rating(move, score, self.name) for move, score in zip(position.legal, self.scores))

    def propose(self, request):
        proposal = super().propose(request)
        if self.defect == "stale":
            return replace(proposal, state_id="stale")
        if self.defect == "illegal":
            return replace(proposal, ratings=proposal.ratings + (Rating(0, 999, "illegal"),))
        return proposal

    def observe(self, outcome, own_color):
        self.feedback.append(outcome)
        return ()


def test_coordinator_compares_scales_and_returns_feedback_to_all_members():
    ballots = (
        Ballot("Huge scale", (1_000_000, 8, 0, 1)),
        Ballot("Small A", (0.03, 0.05, 0.01, 0.04)),
        Ballot("Small B", (1, 3, 0, 2)),
    )
    match = Match(Coordinator(ballots), Greedy())
    turn = match.advance()
    assert turn.outcome.move == 26
    assert turn.decision.selected_agent == "Small A"
    assert turn.decision.comparison[0].supporters == ("Small A", "Small B")
    assert len(match.history) == 1 and match.position.scores == (4, 1)
    for exchange, ballot in zip(turn.decision.exchanges, ballots):
        assert exchange.accepted
        assert exchange.request.position == turn.outcome.before
        assert exchange.request.recipient == exchange.proposal.sender == ballot.name
        assert exchange.request.sender == exchange.proposal.recipient == "Coordinator Team"
        assert exchange.proposal.state_id == exchange.request.state_id
        assert ballot.feedback == [turn.outcome]


@pytest.mark.parametrize("defect, count", [("stale", 0), ("illegal", 1)])
def test_invalid_proposal_is_rejected_and_other_member_can_win(defect, count):
    team = Coordinator((Ballot("Bad", (0, 1, 2, 3), defect), Ballot("Good", (9, 1, 2, 3))))
    turn = Match(team, Greedy()).advance()
    assert turn.decision.move == 19
    assert turn.decision.selected_agent == "Good"
    assert not turn.decision.exchanges[0].accepted
    assert turn.invalid_move_attempts == count


def test_all_rejected_proposals_fall_back_to_legal_move():
    team = Coordinator((Ballot("A", (0, 1, 2, 3), "stale"), Ballot("B", (0, 1, 2, 3), "illegal")))
    decision = team.decide(Position())
    assert decision.move == 19 and decision.selected_agent == team.name
    assert not any(exchange.accepted for exchange in decision.exchanges)


def test_rank_normalization_ties_and_nonfinite_rejection():
    ratings = tuple(Rating(move, score, "") for move, score in zip(Position().legal, (9, 5, 5, 0)))
    assert normalized_ranks(Proposal("A", "B", "state", ratings)) == {19: 1, 26: 0.5, 37: 0.5, 44: 0}
    team = Coordinator((Ballot("A", (inf, 1, 2, 3)), Ballot("B", (2, 1, 2, 3))))
    assert not team.decide(Position()).exchanges[0].accepted


def test_adaptive_updates_ratings_and_remembers_opponent_per_instance():
    adaptive = Adaptive()
    adaptive.start_match("Greedy")
    before = next(
        position for position in openings(5, 12)
        if len({len(flips(position.board, position.turn, move)) for move in position.legal}) > 1
    )
    move = Greedy().decide(before).move
    after = Position(play(before.board, before.turn, move), opponent(before.turn))
    outcome = Outcome(before, after, move, len(flips(before.board, before.turn, move)))
    original_ratings = adaptive.rate(after)
    assert adaptive.observe(outcome, before.turn) == ()
    events = adaptive.observe(outcome, after.turn)
    capture = next(event for event in events if event.feature == "capture pressure")
    assert capture.new_weight > capture.previous_weight == 4
    assert capture.opponent == "Greedy" and capture.reason
    assert any(a.score != b.score for a, b in zip(original_ratings, adaptive.rate(after)))
    learned = adaptive.weights
    adaptive.start_match("Other")
    assert adaptive.weights == (4, 3)
    adaptive.start_match("Greedy")
    assert adaptive.weights == learned
    assert Adaptive().weights == (4, 3)


def test_proposal_is_addressed_back_to_requester():
    position = Position()
    proposal = Greedy().propose(Request("Example", "Greedy", position))
    assert proposal.recipient == "Example" and proposal.state_id == position.identifier
    assert tuple(rating.move for rating in proposal.ratings) == position.legal
