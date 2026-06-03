# Orbit Wars

Working repo for the Kaggle [Orbit Wars](https://www.kaggle.com/competitions/orbit-wars)
competition.

The current `main.py` is a local candidate agent only. Do not submit to Kaggle
until local evidence suggests the bot is at least top-500 level.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Kaggle credentials are expected in `~/.kaggle/kaggle.json` or
`~/.kaggle/access_token`.

## Local Tests

```bash
.venv/bin/python -m pytest tests/test_agent.py
```

## Local Benchmark

```bash
.venv/bin/python scripts/benchmark.py --seeds 30 --out reports/benchmark-v2.csv
```

Current v2 summary:

| Matchup | Wins | Games | Win rate |
| --- | ---: | ---: | ---: |
| 2p random | 30 | 30 | 100.0% |
| 2p official nearest | 28 | 30 | 93.3% |
| 2p official starter | 22 | 30 | 73.3% |
| 4p mixed | 18 | 30 | 60.0% |

## Kaggle Submission Gate

Do not submit the first Kaggle result yet. Before submitting, require:

- A stronger opponent pool than `random` / official starter agents.
- A larger seed suite with known difficult seeds.
- Current leaderboard/top-500 score context.
- A manual confirmation step before running `kaggle competitions submit`.
