"""
Quick optimizer: 7 Wonders (30 trials) + Dominion card selection (20 trials)
Target: under 2 hours total.

Usage:
  python quick_7w_dom.py
"""

import json
import random
import time
import requests
from pathlib import Path
from itertools import combinations

API_URL = "http://localhost:3000/api/run_game"
RESULTS_FILE = "all_results.json"

# ─── 7 Wonders ───────────────────────────────────────────────────────────────

WONDERS_ALL = [
    "TheColossusOfRhodes",
    "TheLighthouseOfAlexandria",
    "TheTempleOfArtemisInEphesus",
    "TheHangingGardensOfBabylon",
    "TheStatueOfZeusInOlympia",
    "TheMausoleumOfHalicarnassus",
    "ThePyramidsOfGiza",
]

W7_PARAMS = {
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

# ─── Dominion ────────────────────────────────────────────────────────────────

ALL_DOMINION_CARDS = [
    "CELLAR", "CHAPEL", "MOAT", "HARBINGER", "MERCHANT", "VASSAL",
    "VILLAGE", "WORKSHOP", "BUREAUCRAT", "GARDENS", "MILITIA",
    "MONEYLENDER", "POACHER", "REMODEL", "SMITHY", "THRONE_ROOM",
    "BANDIT", "COUNCIL_ROOM", "FESTIVAL", "LABORATORY", "LIBRARY",
    "MARKET", "MINE", "SENTRY", "WITCH", "ARTISAN",
]

# Best numeric params — keep these fixed, only vary cards
DOM_BEST_NUMERIC = {
    "HAND_SIZE": 10,
    "PILES_EXHAUSTED_FOR_GAME_END": 3,
    "KINGDOM_CARDS_OF_EACH_TYPE": 10,
    "CURSE_CARDS_PER_PLAYER": 20,
    "STARTING_COPPER": 10,
    "STARTING_ESTATES": 10,
    "COPPER_SUPPLY": 10,
    "SILVER_SUPPLY": 30,
    "GOLD_SUPPLY": 20,
}


def submit_run(game, params):
    body = {"game": game, "params": params, "run_type": "fast", "timeout": 300000}
    try:
        resp = requests.post(API_URL, json=body,
                             headers={"Content-Type": "application/json"},
                             timeout=600)
        if resp.status_code != 200:
            return {"score": 0}
        return resp.json()
    except:
        return {"score": 0}


def save_result(game, params, score):
    path = Path(RESULTS_FILE)
    results = json.loads(path.read_text()) if path.exists() else []
    results.append({
        "game": game, "params": params, "score": score,
        "run_type": "fast", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    path.write_text(json.dumps(results, indent=2))


def random_7w_params():
    params = {k: random.choice(v) for k, v in W7_PARAMS.items()}
    n_wonders = random.choice([4, 5, 6, 7])
    params["wonders"] = random.sample(WONDERS_ALL, n_wonders)
    return params


def random_dom_cards():
    """Random 10 cards from the 26 available, keep numeric params fixed."""
    params = dict(DOM_BEST_NUMERIC)
    params["CARDS"] = random.sample(ALL_DOMINION_CARDS, 10)
    return params


def run_search(game, n_trials, param_fn):
    print(f"\n{'='*60}")
    print(f"  Random Search: {game} — {n_trials} trials")
    print(f"{'='*60}\n")

    best_score = 0
    best_params = None
    start = time.time()

    for i in range(1, n_trials + 1):
        params = param_fn()
        result = submit_run(game, params)
        score = result.get("score", 0)
        save_result(game, params, score)

        if score > best_score:
            best_score = score
            best_params = params
            print(f"  [{i:3d}/{n_trials}]  score: {score:7.1f}  best: {best_score:7.1f}  *NEW BEST*")
        else:
            print(f"  [{i:3d}/{n_trials}]  score: {score:7.1f}  best: {best_score:7.1f}")

    elapsed = (time.time() - start) / 60
    print(f"\n  Done in {elapsed:.0f}m. Best {game}: {best_score:.1f}")
    if best_params:
        print(f"  Params: {json.dumps(best_params, indent=4)}\n")
    return best_score, best_params


if __name__ == "__main__":
    total_start = time.time()

    print(f"\n{'='*60}")
    print(f"  Quick Optimization: 7 Wonders + Dominion Cards")
    print(f"  Target: under 2 hours")
    print(f"{'='*60}")

    w7_score, w7_params = run_search("Wonders7", 30, random_7w_params)
    dom_score, dom_params = run_search("Dominion", 20, random_dom_cards)

    total = (time.time() - total_start) / 60
    print(f"\n{'='*60}")
    print(f"  COMPLETE in {total:.0f} minutes")
    print(f"  7 Wonders best:  {w7_score:.1f}  (current: 983.3)")
    print(f"  Dominion best:   {dom_score:.1f}  (current: 974.6)")
    print(f"{'='*60}\n")
