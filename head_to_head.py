"""
Head-to-head EK config verification.

Runs each candidate config the same number of times, ROUND-ROBIN (one run of
each per round, in a fixed order), so time-correlated noise (CPU load, etc.)
hits every config equally. Then reports mean / std / min / max per config so you
can see which is genuinely stronger rather than which got a lucky single roll.

This is a MEASUREMENT tool, not a search. It changes nothing and submits nothing.

Usage:
  python head_to_head.py --port 3000 --runs 10
"""

import argparse
import json
import statistics
import time
import requests
from pathlib import Path

GAME = "ExplodingKittens"
RESULTS_FILE = "head_to_head_results.json"

# --- Candidates -------------------------------------------------------------
# A/B differ ONLY in TACOCAT (6 vs 8) — the clean test of the speculative stack.
# C/D are tonight's two search endpoints, included at low expectation.
CANDIDATES = {
    "combined_TACO6 (sub 11, board 3508)": {
        "nCardsPerPlayer": 7, "nopeOwnCards": False, "ATTACK_count": 3,
        "SKIP_count": 5, "FAVOR_count": 10, "SHUFFLE_count": 10,
        "SEETHEFUTURE_count": 6, "TACOCAT_count": 6, "MELONCAT_count": 5,
        "BEARDCAT_count": 3, "RAINBOWCAT_count": 6, "FURRYCAT_count": 2,
        "NOPE_count": 7, "DEFUSE_count": 6,
    },
    "perturbation_TACO8 (sub 10, board 3499)": {
        "nCardsPerPlayer": 7, "nopeOwnCards": False, "ATTACK_count": 3,
        "SKIP_count": 5, "FAVOR_count": 10, "SHUFFLE_count": 10,
        "SEETHEFUTURE_count": 6, "TACOCAT_count": 8, "MELONCAT_count": 5,
        "BEARDCAT_count": 3, "RAINBOWCAT_count": 6, "FURRYCAT_count": 2,
        "NOPE_count": 7, "DEFUSE_count": 6,
    },
    "p3001_final (805)": {
        "nCardsPerPlayer": 7, "nopeOwnCards": False, "ATTACK_count": 6,
        "SKIP_count": 5, "FAVOR_count": 10, "SHUFFLE_count": 8,
        "SEETHEFUTURE_count": 6, "TACOCAT_count": 10, "MELONCAT_count": 10,
        "BEARDCAT_count": 3, "RAINBOWCAT_count": 6, "FURRYCAT_count": 6,
        "NOPE_count": 2, "DEFUSE_count": 4,
    },
    "p3000_final (792)": {
        "nCardsPerPlayer": 3, "nopeOwnCards": True, "ATTACK_count": 3,
        "SKIP_count": 5, "FAVOR_count": 10, "SHUFFLE_count": 1,
        "SEETHEFUTURE_count": 2, "TACOCAT_count": 9, "MELONCAT_count": 5,
        "BEARDCAT_count": 3, "RAINBOWCAT_count": 6, "FURRYCAT_count": 2,
        "NOPE_count": 7, "DEFUSE_count": 9,
    },
}

API_URL = None


def submit_run(params, run_type="fast"):
    body = {"game": GAME, "params": params, "run_type": run_type, "timeout": 300000}
    try:
        resp = requests.post(API_URL, json=body,
                             headers={"Content-Type": "application/json"},
                             timeout=600)
        if resp.status_code != 200:
            return 0
        return resp.json().get("score", 0)
    except:
        return 0


def save(all_scores):
    Path(RESULTS_FILE).write_text(json.dumps(all_scores, indent=2))


def run_head_to_head(n_runs):
    names = list(CANDIDATES.keys())
    scores = {name: [] for name in names}
    start = time.time()

    for r in range(1, n_runs + 1):
        print(f"\n  --- Round {r}/{n_runs} ---")
        for name in names:  # fixed order each round = round-robin
            s = submit_run(CANDIDATES[name])
            if s > 0:
                scores[name].append(s)
            elapsed = (time.time() - start) / 60
            print(f"    {name:42s}  {s:7.1f}   ({elapsed:.0f}m)")
            save(scores)  # checkpoint every single run

    # --- Summary ---
    print(f"\n{'='*72}")
    print(f"  HEAD-TO-HEAD SUMMARY  ({n_runs} runs each)")
    print(f"{'='*72}")

    ranked = []
    for name in names:
        vals = scores[name]
        if not vals:
            ranked.append((name, 0, 0, 0, 0, 0))
            continue
        mean = statistics.mean(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        ranked.append((name, mean, std, min(vals), max(vals), len(vals)))

    ranked.sort(key=lambda x: x[1], reverse=True)

    print(f"\n  {'config':42s}  {'mean':>7s} {'std':>6s} {'min':>6s} {'max':>6s} {'n':>3s}")
    print(f"  {'-'*42}  {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*3}")
    for name, mean, std, lo, hi, n in ranked:
        print(f"  {name:42s}  {mean:7.1f} {std:6.1f} {lo:6.1f} {hi:6.1f} {n:3d}")

    if len(ranked) >= 2 and ranked[0][5] > 0 and ranked[1][5] > 0:
        top, second = ranked[0], ranked[1]
        gap = top[1] - second[1]
        # crude SE of the difference of two means
        se = ((top[2] ** 2) / max(top[5], 1) + (second[2] ** 2) / max(second[5], 1)) ** 0.5
        print(f"\n  Top-2 gap: {gap:.1f}   (approx SE of gap: {se:.1f})")
        if gap > 2 * se:
            print(f"  -> '{top[0]}' looks genuinely ahead.")
        else:
            print(f"  -> Gap is within noise. These are statistically indistinguishable;")
            print(f"     keep whatever is already banked (3508 = combined) rather than churn.")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()

    API_URL = f"http://localhost:{args.port}/api/run_game"

    print(f"\n{'='*72}")
    print(f"  EK Head-to-Head — port {args.port}, {args.runs} runs each, "
          f"{len(CANDIDATES)} configs")
    print(f"  Round-robin interleaved. Results -> {RESULTS_FILE}")
    print(f"{'='*72}")

    run_head_to_head(args.runs)
