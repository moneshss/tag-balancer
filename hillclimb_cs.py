"""
Hill Climbing optimizer for Can't Stop.
Starts from the best known params and tweaks one parameter at a time.
Uses single-run screening + 2-run confirmation to filter noise.

Usage:
  python hillclimb_cs.py --rounds 5

Each round tests every parameter at every value, keeping improvements.
One round = ~119 trials × ~5 min = ~10 hours (Can't Stop is the slowest game).
Multiple rounds catch interactions between parameters.
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

API_URL = "http://localhost:3000/api/run_game"
GAME = "CantStop"
RESULTS_FILE = "all_results.json"

# Parameter definitions — ranges centered around current best with room to explore
PARAMS = {
    "TWO_MAX":          list(range(1, 6)),       # 1-5   (4 to test)
    "THREE_MAX":        list(range(1, 9)),        # 1-8   (7 to test)
    "FOUR_MAX":         list(range(1, 11)),       # 1-10  (9 to test)
    "FIVE_MAX":         list(range(2, 15)),       # 2-14  (12 to test)
    "SIX_MAX":          list(range(3, 17)),       # 3-16  (13 to test)
    "SEVEN_MAX":        list(range(5, 21)),       # 5-20  (15 to test)
    "EIGHT_MAX":        list(range(3, 17)),       # 3-16  (13 to test)
    "NINE_MAX":         list(range(2, 15)),       # 2-14  (12 to test)
    "TEN_MAX":          list(range(1, 11)),       # 1-10  (9 to test)
    "ELEVEN_MAX":       list(range(1, 9)),        # 1-8   (7 to test)
    "TWELVE_MAX":       list(range(1, 6)),        # 1-5   (4 to test)
    "COLUMNS_TO_WIN":   list(range(2, 10)),       # 2-9   (7 to test)
    "MARKERS":          list(range(1, 6)),        # 1-5   (4 to test)
}

# Best known params from Optuna (fast score 962.0)
BEST_KNOWN = {
    "TWO_MAX": 2, "THREE_MAX": 4, "FOUR_MAX": 5, "FIVE_MAX": 9,
    "SIX_MAX": 10, "SEVEN_MAX": 14, "EIGHT_MAX": 9, "NINE_MAX": 6,
    "TEN_MAX": 4, "ELEVEN_MAX": 2, "TWELVE_MAX": 1,
    "COLUMNS_TO_WIN": 6, "MARKERS": 2
}


def submit_run(params, run_type="fast"):
    body = {"game": GAME, "params": params, "run_type": run_type, "timeout": 300000}
    try:
        resp = requests.post(API_URL, json=body,
                             headers={"Content-Type": "application/json"},
                             timeout=600)
        if resp.status_code != 200:
            return {"score": 0}
        return resp.json()
    except:
        return {"score": 0}


def save_result(params, score, run_type="fast"):
    path = Path(RESULTS_FILE)
    results = json.loads(path.read_text()) if path.exists() else []
    results.append({
        "game": GAME, "params": params, "score": score,
        "run_type": run_type, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    path.write_text(json.dumps(results, indent=2))


def evaluate(params, n_evals=3):
    """Evaluate params multiple times and return average to reduce noise."""
    scores = []
    for _ in range(n_evals):
        result = submit_run(params)
        score = result.get("score", 0)
        if score > 0:
            scores.append(score)
        save_result(params, score)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def hill_climb(n_rounds=3):
    current = dict(BEST_KNOWN)

    # Count trials per round
    n_trials = sum(len(vals) - (1 if current[p] in vals else 0)
                   for p, vals in PARAMS.items())
    print(f"  Trials per round: ~{n_trials} × ~5 min = ~{n_trials * 5 / 60:.0f} hours\n")

    # Evaluate starting point with averaging
    print("  Evaluating starting point (3 runs for stability)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Starting score (averaged): {current_score:.1f}\n")

    total_start = time.time()

    for round_num in range(1, n_rounds + 1):
        print(f"  --- Round {round_num}/{n_rounds} ---\n")
        improved_this_round = False

        # Shuffle param order each round for variety
        param_names = list(PARAMS.keys())
        random.shuffle(param_names)

        for param_name in param_names:
            values = PARAMS[param_name]
            current_val = current[param_name]
            best_val = current_val
            best_score = current_score

            # Try every other value for this parameter
            candidates = [v for v in values if v != current_val]
            print(f"  [{param_name}] current={current_val}, testing {len(candidates)} values")

            for val in candidates:
                candidate = dict(current)
                candidate[param_name] = val

                # Single eval for screening
                score = evaluate(candidate, n_evals=1)
                elapsed = (time.time() - total_start) / 60

                if score > best_score:
                    # Confirm with additional evals to reduce noise
                    confirm_score = evaluate(candidate, n_evals=2)
                    avg_score = (score + confirm_score * 2) / 3

                    if avg_score > best_score:
                        best_val = val
                        best_score = avg_score
                        print(f"    {param_name}: {current_val} -> {val}  "
                              f"score: {avg_score:.1f} (was {current_score:.1f})  "
                              f"*IMPROVED*  ({elapsed:.0f}m)")
                    else:
                        print(f"    {param_name}: {val}  "
                              f"score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)  ({elapsed:.0f}m)")
                else:
                    print(f"    {param_name}: {val}  score: {score:.1f}  ({elapsed:.0f}m)")

            if best_val != current_val:
                current[param_name] = best_val
                current_score = best_score
                improved_this_round = True
                print(f"\n    >>> Updated {param_name} = {best_val}, score = {current_score:.1f}\n")

        elapsed = (time.time() - total_start) / 60
        print(f"\n  Round {round_num} complete ({elapsed:.0f}m). Score: {current_score:.1f}")
        print(f"  Current params: {json.dumps(current, indent=4)}")

        if not improved_this_round:
            print("  No improvements this round — stopping early.\n")
            break
        print()

    total_elapsed = (time.time() - total_start) / 60
    print(f"\n{'='*60}")
    print(f"  Hill climbing complete in {total_elapsed:.0f} minutes")
    print(f"  Final score: {current_score:.1f}")
    print(f"  Params: {json.dumps(current, indent=4)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Hill Climbing: CantStop — {args.rounds} rounds")
    print(f"  ~119 trials/round × ~5 min = ~10 hours/round")
    print(f"{'='*60}\n")

    hill_climb(n_rounds=args.rounds)
