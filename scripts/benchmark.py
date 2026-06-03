#!/usr/bin/env python3
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT = str(ROOT / "main.py")
OFFICIAL_NEAREST = str(ROOT / "kaggle" / "orbit-wars" / "main.py")


def run_episode(agent, opponents, seed, debug=False):
    env = make("orbit_wars", configuration={"seed": seed}, debug=debug)
    players = [agent, *opponents]
    env.run(players)
    final = env.steps[-1]
    rewards = [state.reward for state in final]
    statuses = [state.status for state in final]
    return {
        "seed": seed,
        "players": len(players),
        "reward": rewards[0],
        "win": 1 if rewards[0] == 1 else 0,
        "rewards": rewards,
        "statuses": statuses,
    }


def summarize(rows):
    rewards = [row["reward"] for row in rows]
    wins = [row["win"] for row in rows]
    return {
        "games": len(rows),
        "wins": sum(wins),
        "win_rate": sum(wins) / len(wins) if wins else 0.0,
        "mean_reward": statistics.mean(rewards) if rewards else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark an Orbit Wars agent locally.")
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=1)
    parser.add_argument(
        "--matchup",
        choices=["random", "starter", "nearest", "all"],
        default="all",
    )
    parser.add_argument("--out", default=None, help="Optional CSV path for raw rows.")
    args = parser.parse_args()

    matchups = {
        "random": ["random"],
        "starter": ["starter"],
        "nearest": [OFFICIAL_NEAREST],
        "all": ["random", "starter", OFFICIAL_NEAREST],
    }

    selected = matchups[args.matchup]
    seeds = range(args.start_seed, args.start_seed + args.seeds)
    all_rows = []
    summaries = {}

    for label, opponents in [
        ("2p_random", ["random"]),
        ("2p_starter", ["starter"]),
        ("2p_nearest", [OFFICIAL_NEAREST]),
        ("4p_mixed", selected),
    ]:
        rows = []
        for seed in seeds:
            row = run_episode(args.agent, opponents, seed)
            row["matchup"] = label
            rows.append(row)
            all_rows.append(row)
        summaries[label] = summarize(rows)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["matchup", "seed", "players", "reward", "win", "rewards", "statuses"]
            )
            writer.writeheader()
            for row in all_rows:
                serializable = row.copy()
                serializable["rewards"] = json.dumps(serializable["rewards"])
                serializable["statuses"] = json.dumps(serializable["statuses"])
                writer.writerow(serializable)

    print(json.dumps(summaries, indent=2, sort_keys=True))
    worst = min(summary["win_rate"] for summary in summaries.values())
    return 0 if worst >= 0.5 else 1


if __name__ == "__main__":
    sys.exit(main())
