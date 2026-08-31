"""
EK Pair Perturbation Search v2 — seeded from the COMBINED config (3508, ~829 avg).

Changes from v1:
  * BEST_KNOWN is now the combined leaderboard-best config (TACO=6, STF=6, MELON=5),
    not the old Start-1 params (810.2). Searching from 829 instead of 810 means we
    stop rediscovering things we already have.
  * --seed argument so two parallel ports explore different perturbations instead
    of duplicating coverage.
  * Per-port results file (ek_perturb_v2_p{port}.json) so parallel scripts never
    do read-modify-write on the same JSON.

Hill climbing changes one param at a time, so it misses improvements where neither
change alone helps but the combination does. This script randomly samples 2-param
perturbations and confirms winners (screen 1 run -> confirm 2 runs).

At ~1.9 min/trial with CPU contention, 2.5 hours per port is roughly 75-80 trials.

Usage (two terminals, one per port):
  python ek_pair_perturb_v2.py --port 3000 --hours 2.5 --seed 1
  python ek_pair_perturb_v2.py --port 3001 --hours 2.5 --seed 2
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

GAME = "ExplodingKittens"

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

# COMBINED config — submission 11, leaderboard best 3508.
# This is the perturbation winner (STF=6, MELON=5) with the fresh-hill-climb
# TACOCAT=6 stacked on top. Baseline gets re-measured on launch (3 runs).
BEST_KNOWN = {
    "nCardsPerPlayer": 7,
    "nopeOwnCards": False,
    "ATTACK_count": 3,
    "SKIP_count": 5,
    "FAVOR_count": 10,
    "SHUFFLE_count": 10,
    "SEETHEFUTURE_count": 6,
    "TACOCAT_count": 6,
    "MELONCAT_count": 5,
    "BEARDCAT_count": 3,
    "RAINBOWCAT_count": 6,
    "FURRYCAT_count": 2,
    "NOPE_count": 7,
    "DEFUSE_count": 6,
}

# Rough starting anchor for the end-of-run summary. The real baseline is measured
# live at launch and used for all comparisons.
ANCHOR = 829.1

API_URL = None
RESULTS_FILE = None


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


def perturb_search(max_hours, seed):
    rng = random.Random(seed)  # per-port RNG so the two ports diverge
    current = dict(BEST_KNOWN)
    param_names = list(PARAMS.keys())

    print("  Establishing baseline (3 runs)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Baseline (combined config): {current_score:.1f}\n")
    save_result({
        "type": "baseline", "trial": 0,
        "params": dict(current), "score": current_score,
        "seed": seed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    start_time = time.time()
    end_time = start_time + max_hours * 3600
    trial = 0
    improvements = 0

    while time.time() < end_time:
        trial += 1
        elapsed = (time.time() - start_time) / 60

        p1, p2 = rng.sample(param_names, 2)
        v1 = rng.choice([v for v in PARAMS[p1] if v != current[p1]])
        v2 = rng.choice([v for v in PARAMS[p2] if v != current[p2]])

        candidate = dict(current)
        candidate[p1] = v1
        candidate[p2] = v2

        # Screen with 1 run
        score = evaluate(candidate, n_evals=1)

        if score > current_score:
            # Confirm with 2 more runs
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
                    "changed": {p1: v1, p2: v2}, "seed": seed,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            else:
                print(f"  #{trial} ({elapsed:.0f}m) {p1}={v1}, {p2}={v2}  "
                      f"score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)")
        else:
            if trial % 20 == 0:
                print(f"  #{trial} ({elapsed:.0f}m) ... best so far: {current_score:.1f} "
                      f"({improvements} improvements)")

        if trial % 25 == 0:
            save_result({
                "type": "checkpoint", "trial": trial,
                "params": dict(current), "score": current_score,
                "improvements": improvements, "seed": seed,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

    total_elapsed = (time.time() - start_time) / 60
    print(f"\n{'='*60}")
    print(f"  Pair perturbation complete — {trial} trials in {total_elapsed:.0f} minutes")
    print(f"  {improvements} improvements found")
    print(f"  Final score: {current_score:.1f}  (started ~{ANCHOR})")
    if current_score > ANCHOR:
        print(f"  IMPROVEMENT over anchor: +{current_score - ANCHOR:.1f}")
    else:
        print(f"  No improvement over anchor")
    print(f"  Params: {json.dumps(current, indent=4)}")
    print(f"{'='*60}\n")

    save_result({
        "type": "final", "trial": trial,
        "params": dict(current), "score": current_score,
        "improvements": improvements, "seed": seed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--hours", type=float, default=2.5)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    API_URL = f"http://localhost:{args.port}/api/run_game"
    RESULTS_FILE = f"ek_perturb_v2_p{args.port}.json"

    print(f"\n{'='*60}")
    print(f"  EK Pair Perturbation v2 — port {args.port}, seed {args.seed}")
    print(f"  Time limit: {args.hours} hours")
    print(f"  Starting from COMBINED config (~{ANCHOR})")
    print(f"  Results -> {RESULTS_FILE}")
    print(f"{'='*60}\n")

    perturb_search(max_hours=args.hours, seed=args.seed)
