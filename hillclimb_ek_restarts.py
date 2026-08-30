"""
EK Random Restarts — find better local optima by hill climbing
from multiple random starting points.

Phase 1: Screen 25 random configs (single fast run each) — ~50 min
Phase 2: Hill climb the top 3 scorers for 2 rounds each — ~12 hours

The current best (793.6 averaged) came from hill climbing ONE starting
point. Multiple starts dramatically increase the chance of finding a
better local optimum in EK's noisy, high-dimensional space.

Usage:
  python hillclimb_ek_restarts.py --port 3001
  (run on port 3001 while Can't Stop hill-climbs on port 3000)
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

GAME = "ExplodingKittens"
RESULTS_FILE = "ek_restart_results.json"  # separate file — avoids write conflicts with CS on port 3000

# Parameter definitions — same as original EK hill climber
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

# Current best (793.6 averaged after hill climbing)
CURRENT_BEST = {
    "nCardsPerPlayer": 5, "nopeOwnCards": False,
    "ATTACK_count": 4, "SKIP_count": 7, "FAVOR_count": 10,
    "SHUFFLE_count": 7, "SEETHEFUTURE_count": 10, "TACOCAT_count": 4,
    "MELONCAT_count": 4, "BEARDCAT_count": 10, "RAINBOWCAT_count": 5,
    "FURRYCAT_count": 6, "NOPE_count": 6, "DEFUSE_count": 3,
}

API_URL = None  # set in main() based on --port


def random_params():
    """Generate a fully random EK configuration."""
    return {k: random.choice(v) for k, v in PARAMS.items()}


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


def save_result(params, score, run_type="fast", tag=""):
    path = Path(RESULTS_FILE)
    results = json.loads(path.read_text()) if path.exists() else []
    results.append({
        "game": GAME, "params": params, "score": score,
        "run_type": run_type, "tag": tag,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    path.write_text(json.dumps(results, indent=2))


def evaluate(params, n_evals=3, tag=""):
    """Evaluate params multiple times and return average to reduce noise."""
    scores = []
    for _ in range(n_evals):
        result = submit_run(params)
        score = result.get("score", 0)
        if score > 0:
            scores.append(score)
        save_result(params, score, tag=tag)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


# ── Phase 1: Random screening ────────────────────────────────

def phase1_screen(n_random=25):
    """Screen random configs with single fast runs."""
    print(f"\n  Phase 1: Screening {n_random} random configs...\n")

    candidates = []
    start = time.time()

    for i in range(n_random):
        params = random_params()
        score = evaluate(params, n_evals=1, tag=f"phase1-{i}")
        elapsed = (time.time() - start) / 60
        print(f"    Config {i+1}/{n_random}: {score:.1f}  ({elapsed:.0f}m)")
        candidates.append((score, params))

    candidates.sort(key=lambda x: x[0], reverse=True)

    print(f"\n  Phase 1 complete ({(time.time()-start)/60:.0f}m)")
    print(f"  Top 5 scores: {[f'{s:.1f}' for s, _ in candidates[:5]]}")

    return candidates


# ── Phase 2: Hill climbing ────────────────────────────────────

def hill_climb(start_params, label, n_rounds=2):
    """Hill climb from a starting point — same logic as hillclimb_ek.py."""
    current = dict(start_params)

    print(f"\n  Evaluating {label} (3 runs)...")
    current_score = evaluate(current, n_evals=3, tag=f"{label}-baseline")
    print(f"  {label} baseline (averaged): {current_score:.1f}\n")

    total_start = time.time()

    for round_num in range(1, n_rounds + 1):
        print(f"  --- {label} Round {round_num}/{n_rounds} ---\n")
        improved_this_round = False

        param_names = list(PARAMS.keys())
        random.shuffle(param_names)

        for param_name in param_names:
            values = PARAMS[param_name]
            current_val = current[param_name]
            best_val = current_val
            best_score = current_score

            for val in values:
                if val == current_val:
                    continue

                candidate = dict(current)
                candidate[param_name] = val

                score = evaluate(candidate, n_evals=1, tag=f"{label}-r{round_num}")
                elapsed = (time.time() - total_start) / 60

                if score > best_score:
                    confirm_score = evaluate(candidate, n_evals=2, tag=f"{label}-confirm")
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
        print(f"\n  {label} Round {round_num} complete ({elapsed:.0f}m). Score: {current_score:.1f}")

        if not improved_this_round:
            print(f"  No improvements — stopping {label} early.\n")
            break
        print()

    return current, current_score


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3001,
                        help="Docker API port (default 3001, avoids conflict with CS on 3000)")
    parser.add_argument("--n-random", type=int, default=25,
                        help="Random configs to screen in Phase 1")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Top configs to hill climb in Phase 2")
    parser.add_argument("--rounds", type=int, default=2,
                        help="Hill climbing rounds per start")
    parser.add_argument("--min-screen-score", type=float, default=600.0,
                        help="Minimum Phase 1 score to qualify for Phase 2")
    args = parser.parse_args()

    global API_URL
    API_URL = f"http://localhost:{args.port}/api/run_game"

    print(f"\n{'='*60}")
    print(f"  EK Random Restarts — port {args.port}")
    print(f"  Phase 1: {args.n_random} random screens")
    print(f"  Phase 2: Top {args.top_k} (>{args.min_screen_score}) × {args.rounds} rounds")
    print(f"  Current best: 793.6 averaged")
    print(f"  Results → {RESULTS_FILE}")
    print(f"{'='*60}")

    total_start = time.time()

    # Phase 1
    candidates = phase1_screen(n_random=args.n_random)

    # Filter by minimum score
    qualified = [(s, p) for s, p in candidates if s >= args.min_screen_score]
    print(f"\n  {len(qualified)} configs scored >= {args.min_screen_score}")

    if not qualified:
        print("  No configs qualified! Try more random samples or lower the threshold.")
        print("  Falling back to top 3 regardless of score...\n")
        qualified = candidates[:args.top_k]

    # Phase 2
    print(f"\n{'='*60}")
    print(f"  Phase 2: Hill climbing {min(args.top_k, len(qualified))} starts")
    print(f"{'='*60}")

    all_results = []

    for i in range(min(args.top_k, len(qualified))):
        screen_score, start_params = qualified[i]
        print(f"\n  ═══ Start {i+1}/{min(args.top_k, len(qualified))}: "
              f"screened at {screen_score:.1f} ═══")
        final_params, final_score = hill_climb(
            start_params, f"start-{i+1}", n_rounds=args.rounds
        )
        all_results.append((f"start-{i+1}", screen_score, final_score, final_params))

    # Summary
    total_elapsed = (time.time() - total_start) / 60
    all_results.sort(key=lambda x: x[2], reverse=True)

    print(f"\n{'='*60}")
    print(f"  FINAL RESULTS — {total_elapsed:.0f} minutes total")
    print(f"  Current best to beat: 793.6 averaged")
    print(f"{'='*60}")

    for label, screen_s, final_s, params in all_results:
        marker = " <<< NEW BEST" if final_s > 793.6 else ""
        print(f"\n  {label}: screened {screen_s:.1f} → hill-climbed {final_s:.1f}{marker}")
        print(f"    {json.dumps(params)}")

    best_label, _, best_score, best_params = all_results[0]
    print(f"\n  {'─'*40}")
    print(f"  OVERALL BEST: {best_label} at {best_score:.1f}")
    if best_score > 793.6:
        print(f"  IMPROVEMENT: +{best_score - 793.6:.1f} over current")
    else:
        print(f"  No improvement over current 793.6")
    print(f"\n{json.dumps(best_params, indent=4)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
