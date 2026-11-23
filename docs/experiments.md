# Tournament experiment

## Method

```bash
python -m reversy_mas.tournament --seed 42 --openings 5 --depth 2 --output experiment-local.json
```

The recorded run used CPython 3.12 on Linux. A seeded generator chose six uniformly random legal placements from the standard board for each of five distinct starts. Each of the ten agent pairs played each opening twice with swapped colors. Agents began each fixture with fresh state. Strategic agents used search depth 2 and searched to completion from five empty squares. Ties were deterministic. The opening hashes, final scores, timings, and metric totals are in [experiment-results.json](experiment-results.json).

## Results

| Player | Games | Wins | Losses | Draws | Win rate | Mean decision (ms) | Mean match (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Strategic | 40 | 31 | 9 | 0 | 77.5% | 4.79 | 0.167 |
| Greedy | 40 | 0 | 40 | 0 | 0.0% | 0.02 | 0.076 |
| Defensive | 40 | 23 | 17 | 0 | 57.5% | 0.18 | 0.068 |
| Adaptive | 40 | 21 | 19 | 0 | 52.5% | 0.26 | 0.073 |
| Coordinator Team | 40 | 25 | 15 | 0 | 62.5% | 4.41 | 0.157 |

Across the 100 games, the runner recorded zero invalid move attempts and zero draws. Decision time is wall time spent inside the active policy, including team communication and aggregation when applicable. Passes are excluded from the decision mean. Match time includes setup and feedback processing. The same match duration contributes to each participant's mean.

The team credited Strategic 718 times, Defensive 213, Greedy 135, and Adaptive 22. Shared nominations receive primary credit in roster order, so these totals measure attribution under the policy.

| Agent instance | Capture updates | Mean absolute change | Edge updates | Mean absolute change |
| --- | ---: | ---: | ---: | ---: |
| Adaptive solo | 866 | 0.304 | 782 | 0.259 |
| Adaptive inside team | 908 | 0.285 | 809 | 0.270 |

## Does coordination help?

For each individual strategy, compare its result with the team's result against the same external opponent, on the same opening and with the same color. Exclude the compared individual from the opponent pool. Each comparison uses three opponents, five openings, and two colors, for 30 matched fixtures. Wins score 1, draws 0.5, and losses 0.

| Replaced solo policy | Team points | Solo points | Better / worse / tied | Team point-rate change |
| --- | ---: | ---: | ---: | ---: |
| Strategic | 22 | 24 | 3 / 5 / 22 | −6.7 percentage points |
| Greedy | 15 | 0 | 15 / 0 / 15 | +50.0 percentage points |
| Defensive | 20 | 18 | 4 / 2 / 24 | +6.7 percentage points |
| Adaptive | 18 | 18 | 3 / 3 / 24 | 0.0 percentage points |

The team improved on Greedy and Defensive, tied Adaptive on points, and trailed Strategic across matched opponents. In a separate direct comparison drawn from the round robin, Strategic beat the team 7–3.

## Limitations

Five seeded openings and one search-depth configuration support a reproducible comparison at this setting. Opening pairs are dependent, and opponents overlap across comparisons. The differences are descriptive and do not establish statistical significance or rankings at other depths. The tournament estimates the effect of replacing a whole solo policy with the team policy. It does not isolate the contribution of adaptation. Timings reflect a shared legal-move cache, fixture order, and the execution machine. Search settings and timing budgets were not matched across all policies.
