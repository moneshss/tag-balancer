"""
Optimizer for Exploding Kittens, Dominion, and 7 Wonders
Run sequentially overnight to get baseline scores for all 3 remaining games.

Prerequisites:
  1. Docker running: docker run -p 3000:3000 longhousedev/localapi
  2. pip install requests optuna

Usage:
  # Run all 3 games with random search (recommended overnight run)
  python remaining_games_optimizer.py random-all --trials 20

  # Run a single game
  python remaining_games_optimizer.py random --game ExplodingKittens --trials 20
  python remaining_games_optimizer.py random --game Dominion --trials 20
  python remaining_games_optimizer.py random --game Wonders7 --trials 20

  # Optimize a single game with Bayesian optimization
  python remaining_games_optimizer.py optimize --game ExplodingKittens --trials 30

  # Show best results across all games
  python remaining_games_optimizer.py best
"""

import argparse
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

# ---------------------------------------------------------------------------
# Game definitions
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


# ---------------------------------------------------------------------------
# Random param generation
# ---------------------------------------------------------------------------
def random_params(game: str) -> dict:
    if game == "ExplodingKittens":
        return {k: random.choice(v) for k, v in EXPLODING_KITTENS_PARAMS.items()}

    elif game == "Dominion":
        params = {k: random.choice(v) for k, v in DOMINION_PARAMS.items()}
        cards = random.sample(DOMINION_ALL_CARDS, 10)
        params["CARDS"] = cards
        return params

    elif game == "Wonders7":
        params = {k: random.choice(v) for k, v in WONDERS7_PARAMS.items()}
        n_wonders = random.randint(4, 7)
        wonders = random.sample(WONDERS7_ALL_WONDERS, n_wonders)
        params["wonders"] = wonders
        return params

    else:
        raise ValueError(f"Unknown game: {game}")


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------
def submit_run(game: str, params: dict, run_type: str = "fast") -> dict:
    """Send a parameter set to the local API and return the response."""
    body = {
        "game": game,
        "params": params,
        "run_type": run_type,
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(API_URL, json=body, headers=headers, timeout=600)
        if resp.status_code != 200:
            error_body = resp.text
            print(f"  [ERROR] {resp.status_code}: {error_body[:200]}")
            return {"score": 0, "error": error_body}
        return resp.json()
    except requests.exceptions.ConnectionError:
        print("\n  [ERROR] Can't connect to the local API.")
        print("  Make sure Docker is running:")
        print("    docker run -p 3000:3000 longhousedev/localapi\n")
        raise SystemExit(1)
    except Exception as e:
        print(f"  [ERROR] API request failed: {e}")
        return {"score": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Results storage (one file, tagged by game)
# ---------------------------------------------------------------------------
def load_results() -> list[dict]:
    path = Path(RESULTS_FILE)
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_result(game: str, params: dict, score: float, run_type: str):
    results = load_results()
    results.append({
        "game": game,
        "params": params,
        "score": score,
        "run_type": run_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    Path(RESULTS_FILE).write_text(json.dumps(results, indent=2))


def get_best(game: str, run_type: str | None = None) -> dict | None:
    results = [r for r in load_results() if r["game"] == game]
    if run_type:
        results = [r for r in results if r["run_type"] == run_type]
    if not results:
        return None
    return max(results, key=lambda r: r["score"])


# ---------------------------------------------------------------------------
# Random search
# ---------------------------------------------------------------------------
def random_search(game: str, n_trials: int):
    print(f"\n{'='*60}")
    print(f"  Random Search: {game} — {n_trials} trials")
    print(f"{'='*60}\n")

    best_score = 0
    best_params = None

    for i in range(1, n_trials + 1):
        params = random_params(game)
        result = submit_run(game, params)
        score = result.get("score", 0)
        save_result(game, params, score, "fast")

        if score > best_score:
            best_score = score
            best_params = params

        tag = "*NEW BEST*" if score == best_score and score > 0 else ""
        print(f"  [{i:3d}/{n_trials}]  score: {score:7.1f}  best: {best_score:7.1f}  {tag}")

    print(f"\n  Best {game} score: {best_score:.1f}")
    if best_params:
        # Print compact version (skip long lists)
        compact = {k: v for k, v in best_params.items() if not isinstance(v, list)}
        print(f"  Params: {json.dumps(compact, indent=4)}")
        for k, v in best_params.items():
            if isinstance(v, list):
                print(f"  {k}: {v}")
    print()
    return best_score, best_params


# ---------------------------------------------------------------------------
# Bayesian optimization (for games without list params)
# ---------------------------------------------------------------------------
def optimize(game: str, n_trials: int):
    if game == "Dominion":
        param_defs = DOMINION_PARAMS
    elif game == "ExplodingKittens":
        param_defs = EXPLODING_KITTENS_PARAMS
    elif game == "Wonders7":
        param_defs = WONDERS7_PARAMS
    else:
        raise ValueError(f"Unknown game: {game}")

    print(f"\n{'='*60}")
    print(f"  Bayesian Optimization: {game} — {n_trials} trials")
    print(f"{'='*60}\n")

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", study_name=game)

    # Seed with previous results
    past = [r for r in load_results() if r["game"] == game and r["score"] > 0 and r["run_type"] == "fast"]
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
                if all(r["params"].get(k) == v for k, v in params.items()
                       if not isinstance(v, list)):
                    return r["score"]
            return 0.0
        study.optimize(seed_objective, n_trials=seeded)
        print(f"  Seeded with {seeded} previous results. Best: {study.best_value:.1f}\n")

    best_so_far = study.best_value if study.trials else 0

    def objective(trial):
        nonlocal best_so_far
        params = {}
        for name, values in param_defs.items():
            idx = trial.suggest_int(name, 0, len(values) - 1)
            params[name] = values[idx]

        # Handle list params with random sampling (Optuna optimizes the rest)
        if game == "Dominion":
            params["CARDS"] = random.sample(DOMINION_ALL_CARDS, 10)
        elif game == "Wonders7":
            n_wonders = random.randint(4, 7)
            params["wonders"] = random.sample(WONDERS7_ALL_WONDERS, n_wonders)

        result = submit_run(game, params)
        score = result.get("score", 0)
        save_result(game, params, score, "fast")

        n = trial.number + 1 - seeded
        if score > best_so_far:
            best_so_far = score
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}  *NEW BEST*")
        else:
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}")
        return score

    study.optimize(objective, n_trials=n_trials)

    best = {}
    for name, values in param_defs.items():
        idx = study.best_params[name]
        best[name] = values[idx]

    print(f"\n  Best score: {study.best_value:.1f}")
    print(f"  Params: {json.dumps(best, indent=4)}\n")
    return best


# ---------------------------------------------------------------------------
# Show best across all games
# ---------------------------------------------------------------------------
def show_best():
    games = ["CantStop", "ExplodingKittens", "Dominion", "Wonders7"]
    total = 0
    print(f"\n{'='*60}")
    print("  Best scores across all games")
    print(f"{'='*60}\n")

    for game in games:
        best = get_best(game)
        if best:
            print(f"  {game:20s}  {best['score']:7.1f}  ({best['run_type']})  @ {best['timestamp']}")
            total += best["score"]
        else:
            print(f"  {game:20s}  ---  (no results)")

    print(f"\n  {'TOTAL':20s}  {total:7.1f} / 4000")

    # Also count from cantstop_results.json if it exists
    cs_path = Path("cantstop_results.json")
    if cs_path.exists():
        cs_results = json.loads(cs_path.read_text())
        cs_valid = [r for r in cs_results if r.get("score", 0) > 0]
        if cs_valid:
            cs_best = max(cs_valid, key=lambda r: r["score"])
            existing = get_best("CantStop")
            if not existing or cs_best["score"] > existing["score"]:
                print(f"\n  Note: cantstop_results.json has a better CantStop score: {cs_best['score']:.1f}")
                adjusted = total - (existing["score"] if existing else 0) + cs_best["score"]
                print(f"  Adjusted total: {adjusted:.1f} / 4000")

    all_results = load_results()
    print(f"\n  Total evaluations in {RESULTS_FILE}: {len(all_results)}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remaining Games Optimizer")
    parser.add_argument("command", choices=["random", "random-all", "optimize", "best", "test"])
    parser.add_argument("--game", choices=["ExplodingKittens", "Dominion", "Wonders7"])
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()

    if args.command == "test":
        print("=== Testing all 3 games with 1 trial each ===\n")
        for game in ["ExplodingKittens", "Dominion", "Wonders7"]:
            params = random_params(game)
            print(f"  {game}: ", end="", flush=True)
            result = submit_run(game, params)
            score = result.get("score", 0)
            if score > 0:
                print(f"OK! score={score:.1f}")
            else:
                print(f"FAILED — {result}")
        print("\n  If all 3 say OK, you're good to run random-all.\n")

    elif args.command == "random-all":
        start = time.time()
        for game in ["ExplodingKittens", "Dominion", "Wonders7"]:
            random_search(game, args.trials)
        elapsed = (time.time() - start) / 3600
        print(f"  Total time: {elapsed:.1f} hours")
        show_best()

    elif args.command == "random":
        if not args.game:
            print("Error: --game required for 'random' command")
            raise SystemExit(1)
        random_search(args.game, args.trials)

    elif args.command == "optimize":
        if not args.game:
            print("Error: --game required for 'optimize' command")
            raise SystemExit(1)
        optimize(args.game, args.trials)

    elif args.command == "best":
        show_best()
