"""
Hill Climbing optimizer for 7 Wonders.
Same approach as hillclimb_ek.py — tweak one parameter at a time,
confirm improvements with averaging.

7W is fast (~1.75 min/trial) so this should complete quicker than EK.
One round ≈ ~130 trials × ~1.75 min ≈ ~4 hours.

The 'wonders' parameter is a list (pick 4-7 from 7 available), so we
handle it specially: try adding, removing, and swapping wonders.

Usage:
  python hillclimb_7w.py --rounds 3
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

API_URL = "http://localhost:3000/api/run_game"
GAME = "Wonders7"
RESULTS_FILE = "all_results.json"

# All available wonders
ALL_WONDERS = [
    "TheColossusOfRhodes",
    "TheLighthouseOfAlexandria",
    "TheTempleOfArtemisInEphesus",
    "TheHangingGardensOfBabylon",
    "TheStatueOfZeusInOlympia",
    "TheMausoleumOfHalicarnassus",
    "ThePyramidsOfGiza",
]

# Numeric parameter definitions with search ranges
PARAMS = {
    "nCostNeighbourResource":  [0, 1, 2, 3, 4, 5],
    "nCostDiscountedResource": [0, 1, 2, 3, 4, 5],
    "nCoinsDiscard":           [0, 1, 2, 3, 4, 5],
    "startingCoins":           [0, 1, 2, 3, 4, 5, 6, 7],
    "rawMaterialLow":          [1, 2, 3, 4, 5],
    "rawMaterialHigh":         [1, 2, 3, 4, 5],
    "manufacturedMaterial":     [1, 2, 3, 4, 5],
    "victoryLow":              [1, 2, 3, 4, 5],
    "victoryMed":              [1, 2, 3, 4, 5],
    "victoryHigh":             [3, 4, 5, 6, 7],
    "victoryVeryHigh":         [3, 4, 5, 6, 7],
    "victoryPantheon":         [5, 6, 7, 8, 9],
    "victoryPalace":           [6, 7, 8, 9, 10],
    "tavernMoney":             [3, 4, 5, 6, 7],
    "wildcardProduction":      [1, 2, 3, 4, 5],
    "commercialMultiplierLow": [1, 2, 3, 4, 5],
    "commercialMultiplierMed": [1, 2, 3, 4, 5],
    "commercialMultiplierHigh":[1, 2, 3, 4, 5],
    "militaryLow":             [1, 2, 3, 4, 5],
    "militaryMed":             [1, 2, 3, 4, 5],
    "militaryHigh":            [1, 2, 3, 4, 5],
    "scienceCompass":          [1, 2, 3, 4, 5],
    "scienceTablet":           [1, 2, 3, 4, 5],
    "scienceCog":              [1, 2, 3, 4, 5],
    "guildMultiplierLow":      [1, 2, 3, 4, 5],
    "guildMultiplierMed":      [1, 2, 3, 4, 5],
    "builderMultiplier":       [1, 2, 3, 4, 5],
    "decoratorVictoryPoints":  [5, 6, 7, 8, 9],
}

# Best known params (983.3 from random search)
BEST_KNOWN = {
    "nCostNeighbourResource": 0,
    "nCostDiscountedResource": 3,
    "nCoinsDiscard": 1,
    "startingCoins": 7,
    "rawMaterialLow": 4,
    "rawMaterialHigh": 5,
    "manufacturedMaterial": 3,
    "victoryLow": 4,
    "victoryMed": 5,
    "victoryHigh": 3,
    "victoryVeryHigh": 5,
    "victoryPantheon": 5,
    "victoryPalace": 9,
    "tavernMoney": 7,
    "wildcardProduction": 5,
    "commercialMultiplierLow": 2,
    "commercialMultiplierMed": 5,
    "commercialMultiplierHigh": 4,
    "militaryLow": 1,
    "militaryMed": 2,
    "militaryHigh": 2,
    "scienceCompass": 4,
    "scienceTablet": 1,
    "scienceCog": 2,
    "guildMultiplierLow": 1,
    "guildMultiplierMed": 5,
    "builderMultiplier": 3,
    "decoratorVictoryPoints": 9,
    "wonders": [
        "TheStatueOfZeusInOlympia",
        "TheColossusOfRhodes",
        "TheHangingGardensOfBabylon",
        "TheMausoleumOfHalicarnassus",
    ],
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


def hill_climb_wonders(current, current_score, total_start):
    """Try modifications to the wonders list: swap, add, remove."""
    current_wonders = list(current["wonders"])
    not_included = [w for w in ALL_WONDERS if w not in current_wonders]
    best_score = current_score
    best_wonders = list(current_wonders)
    improved = False

    # Try swapping each included wonder for each excluded one
    for i, old_w in enumerate(current_wonders):
        for new_w in not_included:
            candidate = dict(current)
            new_list = list(current_wonders)
            new_list[i] = new_w
            candidate["wonders"] = new_list

            score = evaluate(candidate, n_evals=1)
            elapsed = (time.time() - total_start) / 60

            if score > best_score:
                confirm_score = evaluate(candidate, n_evals=2)
                avg_score = (score + confirm_score * 2) / 3

                if avg_score > best_score:
                    best_wonders = list(new_list)
                    best_score = avg_score
                    short_old = old_w.replace("The", "").replace("Of", "")[:20]
                    short_new = new_w.replace("The", "").replace("Of", "")[:20]
                    print(f"    wonders: swap {short_old} -> {short_new}  "
                          f"score: {avg_score:.1f} (was {current_score:.1f})  "
                          f"*IMPROVED*  ({elapsed:.0f}m)")
                else:
                    print(f"    wonders: swap  score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)  ({elapsed:.0f}m)")
            else:
                print(f"    wonders: swap  score: {score:.1f}  ({elapsed:.0f}m)")

    # Try adding a wonder (if < 7)
    if len(current_wonders) < 7:
        for new_w in not_included:
            candidate = dict(current)
            new_list = list(best_wonders) + [new_w]
            candidate["wonders"] = new_list

            score = evaluate(candidate, n_evals=1)
            elapsed = (time.time() - total_start) / 60

            if score > best_score:
                confirm_score = evaluate(candidate, n_evals=2)
                avg_score = (score + confirm_score * 2) / 3

                if avg_score > best_score:
                    best_wonders = list(new_list)
                    best_score = avg_score
                    print(f"    wonders: +{new_w[:25]}  "
                          f"score: {avg_score:.1f}  *IMPROVED*  ({elapsed:.0f}m)")
                else:
                    print(f"    wonders: add  score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)  ({elapsed:.0f}m)")
            else:
                print(f"    wonders: add  score: {score:.1f}  ({elapsed:.0f}m)")

    # Try removing a wonder (if > 4)
    if len(best_wonders) > 4:
        for i, w in enumerate(best_wonders):
            candidate = dict(current)
            new_list = [x for j, x in enumerate(best_wonders) if j != i]
            candidate["wonders"] = new_list

            score = evaluate(candidate, n_evals=1)
            elapsed = (time.time() - total_start) / 60

            if score > best_score:
                confirm_score = evaluate(candidate, n_evals=2)
                avg_score = (score + confirm_score * 2) / 3

                if avg_score > best_score:
                    best_wonders = list(new_list)
                    best_score = avg_score
                    print(f"    wonders: -{w[:25]}  "
                          f"score: {avg_score:.1f}  *IMPROVED*  ({elapsed:.0f}m)")
                else:
                    print(f"    wonders: remove  score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)  ({elapsed:.0f}m)")
            else:
                print(f"    wonders: remove  score: {score:.1f}  ({elapsed:.0f}m)")

    if best_wonders != current_wonders:
        improved = True

    return best_wonders, best_score, improved


def hill_climb(n_rounds=3):
    current = dict(BEST_KNOWN)
    current["wonders"] = list(BEST_KNOWN["wonders"])

    # Evaluate starting point with averaging
    print("  Evaluating starting point (3 runs for stability)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Starting score (averaged): {current_score:.1f}\n")

    total_start = time.time()

    for round_num in range(1, n_rounds + 1):
        print(f"  --- Round {round_num}/{n_rounds} ---\n")
        improved_this_round = False

        # Shuffle numeric param order each round
        param_names = list(PARAMS.keys())
        random.shuffle(param_names)

        # Numeric parameters
        for param_name in param_names:
            values = PARAMS[param_name]
            current_val = current[param_name]
            best_val = current_val
            best_score = current_score

            for val in values:
                if val == current_val:
                    continue

                candidate = dict(current)
                candidate["wonders"] = list(current["wonders"])
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

        # Wonders parameter
        print(f"\n    --- Testing wonders combinations ---\n")
        new_wonders, new_score, wonders_improved = hill_climb_wonders(
            current, current_score, total_start
        )
        if wonders_improved:
            current["wonders"] = new_wonders
            current_score = new_score
            improved_this_round = True
            print(f"\n    >>> Updated wonders = {new_wonders}, score = {current_score:.1f}\n")

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
    print(f"  Hill Climbing: 7 Wonders — {args.rounds} rounds")
    print(f"{'='*60}\n")

    hill_climb(n_rounds=args.rounds)
