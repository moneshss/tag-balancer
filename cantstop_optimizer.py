"""
Can't Stop Optimizer for the 2026 Tabletop Games Balancing Competition

Prerequisites:
  1. Docker running: docker run -p 3000:3000 longhousedev/localapi
  2. pip install requests optuna

Usage:
  # Phase 1: Random search (50 trials) to map the landscape
  python cantstop_optimizer.py random --trials 50

  # Phase 2: Bayesian optimization (200 trials) to refine
  python cantstop_optimizer.py optimize --trials 200

  # Validate your best result with a medium run
  python cantstop_optimizer.py validate

  # Show the best parameters found so far
  python cantstop_optimizer.py best
"""

import argparse
import json
import time
import requests
import optuna
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_URL = "http://localhost:3000/api/run_game"
GAME = "CantStop"
RESULTS_FILE = "cantstop_results.json"

# Parameter definitions: name -> list of accepted values
PARAMS = {
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


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------
def submit_run(params: dict, run_type: str = "fast") -> dict:
    """Send a parameter set to the local API and return the response."""
    body = {
        "game": GAME,
        "params": params,
        "run_type": run_type,
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(API_URL, json=body, headers=headers, timeout=600)
        if resp.status_code != 200:
            error_body = resp.text
            print(f"[ERROR] {resp.status_code}: {error_body}")
            return {"score": 0, "error": error_body}
        return resp.json()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Can't connect to the local API.")
        print("Make sure Docker is running:")
        print("  docker run -p 3000:3000 longhousedev/localapi\n")
        raise SystemExit(1)
    except Exception as e:
        print(f"[ERROR] API request failed: {e}")
        return {"score": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Results storage
# ---------------------------------------------------------------------------
def load_results() -> list[dict]:
    path = Path(RESULTS_FILE)
    if path.exists():
        return json.loads(path.read_text())
    return []


def save_result(params: dict, score: float, run_type: str):
    results = load_results()
    results.append({
        "params": params,
        "score": score,
        "run_type": run_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    Path(RESULTS_FILE).write_text(json.dumps(results, indent=2))


def get_best(run_type: str | None = None) -> dict | None:
    results = load_results()
    if run_type:
        results = [r for r in results if r["run_type"] == run_type]
    if not results:
        return None
    return max(results, key=lambda r: r["score"])


# ---------------------------------------------------------------------------
# Random search
# ---------------------------------------------------------------------------
def random_search(n_trials: int):
    import random

    print(f"=== Random Search: {n_trials} trials ===\n")
    best_score = 0
    best_params = None

    for i in range(1, n_trials + 1):
        params = {name: random.choice(values) for name, values in PARAMS.items()}
        result = submit_run(params)
        score = result.get("score", 0)
        save_result(params, score, "fast")

        if score > best_score:
            best_score = score
            best_params = params

        status = "*NEW BEST*" if score == best_score and score > 0 else ""
        print(f"  [{i:3d}/{n_trials}]  score: {score:7.1f}  best: {best_score:7.1f}  {status}")

    print(f"\n  Best score from random search: {best_score:.1f}")
    print(f"  Params: {json.dumps(best_params, indent=4)}\n")


# ---------------------------------------------------------------------------
# Bayesian optimization with Optuna
# ---------------------------------------------------------------------------
def optimize(n_trials: int):
    print(f"=== Bayesian Optimization: {n_trials} trials ===\n")

    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(direction="maximize", study_name="cantstop")

    # Seed with previous results so Optuna knows what's been tried
    past = load_results()
    seeded = 0
    for r in past:
        if r["score"] > 0 and r["run_type"] == "fast":
            trial_params = {}
            for name, values in PARAMS.items():
                val = r["params"].get(name)
                if val in values:
                    trial_params[name] = values.index(val)
                else:
                    break
            else:
                study.enqueue_trial(trial_params)
                seeded += 1
    if seeded:
        # Run the seeded trials silently to teach Optuna
        def seed_objective(trial):
            params = {}
            for name, values in PARAMS.items():
                idx = trial.suggest_int(name, 0, len(values) - 1)
                params[name] = values[idx]
            # Look up the score from past results
            for r in past:
                if all(r["params"].get(k) == v for k, v in params.items()):
                    return r["score"]
            return 0.0
        study.optimize(seed_objective, n_trials=seeded)
        print(f"  Seeded Optuna with {seeded} previous results.")
        print(f"  Best from history: {study.best_value:.1f}\n")

    best_so_far = study.best_value if study.trials else 0

    def objective(trial: optuna.Trial) -> float:
        nonlocal best_so_far
        params = {}
        for name, values in PARAMS.items():
            idx = trial.suggest_int(name, 0, len(values) - 1)
            params[name] = values[idx]

        result = submit_run(params)
        score = result.get("score", 0)
        save_result(params, score, "fast")

        n = trial.number + 1 - seeded
        if score > best_so_far:
            best_so_far = score
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}  *NEW BEST*")
        else:
            print(f"  [{n:3d}/{n_trials}]  score: {score:7.1f}  best: {best_so_far:7.1f}")

        return score

    study.optimize(objective, n_trials=n_trials)

    # Decode best params back to actual values
    best = {}
    for name, values in PARAMS.items():
        idx = study.best_params[name]
        best[name] = values[idx]

    print(f"\n  Best score: {study.best_value:.1f}")
    print(f"  Params: {json.dumps(best, indent=4)}\n")
    return best


# ---------------------------------------------------------------------------
# Validate best with a medium run
# ---------------------------------------------------------------------------
def validate():
    best = get_best()
    if not best:
        print("No results found yet. Run random or optimize first.")
        return

    params = best["params"]
    print(f"=== Validating best params (medium run) ===")
    print(f"  Best fast score was: {best['score']:.1f}")
    print(f"  Running medium (360 matchups)... this will take a while.\n")

    result = submit_run(params, run_type="medium")
    score = result.get("score", 0)
    save_result(params, score, "medium")

    print(f"  Medium run score: {score:.1f}")
    print(f"  Params: {json.dumps(params, indent=4)}\n")


# ---------------------------------------------------------------------------
# Show best
# ---------------------------------------------------------------------------
def show_best():
    for rt in ["fast", "medium"]:
        best = get_best(rt)
        if best:
            print(f"  Best ({rt}): {best['score']:.1f}  @ {best['timestamp']}")
            print(f"    {json.dumps(best['params'])}")
    total = load_results()
    print(f"\n  Total evaluations: {len(total)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Can't Stop Optimizer")
    parser.add_argument("command", choices=["random", "optimize", "validate", "best"])
    parser.add_argument("--trials", type=int, default=50, help="Number of trials")
    args = parser.parse_args()

    if args.command == "random":
        random_search(args.trials)
    elif args.command == "optimize":
        optimize(args.trials)
    elif args.command == "validate":
        validate()
    elif args.command == "best":
        show_best()
