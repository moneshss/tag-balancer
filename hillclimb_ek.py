"""
Hill Climbing optimizer for Exploding Kittens.
Starts from the best known params and tweaks one parameter at a time.
Much more effective than Bayesian optimization when you already have
a decent starting point in a noisy, high-dimensional space.

Usage:
  python hillclimb_ek.py --rounds 5

Each round tests every parameter at every value, keeping improvements.
One round = ~140 trials × ~1.5 min = ~3.5 hours.
Multiple rounds catch interactions between parameters.
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

API_URL = "http://localhost:3000/api/run_game"
GAME = "ExplodingKittens"
RESULTS_FILE = "all_results.json"

# Parameter definitions
PARAMS = {
    "nCardsPerPlayer":     [3, 5, 7, 10, 15],
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

# Best known params (879.8 from random search)
BEST_KNOWN = {
    "nCardsPerPlayer": 15,
    "nopeOwnCards": False,
    "ATTACK_count": 10,
    "SKIP_count": 7,
    "FAVOR_count": 7,
    "SHUFFLE_count": 7,
    "SEETHEFUTURE_count": 10,
    "TACOCAT_count": 4,
    "MELONCAT_count": 4,
    "BEARDCAT_count": 10,
    "RAINBOWCAT_count": 5,
    "FURRYCAT_count": 3,
    "NOPE_count": 8,
    "DEFUSE_count": 3,
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
            for val in values:
                if val == current_val:
                    continue
                
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
    print(f"  Hill Climbing: ExplodingKittens — {args.rounds} rounds")
    print(f"{'='*60}\n")

    hill_climb(n_rounds=args.rounds)
