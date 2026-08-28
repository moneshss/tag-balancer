"""
Hill Climbing optimizer for Dominion.
Handles numeric parameters AND card selection (10 from 26).

For cards: tries swapping each included card for each excluded card.
For numeric params: same approach as EK/7W hill climbers.

Dominion is ~3 min/trial, slower than 7W but faster than Can't Stop.
One round ≈ ~200 trials × ~3 min ≈ ~10 hours.

Usage:
  python hillclimb_dom.py --rounds 3
"""

import argparse
import json
import random
import time
import requests
from pathlib import Path

API_URL = "http://localhost:3000/api/run_game"
GAME = "Dominion"
RESULTS_FILE = "all_results.json"

# All available kingdom cards
ALL_CARDS = [
    "CELLAR", "CHAPEL", "MOAT", "HARBINGER", "MERCHANT", "VASSAL",
    "VILLAGE", "WORKSHOP", "BUREAUCRAT", "GARDENS", "MILITIA",
    "MONEYLENDER", "POACHER", "REMODEL", "SMITHY", "THRONE_ROOM",
    "BANDIT", "COUNCIL_ROOM", "FESTIVAL", "LABORATORY", "LIBRARY",
    "MARKET", "MINE", "SENTRY", "WITCH", "ARTISAN",
]

# Numeric parameter definitions
PARAMS = {
    "HAND_SIZE":                    [3, 5, 7, 10, 12, 15],
    "PILES_EXHAUSTED_FOR_GAME_END": [1, 2, 3, 4, 5],
    "KINGDOM_CARDS_OF_EACH_TYPE":   [5, 8, 10, 12, 15, 20],
    "CURSE_CARDS_PER_PLAYER":       [5, 10, 15, 20, 25, 30],
    "STARTING_COPPER":              [3, 5, 7, 10, 12, 15],
    "STARTING_ESTATES":             [1, 3, 5, 7, 10, 15],
    "COPPER_SUPPLY":                [5, 10, 15, 20, 30, 40],
    "SILVER_SUPPLY":                [10, 20, 30, 40],
    "GOLD_SUPPLY":                  [10, 15, 20, 30],
}

# Best known params (974.6 from random search)
BEST_KNOWN = {
    "HAND_SIZE": 10,
    "PILES_EXHAUSTED_FOR_GAME_END": 3,
    "KINGDOM_CARDS_OF_EACH_TYPE": 10,
    "CURSE_CARDS_PER_PLAYER": 20,
    "STARTING_COPPER": 10,
    "STARTING_ESTATES": 10,
    "COPPER_SUPPLY": 10,
    "SILVER_SUPPLY": 30,
    "GOLD_SUPPLY": 20,
    "CARDS": [
        "SMITHY", "MINE", "MARKET", "GARDENS", "WORKSHOP",
        "MOAT", "BUREAUCRAT", "CHAPEL", "FESTIVAL", "LABORATORY",
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


def hill_climb_cards(current, current_score, total_start):
    """Try swapping each included card for each excluded card."""
    current_cards = list(current["CARDS"])
    excluded = [c for c in ALL_CARDS if c not in current_cards]
    best_score = current_score
    best_cards = list(current_cards)
    improved = False

    for i, old_card in enumerate(current_cards):
        for new_card in excluded:
            candidate = dict(current)
            new_list = list(best_cards)
            new_list[i] = new_card
            candidate["CARDS"] = new_list

            score = evaluate(candidate, n_evals=1)
            elapsed = (time.time() - total_start) / 60

            if score > best_score:
                confirm_score = evaluate(candidate, n_evals=2)
                avg_score = (score + confirm_score * 2) / 3

                if avg_score > best_score:
                    best_cards = list(new_list)
                    best_score = avg_score
                    print(f"    CARDS: {old_card} -> {new_card}  "
                          f"score: {avg_score:.1f} (was {current_score:.1f})  "
                          f"*IMPROVED*  ({elapsed:.0f}m)")
                else:
                    print(f"    CARDS: {old_card}->{new_card}  "
                          f"score: {score:.1f} -> confirmed {avg_score:.1f} (false positive)  ({elapsed:.0f}m)")
            else:
                print(f"    CARDS: {old_card}->{new_card}  score: {score:.1f}  ({elapsed:.0f}m)")

    if best_cards != current_cards:
        improved = True

    return best_cards, best_score, improved


def hill_climb(n_rounds=3):
    current = dict(BEST_KNOWN)
    current["CARDS"] = list(BEST_KNOWN["CARDS"])

    # Evaluate starting point with averaging
    print("  Evaluating starting point (3 runs for stability)...")
    current_score = evaluate(current, n_evals=3)
    print(f"  Starting score (averaged): {current_score:.1f}\n")

    total_start = time.time()

    for round_num in range(1, n_rounds + 1):
        print(f"  --- Round {round_num}/{n_rounds} ---\n")
        improved_this_round = False

        # Shuffle param order each round
        param_names = list(PARAMS.keys())
        random.shuffle(param_names)

        # Numeric parameters first
        for param_name in param_names:
            values = PARAMS[param_name]
            current_val = current[param_name]
            best_val = current_val
            best_score = current_score

            for val in values:
                if val == current_val:
                    continue

                candidate = dict(current)
                candidate["CARDS"] = list(current["CARDS"])
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

        # Card selection
        print(f"\n    --- Testing card swaps ---\n")
        new_cards, new_score, cards_improved = hill_climb_cards(
            current, current_score, total_start
        )
        if cards_improved:
            current["CARDS"] = new_cards
            current_score = new_score
            improved_this_round = True
            print(f"\n    >>> Updated CARDS = {new_cards}, score = {current_score:.1f}\n")

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
    print(f"  Hill Climbing: Dominion — {args.rounds} rounds")
    print(f"{'='*60}\n")

    hill_climb(n_rounds=args.rounds)
