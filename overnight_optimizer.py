"""
Overnight Optuna optimization for all 3 remaining games.
Seeded with existing random search results.

Usage:
  python overnight_optimizer.py

Estimated runtime: 6-8 hours (based on ~5min/trial for slower games)
"""

import json
import random
import time
import requests
import optuna
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_URL = "http://localhost:3000/api/run_game"
RESULTS_FILE = "all_results.json"

# How many Optuna trials per game
TRIALS = {
    "ExplodingKittens": 50,  # Most room to improve (879 -> ???) ~2.5h
    "Dominion": 30,          # Already at 974 ~1.5h
    "Wonders7": 30,          # Already at 983 ~1h
    "CantStop": 25,          # Already at 957, slow game ~2h
}

# ---------------------------------------------------------------------------
# Game definitions (same as remaining_games_optimizer.py)
# ---------------------------------------------------------------------------

EXPLODING_KITTENS_PARAMS = {
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

DOMINION_PARAMS = {
    "HAND_SIZE":                     [3, 5, 7, 10],
    "PILES_EXHAUSTED_FOR_GAME_END":  [1, 3, 5, 7, 10],
    "KINGDOM_CARDS_OF_EACH_TYPE":    [5, 10, 15, 20],
    "CURSE_CARDS_PER_PLAYER":        [5, 10, 15, 20],
    "STARTING_COPPER":               [3, 5, 7, 10, 15],
    "STARTING_ESTATES":              [1, 3, 5, 7, 10],
    "COPPER_SUPPLY":                 [10, 20, 32, 40, 50],
    "SILVER_SUPPLY":                 [10, 20, 30, 40, 50],
    "GOLD_SUPPLY":                   [10, 20, 30, 40, 50],
}

DOMINION_ALL_CARDS = [
    "CELLAR", "CHAPEL", "MOAT", "HARBINGER", "MERCHANT", "VASSAL",
    "VILLAGE", "WORKSHOP", "BUREAUCRAT", "GARDENS", "MILITIA",
    "MONEYLENDER", "POACHER", "REMODEL", "SMITHY", "THRONE_ROOM",
    "BANDIT", "COUNCIL_ROOM", "FESTIVAL", "LABORATORY", "LIBRARY",
    "MARKET", "MINE", "SENTRY", "WITCH", "ARTISAN",
]

WONDERS7_PARAMS = {
    "nCostNeighbourResource":   [0, 1, 2, 3, 4, 5],
    "nCostDiscountedResource":  [0, 1, 2, 3, 4, 5],
    "nCoinsDiscard":            [0, 1, 2, 3, 4, 5],
    "startingCoins":            [0, 1, 2, 3, 4, 5, 6, 7],
    "rawMaterialLow":           [1, 2, 3, 4, 5],
    "rawMaterialHigh":          [1, 2, 3, 4, 5],
    "manufacturedMaterial":     [1, 2, 3, 4, 5],
    "victoryLow":               [1, 2, 3, 4, 5],
    "victoryMed":               [1, 2, 3, 4, 5],
    "victoryHigh":              [3, 4, 5, 6, 7],
    "victoryVeryHigh":          [3, 4, 5, 6, 7],
    "victoryPantheon":          [5, 6, 7, 8, 9],
    "victoryPalace":            [6, 7, 8, 9, 10],
    "tavernMoney":              [3, 4, 5, 6, 7],
    "wildcardProduction":       [1, 2, 3, 4, 5],
    "commercialMultiplierLow":  [1, 2, 3, 4, 5],
    "commercialMultiplierMed":  [1, 2, 3, 4, 5],
    "commercialMultiplierHigh": [1, 2, 3, 4, 5],
    "militaryLow":              [1, 2, 3, 4, 5],
    "militaryMed":              [1, 2, 3, 4, 5],
    "militaryHigh":             [1, 2, 3, 4, 5],
    "scienceCompass":           [1, 2, 3, 4, 5],
    "scienceTablet":            [1, 2, 3, 4, 5],
    "scienceCog":               [1, 2, 3, 4, 5],
    "guildMultiplierLow":       [1, 2, 3, 4, 5],
    "guildMultiplierMed":       [1, 2, 3, 4, 5],
    "builderMultiplier":        [1, 2, 3, 4, 5],
    "decoratorVictoryPoints":   [5, 6, 7, 8, 9],
}

WONDERS7_ALL_WONDERS = [
    "TheColossusOfRhodes",
    "TheLighthouseOfAlexandria",
    "TheTempleOfArtemisInEphesus",
    "TheHangingGardensOfBabylon",
    "TheStatueOfZeusInOlympia",
    "TheMausoleumOfHalicarnassus",
    "ThePyramidsOfGiza",
]

CANTSTOP_PARAMS = {
    "TWO_MAX":        [1, 2, 3, 4, 5],
    "THREE_MAX":      [2, 3, 4, 5, 6],
    "FOUR_MAX":       [4, 5, 6, 7, 8],
    "FIVE_MAX":       [6, 7, 8, 9, 10],
    "SIX_MAX":        [8, 9, 10, 11, 12],
    "SEVEN_MAX":      [10, 11, 12, 13, 14],
    "EIGHT_MAX":      [8, 9, 10, 11, 12],
    "NINE_MAX":       [6, 7, 8, 9, 10],
    "TEN_MAX":        [4, 5, 6, 7, 8],
    "ELEVEN_MAX":     [2, 3, 4, 5, 6],
    "TWELVE_MAX":     [1, 2, 3, 4, 5],
    "COLUMNS_TO_WIN": [2, 3, 4, 5, 6],
    "MARKERS":        [2, 3, 4, 5, 6],
}

GAME_PARAMS = {
    "ExplodingKittens": EXPLODING_KITTENS_PARAMS,
    "Dominion": DOMINION_PARAMS,
    "Wonders7": WONDERS7_PARAMS,
    "CantStop": CANTSTOP_PARAMS,
}


# ---------------------------------------------------------------------------
# API / Storage (same as before)
# ---------------------------------------------------------------------------
def submit_run(game, params, run_type="fast"):
    body = {"game": game, "params": params, "run_type": run_type, "timeout": 300000}
    try:
        resp = requests.post(API_URL, json=body,
                             headers={"Content-Type": "application/json"},
                             timeout=600)
        if resp.status_code != 200:
            print(f"  [ERROR] {resp.status_code}: {resp.text[:200]}")
            return {"score": 0}
        return resp.json()
    except requests.exceptions.ConnectionError:
        print("\n  [ERROR] Docker not running!\n")
        raise SystemExit(1)
    except Exception as e:
        print(f"  [ERROR] {e}")
        return {"score": 0}


def load_results():
    path = Path(RESULTS_FILE)
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_result(game, params, score, run_type="fast"):
    results = load_results()
    results.append({
        "game": game, "params": params, "score": score,
        "run_type": run_type, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    Path(RESULTS_FILE).write_text(json.dumps(results, indent=2))


def get_best(game):
    results = [r for r in load_results() if r["game"] == game and r["score"] > 0]
    if not results:
        return None
    return max(results, key=lambda r: r["score"])


# ---------------------------------------------------------------------------
# Optuna optimizer for one game
# ---------------------------------------------------------------------------
def optimize_game(game, n_trials):
    param_defs = GAME_PARAMS[game]

    print(f"\n{'='*60}")
    print(f"  Optuna: {game} — {n_trials} trials")
    print(f"{'='*60}\n")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name=game)

    # Seed with previous results
    past = [r for r in load_results()
            if r["game"] == game and r["score"] > 0 and r["run_type"] == "fast"]

    # Also load from cantstop_results.json if optimizing CantStop
    if game == "CantStop":
        cs_path = Path("cantstop_results.json")
        if cs_path.exists():
            cs_data = json.loads(cs_path.read_text())
            for r in cs_data:
                if r.get("score", 0) > 0:
                    past.append({"game": "CantStop", "params": r["params"],
                                 "score": r["score"], "run_type": r.get("run_type", "fast")})
    seeded = 0
    for r in past:
        trial_params = {}
        valid = True
        for name, values in param_defs.items():
            val = r["params"].get(name)
            if val in values:
                trial_params[name] = values.index(val)
            else:
                valid = False
                break
        if valid:
            study.enqueue_trial(trial_params)
            seeded += 1

    if seeded:
        def seed_objective(trial):
            params = {}
            for name, values in param_defs.items():
                idx = trial.suggest_int(name, 0, len(values) - 1)
                params[name] = values[idx]
            for r in past:
                match = True
                for k, v in params.items():
                    if not isinstance(v, list) and r["params"].get(k) != v:
                        match = False
                        break
                if match:
                    return r["score"]
            return 0.0
        study.optimize(seed_objective, n_trials=seeded)
        print(f"  Seeded with {seeded} previous results. Best: {study.best_value:.1f}\n")

    best_so_far = study.best_value if study.trials else 0
    start = time.time()

    def objective(trial):
        nonlocal best_so_far
        params = {}
        for name, values in param_defs.items():
            idx = trial.suggest_int(name, 0, len(values) - 1)
            params[name] = values[idx]

        # Handle list params
        if game == "Dominion":
            params["CARDS"] = random.sample(DOMINION_ALL_CARDS, 10)
        elif game == "Wonders7":
            n_wonders = random.randint(4, 7)
            params["wonders"] = random.sample(WONDERS7_ALL_WONDERS, n_wonders)

        result = submit_run(game, params)
        score = result.get("score", 0)
        save_result(game, params, score)

        n = trial.number + 1 - seeded
        elapsed = (time.time() - start) / 60
        if score > best_so_far:
            best_so_far = score
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}  *NEW BEST*  ({elapsed:.0f}m)")
        else:
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}  ({elapsed:.0f}m)")
        return score

    study.optimize(objective, n_trials=n_trials)

    # Decode best
    best = {}
    for name, values in param_defs.items():
        idx = study.best_params[name]
        best[name] = values[idx]

    elapsed = (time.time() - start) / 60
    print(f"\n  {game} done in {elapsed:.0f} minutes.")
    print(f"  Best score: {study.best_value:.1f}")
    print(f"  Params: {json.dumps(best, indent=4)}\n")


