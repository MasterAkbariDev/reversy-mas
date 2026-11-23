"""Paired opening round robin and reproducible coordination experiment."""

import argparse
import itertools
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from .agents import NAMES, Coordinator, create_agent
from .environment import BLACK, WHITE, Game, Position
from .match import Match


@dataclass
class Stats:
    wins: int = 0
    losses: int = 0
    draws: int = 0
    decisions: int = 0
    decision_seconds: float = 0
    match_seconds: float = 0
    invalid_attempts: int = 0
    adaptations: Counter = field(default_factory=Counter)
    weight_movement: Counter = field(default_factory=Counter)
    selected: Counter = field(default_factory=Counter)

    def summary(self) -> dict:
        matches = self.wins + self.losses + self.draws
        return {
            "matches": matches, "wins": self.wins, "losses": self.losses, "draws": self.draws,
            "win_rate": self.wins / matches,
            "average_decision_ms": self.decision_seconds * 1000 / max(1, self.decisions),
            "average_match_seconds": self.match_seconds / matches,
            "invalid_attempts": self.invalid_attempts,
            "selection_counts": dict(self.selected),
            "adaptation_updates": dict(self.adaptations),
            "mean_absolute_weight_change": {
                key: self.weight_movement[key] / count for key, count in self.adaptations.items()
            },
        }


def openings(seed: int, count: int) -> list[Position]:
    if not 1 <= count <= 20:
        raise ValueError("Use 1–20 paired openings")
    rng = random.Random(seed)
    result = []
    seen = set()
    while len(result) < count:
        game = Game()
        for _ in range(6):
            legal = game.position.legal
            game.submit(rng.choice(legal) if legal else None)
        position = game.position
        if position.identifier not in seen:
            result.append(position)
            seen.add(position.identifier)
    return result


def round_robin(
    seed: int = 42, opening_count: int = 2, depth: int = 2,
    names: tuple[str, ...] = NAMES,
) -> dict:
    if not 1 <= depth <= 5 or len(names) < 2 or len(set(names)) != len(names):
        raise ValueError("Use unique competitors and search depth 1–5")
    starts = openings(seed, opening_count)
    stats = {name: Stats() for name in names}
    rows = []
    for first, second in itertools.combinations(names, 2):
        for index, position in enumerate(starts, start=1):
            for black, white in ((first, second), (second, first)):
                start = perf_counter()
                match = Match(create_agent(black, depth), create_agent(white, depth), position)
                match.finish()
                elapsed = perf_counter() - start
                winner = match.position.winner
                black_score, white_score = match.position.scores
                rows.append({
                    "opening": index, "black": black, "white": white, "black_score": black_score,
                    "white_score": white_score, "winner": {BLACK: black, WHITE: white, 0: "Draw"}[winner],
                    "winner_color": winner, "turns": len(match.history), "seconds": elapsed,
                })
                for color, name in ((BLACK, black), (WHITE, white)):
                    record = stats[name]
                    record.wins += winner == color
                    record.losses += winner not in (color, 0)
                    record.draws += winner == 0
                    record.match_seconds += elapsed
                for turn in match.history:
                    record = stats[turn.actor]
                    if turn.decision_seconds is not None:
                        record.decision_seconds += turn.decision_seconds
                        record.decisions += 1
                    record.invalid_attempts += turn.invalid_move_attempts
                    if turn.actor == Coordinator.name and turn.decision:
                        record.selected[turn.decision.selected_agent] += 1
                    for event in turn.adaptations:
                        observing_name = white if event.observed_color == BLACK else black
                        stats[observing_name].adaptations[event.feature] += 1
                        stats[observing_name].weight_movement[event.feature] += abs(
                            event.new_weight - event.previous_weight
                        )
    return {
        "config": {"seed": seed, "opening_count": opening_count, "opening_plies": 6, "depth": depth},
        "opening_ids": [position.identifier for position in starts],
        "total_matches": len(rows), "agents": {name: record.summary() for name, record in stats.items()},
        "matches": rows,
    }


def coordination_experiment(report: dict) -> list[dict]:
    """Compare team and member on the same opening, color and external opponent."""
    team = Coordinator.name
    rows = report["matches"]
    by_fixture = {
        (row["opening"], row["black"], row["white"]): row["winner"]
        for row in rows
    }
    comparisons = []
    for individual in report["agents"]:
        if individual == team:
            continue
        points = Counter()
        for row in rows:
            lineup = row["black"], row["white"]
            if team not in lineup or individual in lineup:
                continue
            replacement = tuple(individual if name == team else name for name in lineup)
            opponent_name = next(name for name in lineup if name != team)
            baseline = by_fixture[(row["opening"], *replacement)]
            team_points = 1 if row["winner"] == team else 0.5 if row["winner"] == "Draw" else 0
            baseline_points = 1 if baseline == individual else 0.5 if baseline == "Draw" else 0
            points["team"] += team_points
            points["solo"] += baseline_points
            points["fixtures"] += 1
            points["improved"] += team_points > baseline_points
            points["worse"] += team_points < baseline_points
            points["tied"] += team_points == baseline_points
        if points["fixtures"]:
            comparisons.append({
                "individual": individual, **{key: points[key] for key in (
                    "fixtures", "team", "solo", "improved", "worse", "tied"
                )},
                "point_rate_delta": (points["team"] - points["solo"]) / points["fixtures"],
            })
    return comparisons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--openings", type=int, choices=range(1, 21), default=2)
    parser.add_argument("--depth", type=int, choices=range(1, 6), default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = round_robin(args.seed, args.openings, args.depth)
    report["coordination_comparison"] = coordination_experiment(report)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['total_matches']} matches")
    for name, row in report["agents"].items():
        print(f"{name:17} {row['wins']:3} W {row['losses']:3} L {row['draws']:3} D "
              f"{row['win_rate']:6.1%} win rate {row['average_decision_ms']:8.2f} ms/decision")
    for row in report["coordination_comparison"]:
        print(f"Team vs {row['individual']:10} {row['point_rate_delta']:+.1%} paired point rate")


if __name__ == "__main__":
    main()
