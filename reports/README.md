# Benchmark Notes

Generated CSV benchmark outputs are intentionally ignored by git. Keep notable
summaries here so the repo records decisions without accumulating bulky run
artifacts.

## v2 local baseline

Command:

```bash
.venv/bin/python scripts/benchmark.py --seeds 30 --out reports/benchmark-v2.csv
```

Results:

| Matchup | Wins | Games | Win rate |
| --- | ---: | ---: | ---: |
| 2p random | 30 | 30 | 100.0% |
| 2p official nearest | 28 | 30 | 93.3% |
| 2p official starter | 22 | 30 | 73.3% |
| 4p mixed | 18 | 30 | 60.0% |

This is not sufficient evidence for a Kaggle submission. The first Kaggle
submission should wait until the agent has a stronger local benchmark suite and
evidence that it is plausibly top-500 level.
