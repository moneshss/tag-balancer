"""
EK Pair Perturbation Search — finds improvements that require
changing 2 parameters simultaneously.

Hill climbing changes one param at a time, so it misses improvements
where neither change alone helps but the combination does. This script
randomly samples 2-param perturbations and confirms winners.

At ~2 min/trial with CPU contention, 7 hours ≈ 200 trials.

Usage:
  python ek_pair_perturb.py --port 3001 --hours 7
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

GAME = "ExplodingKittens"
RESULTS_FILE = "ek_perturb_results.json"

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

# Start 1 final params (810.2 averaged)
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


def save_result(entry):
    path = Path(RESULTS_FILE)
    results = json.loads(path.read_text()) if path.exists() else []
    results.append(entry)
    path.write_text(json.dumps(results, indent=2))


def evaluate(params, n_evals=1):
    scores = []
    for _ in range(n_evals):
        result = submit_run(params)
        score = result.get("score", 0)
        if score > 0:
            scores.append(score)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def perturb_search(max_hours=7):
    current = dict(BEST_KNOWN)
    param_names = list(PARAMS.keys())

    # Establish baseline
    print("  Establishing baseline (3 runs)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Baseline: {current_score:.1f}\n")

    start_time = time.time()
    end_time = start_time + max_hours * 3600
    trial = 0
    improvements = 0

    while time.time() < end_time:
        trial += 1
        elapsed = (time.time() - start_time) / 60

        # Pick 2 random params to change
        p1, p2 = random.sample(param_names, 2)
        v1 = random.choice([v for v in PARAMS[p1] if v != current[p1]])
        v2 = random.choice([v for v in PARAMS[p2] if v != current[p2]])

        candidate = dict(current)
        candidate[p1] = v1
        candidate[p2] = v2

        # Screen
        score = evaluate(candidate, n_evals=1)

        if score > current_score:
            # Confirm
            confirm_score = evaluate(candidate, n_evals=2)
            avg_score = (score + confirm_score * 2) / 3

            if avg_score > current_score:
                print(f"  #{trial} ({elapsed:.0f}m) {p1}={v1}, {p2}={v2}  "
                      f"score: {avg_score:.1f} (was {current_score:.1f})  *IMPROVED*")
                current[p1] = v1
                current[p2] = v2
                current_score = avg_score
                improvements += 1

                save_result({
                    "type": "improvement", "trial": trial,
                    "params": dict(current), "score": avg_score,
                    "changed": {p1: v1, p2: v2},
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                print(f"  #{trial} ({elapsed:.0f}m) {p1}={v1}, {p2}={v2}  "
                      f"score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)")
        else:
            if trial % 20 == 0:
                print(f"  #{trial} ({elapsed:.0f}m) ... best so far: {current_score:.1f} "
                      f"({improvements} improvements)")

        # Save periodic checkpoint
        if trial % 50 == 0:
            save_result({
                "type": "checkpoint", "trial": trial,
                "params": dict(current), "score": current_score,
                "improvements": improvements,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

    total_elapsed = (time.time() - start_time) / 60
    print(f"\n{'='*60}")
    print(f"  Pair perturbation complete — {trial} trials in {total_elapsed:.0f} minutes")
    print(f"  {improvements} improvements found")
    print(f"  Final score: {current_score:.1f}")
    print(f"  Started from: 810.2")
    if current_score > 810.2:
        print(f"  IMPROVEMENT: +{current_score - 810.2:.1f}")
    else:
        print(f"  No improvement over starting point")
    print(f"  Params: {json.dumps(current, indent=4)}")
    print(f"{'='*60}\n")

    save_result({
        "type": "final", "trial": trial,
        "params": dict(current), "score": current_score,
        "improvements": improvements,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3001)
    parser.add_argument("--hours", type=float, default=7)
    args = parser.parse_args()

    API_URL = f"http://localhost:{args.port}/api/run_game"

    print(f"\n{'='*60}")
    print(f"  EK Pair Perturbation — port {args.port}")
    print(f"  Time limit: {args.hours} hours")
    print(f"  Starting from restart winner (810.2)")
    print(f"  Results → {RESULTS_FILE}")
    print(f"{'='*60}\n")

    perturb_search(max_hours=args.hours)
