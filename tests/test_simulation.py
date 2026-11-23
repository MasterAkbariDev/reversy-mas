import pytest

from reversy_mas.agents import NAMES, Coordinator, Greedy, create_agent
from reversy_mas.agents.base import Agent
from reversy_mas.environment import BLACK, WHITE
from reversy_mas.match import Match
from reversy_mas.messages import Decision
from reversy_mas.tournament import coordination_experiment, round_robin


@pytest.mark.parametrize("first, second", [
    ("Strategic", "Greedy"), ("Defensive", "Adaptive"),
    ("Adaptive", "Strategic"), ("Coordinator Team", "Strategic"),
])
def test_full_match(first, second):
    match = Match(create_agent(first), create_agent(second))
    match.finish()
    assert match.position.finished
    assert match.position.winner in (BLACK, WHITE, 0)
    assert all(turn.invalid_move_attempts == 0 for turn in match.history)
    assert sum(turn.outcome.move is not None for turn in match.history) == sum(match.position.scores) - 4
    assert all(b.outcome.before == a.outcome.after for a, b in zip(match.history, match.history[1:]))


def test_human_turn_and_bad_agent_move():
    class Illegal(Agent):
        name = "Illegal"

        def decide(self, position):
            return Decision(0, "Illegal suggestion", self.name)

    match = Match(None, Illegal())
    with pytest.raises(ValueError):
        match.advance()
    with pytest.raises(ValueError):
        match.advance(0)
    assert not match.history
    match.advance(19)
    with pytest.raises(ValueError):
        match.advance(26)
    turn = match.advance()
    assert turn.invalid_move_attempts == 1
    assert turn.outcome.move in turn.outcome.before.legal


def test_tournament_replays_paired_fixtures_and_computes_metrics():
    first = round_robin(42, 1, 1)
    second = round_robin(42, 1, 1)
    assert first["total_matches"] == 20
    assert first["opening_ids"] == second["opening_ids"]
    assert [{k: v for k, v in row.items() if k != "seconds"} for row in first["matches"]] == [
        {k: v for k, v in row.items() if k != "seconds"} for row in second["matches"]
    ]
    fixtures = {(row["black"], row["white"]) for row in first["matches"]}
    assert fixtures == {(a, b) for a in NAMES for b in NAMES if a != b}
    assert sum(row["wins"] for row in first["agents"].values()) == sum(
        row["losses"] for row in first["agents"].values()
    )
    assert all(row["matches"] == 8 and row["invalid_attempts"] == 0 for row in first["agents"].values())
    team = first["agents"][Coordinator.name]
    assert team["selection_counts"] and team["adaptation_updates"]
    assert all(change > 0 for change in team["mean_absolute_weight_change"].values())
    comparison = coordination_experiment(first)
    assert len(comparison) == 4 and comparison == coordination_experiment(second)
    assert all(row["fixtures"] == row["improved"] + row["worse"] + row["tied"] == 6 for row in comparison)


def test_agents_cannot_share_an_instance():
    agent = Greedy()
    with pytest.raises(ValueError):
        Match(agent, agent)
