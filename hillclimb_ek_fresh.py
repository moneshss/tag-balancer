"""
Fresh EK hill climb from the restart winner (Start 1, 810.2 averaged).
Re-tests all params with different random shuffle order to catch
improvements the first pass missed.

Key change: expanded nCardsPerPlayer to [3,4,5,6,7,8,9,10,12,15]
since both Start 1 and Start 3 converged to 7 but 6/8/9 were never tested.

Usage:
  python hillclimb_ek_fresh.py --port 3000 --rounds 3
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

GAME = "ExplodingKittens"
RESULTS_FILE = "ek_fresh_results.json"

# Expanded nCardsPerPlayer range — fill the gaps around 7
PARAMS = {
    "nCardsPerPlayer":     [3, 4, 5, 6, 7, 8, 9, 10, 12, 15],
    "nopeOwnCards":        [True, False],
    "ATTACK_count":        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "SKIP_count":          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "FAVOR_count":         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "SHUFFLE_count":       [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "SEETHEFUTURE_count":  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "TACOCAT_count":       [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "MELONCAT_count":      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "BEARDCAT_count":      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "RAINBOWCAT_count":    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "FURRYCAT_count":      [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "NOPE_count":          [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "DEFUSE_count":        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
}

# Start 1 final params (810.2 averaged — best from restarts)
BEST_KNOWN = {
    "nCardsPerPlayer": 7,
    "nopeOwnCards": False,
    "ATTACK_count": 3,
    "SKIP_count": 5,
    "FAVOR_count": 10,
    "SHUFFLE_count": 10,
    "SEETHEFUTURE_count": 3,
    "TACOCAT_count": 8,
    "MELONCAT_count": 1,
    "BEARDCAT_count": 3,
    "RAINBOWCAT_count": 6,
    "FURRYCAT_count": 2,
    "NOPE_count": 7,
    "DEFUSE_count": 6,
}

API_URL = None


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

    print("  Evaluating starting point (3 runs)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Starting score (averaged): {current_score:.1f}\n")

    total_start = time.time()

    for round_num in range(1, n_rounds + 1):
        print(f"  --- Round {round_num}/{n_rounds} ---\n")
        improved_this_round = False

        param_names = list(PARAMS.keys())
        random.shuffle(param_names)

        for param_name in param_names:
            values = PARAMS[param_name]
            current_val = current[param_name]
            best_val = current_val
            best_score = current_score

            candidates = [v for v in values if v != current_val]
            print(f"  [{param_name}] current={current_val}, testing {len(candidates)} values")

            for val in candidates:
                candidate = dict(current)
                candidate[param_name] = val

                score = evaluate(candidate, n_evals=1)
                elapsed = (time.time() - total_start) / 60

                if score > best_score:
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
    print(f"  Started from: 810.2")
    if current_score > 810.2:
        print(f"  IMPROVEMENT: +{current_score - 810.2:.1f}")
    else:
        print(f"  No improvement over starting point")
    print(f"  Params: {json.dumps(current, indent=4)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    API_URL = f"http://localhost:{args.port}/api/run_game"

    print(f"\n{'='*60}")
    print(f"  Fresh EK Hill Climb — port {args.port}")
    print(f"  Starting from restart winner (810.2)")
    print(f"  {args.rounds} rounds, expanded nCardsPerPlayer range")
    print(f"  Results → {RESULTS_FILE}")
    print(f"{'='*60}\n")

    hill_climb(n_rounds=args.rounds)