# ---------------------------------------------------------------------------
# Generate updated submission JSON
# ---------------------------------------------------------------------------
def generate_submission():
    """Pull best params from all_results.json + cantstop_results.json"""

    # Load Can't Stop results from its own file
    cs_path = Path("cantstop_results.json")
    cs_best = None
    if cs_path.exists():
        cs_results = json.loads(cs_path.read_text())
        cs_valid = [r for r in cs_results if r.get("score", 0) > 0]
        if cs_valid:
            cs_best = max(cs_valid, key=lambda r: r["score"])

    submission = {}
    total = 0

    print(f"\n{'='*60}")
    print(f"  Updated Submission Summary")
    print(f"{'='*60}\n")

    # Can't Stop
    if cs_best:
        submission["CantStop"] = cs_best["params"]
        print(f"  CantStop:          {cs_best['score']:7.1f}")
        total += cs_best["score"]

    # Other games
    for game in ["ExplodingKittens", "Dominion", "Wonders7"]:
        best = get_best(game)
        if best:
            submission[game] = best["params"]
            print(f"  {game:20s} {best['score']:7.1f}")
            total += best["score"]

    print(f"\n  {'TOTAL':20s} {total:7.1f} / 4000\n")

    Path("submission.json").write_text(json.dumps(submission, indent=4))
    print("  Updated submission.json\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    total_start = time.time()

    print("\n" + "="*60)
    print("  OVERNIGHT OPTIMIZATION RUN")
    print("  ExplodingKittens: 50, Dominion: 30, Wonders7: 30, CantStop: 25")
    print("="*60)

    for game, trials in TRIALS.items():
        optimize_game(game, trials)

    total_elapsed = (time.time() - total_start) / 3600
    print(f"\n  Total runtime: {total_elapsed:.1f} hours")

    generate_submission()
