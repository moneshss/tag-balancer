# TAG Balancing Competition 2026

Entry for the [Tabletop Games Balancing Competition 2026](https://balance-competition.tabletopgames.ai/), treating game balancing as a black-box optimisation problem. The goal: tune parameters for four tabletop games - Can't Stop, 7 Wonders, Dominion, and Exploding Kittens - to maximise a combined balance score (max 4000).

**Username:** moneshss  
**Best score:** 3508 pts (submission #11 - "combined")  
**Setup:** Docker (`longhousedev/localapi`) on localhost, Python scripts, Intel Iris XE laptop

---

## Approach

### Phase 1 - Random Search & Bayesian Optimisation (23-25 Aug)

Started with simple random parameter sampling across all four games to map out the landscape, then fed those results into Optuna (Bayesian optimisation) to try to refine them.

**What worked:** Random search found strong initial configs for 7 Wonders (983.3), Dominion (974.6), and Can't Stop (962.0). Optuna improved Can't Stop slightly (957→962).

**What didn't:** Optuna completely failed on Exploding Kittens - 50 trials, zero improvement. EK has 14 parameters and extreme score noise, which breaks Bayesian optimisation's statistical model.

| Script | Purpose |
|---|---|
| `cantstop_optimizer.py` | Random search + Optuna for Can't Stop |
| `remaining_games_optimizer.py` | Random search + Optuna for EK, Dominion, 7 Wonders |
| `overnight_optimizer.py` | Optuna on all 4 games, seeded from prior results |

### Phase 2 - Hill Climbing (27-29 Aug)

Switched to a simpler but more robust approach: start from the best known params, test every value for each parameter one at a time, keep improvements. Used a screen-then-confirm pattern (1 run to screen, 2 more runs to confirm) to filter out the massive noise in fast evaluations.

This became the core optimisation method. Each game got its own hill climbing script, run overnight.

| Script | Game | Runtime | Key findings |
|---|---|---|---|
| `hillclimb_ek.py` | Exploding Kittens | ~14 hours | nCardsPerPlayer 15→5, ATTACK 10→4, +108 avg pts |
| `hillclimb_7w.py` | 7 Wonders | ~15 hours | scienceCog 2→1, rawMaterialHigh 5→2, wonder swap |
| `hillclimb_dom.py` | Dominion | ~25 hours | SILVER_SUPPLY 30→10, LABORATORY→LIBRARY swap |
| `hillclimb_cs.py` | Can't Stop | ~9 hours | FOUR_MAX 5→4 (only improvement found) |

`quick_7w_dom.py` was an additional random search for 7 Wonders and Dominion cards - found nothing, confirming diminishing returns.

### Phase 3 - EK Random Restarts (29-30 Aug)

EK was still the weakest game (~794 averaged). The hill climber had only explored one local optimum. Random restarts generate fresh starting configs and hill climb each one, hoping to find a better basin.

Screened 25 random configs, hill climbed the top 3. The best (Start 1) reached **810.2 averaged** - a different config from the original but converging on the same key values (nCardsPerPlayer=7, FAVOR=10, RAINBOWCAT=6).

| Script | Purpose |
|---|---|
| `hillclimb_ek_restarts.py` | Phase 1 screening + Phase 2 hill climbing from top 3 starts |

### Phase 4 - Fresh Hill Climb & Pair Perturbation (30-31 Aug)

Two scripts running in parallel on separate Docker containers:

**Fresh hill climb** (`hillclimb_ek_fresh.py`): Re-ran hill climbing from the restart winner with a different random parameter order and expanded nCardsPerPlayer range (added 4, 6, 8, 9 which had never been tested). Found TACOCAT 8→6 for **815.9 averaged**.

**Pair perturbation** (`ek_pair_perturb.py`): Instead of changing one parameter at a time, randomly changes two parameters simultaneously. This finds improvements invisible to hill climbing - where neither change alone helps but the combination does. Found SEETHEFUTURE 3→6 + MELONCAT 1→5 together for **829.1 averaged** (+18.9 over starting point). This was the single biggest EK improvement from any method.

### Best Config - "combined" (3508 pts)

The strongest submission stacked both Phase 4 findings: TACOCAT=6 from the fresh hill climb and SEETHEFUTURE=6 + MELONCAT=5 from pair perturbation. Neither improvement alone beat the restart winner on the leaderboard, but combined they produced the highest score. The full parameter set is in [`submissions/11_combined.json`](submissions/11_combined.json).

---

## Submissions

All submission JSONs are in the [`submissions/`](submissions/) folder.

| # | Name | Score | Date | What changed |
|---|---|---|---|---|
| 1 | random run | 3437 | 24 Aug | Initial params from random search + Optuna |
| 2 | 2nd run | 3424 | 24 Aug | Same params, different evaluation roll |
| 3 | exploding kittens | 3471 | 27 Aug | Hill-climbed EK params |
| 4 | 7wonders | 3477 | 28 Aug | + Hill-climbed 7W params |
| 5 | dominion | 3479 | 29 Aug | + Hill-climbed Dominion params |
| 6 | cant stop | 3505 | 30 Aug | + Hill-climbed Can't Stop (FOUR_MAX 5→4) |
| 7 | kitten climb | 3506 | 30 Aug | EK restart winner (Start 1, 810.2 avg) |
| 8 | kitten climb | 3504 | 30 Aug | Same as #7, accidental double submit |
| 9 | tacocat | 3503 | 31 Aug | Fresh hill climb EK (TACOCAT 8→6) |
| 10 | perturbation | 3499 | 31 Aug | Pair perturbation EK (STF=6, MELON=5) |
| 11 | combined | 3508 ★ | 31 Aug | Perturbation + TACOCAT=6 combined |
| 12 | perturb | - | 31 Aug | Same as #10, not processed before close |

---

## Key Learnings

**Fast-run noise is brutal.** Fast evaluations (36 matchups) have ±200 point variance. Single-shot scores are nearly meaningless - a score of 962 can average down to 917 over 3 runs. The screen-then-confirm pattern was essential for filtering false positives.

**Hill climbing > Bayesian optimisation for noisy spaces.** Optuna failed completely on EK (14 params, high noise). Hill climbing with averaging found +108 points. Sometimes simple wins.

**Pair perturbation finds what hill climbing can't.** Single-parameter hill climbing can't discover improvements that require changing two params together. The STF+MELON pair perturbation found +18.9 points that no amount of hill climbing would have uncovered.

**Independent convergence = confidence.** Multiple random restarts converging on the same values (nCardsPerPlayer=7, TACOCAT=8, RAINBOWCAT=6) is strong evidence those values are genuinely optimal, not noise artifacts.

**Can't Stop's parameter space is a minefield.** Almost every parameter change outside a narrow window produces score 0 (timeout/crash). This made hill climbing painfully slow but also confirmed the Optuna solution was already near-optimal.

---

## Results Data

| File | Contents |
|---|---|
| `cantstop_results.json` | Can't Stop random search + Optuna results |
| `all_results.json` | All games - random search, Optuna, hill climbing results |
| `ek_restart_results.json` | EK random restart screening + hill climbing |
| `ek_fresh_results.json` | Fresh EK hill climb from restart winner |
| `ek_perturb_results.json` | EK pair perturbation search |

---

## Running Locally

Start the game API in one terminal:
```bash
docker run -p 3000:3000 longhousedev/localapi
```

In a second terminal, run any of the optimisation scripts:
```bash
# Hill climb a specific game
python hillclimb_ek.py --rounds 3
python hillclimb_7w.py --rounds 3
python hillclimb_dom.py --rounds 3
python hillclimb_cs.py --rounds 3

# EK random restarts (screen 25 configs, hill climb top 3)
python hillclimb_ek_restarts.py --port 3000

# Fresh hill climb from a known good starting point
python hillclimb_ek_fresh.py --port 3000 --rounds 3

# Pair perturbation search (runs for a fixed time limit)
python ek_pair_perturb.py --port 3000 --hours 7
```

To run two scripts in parallel, start a second Docker container on a different port:
```bash
# Terminal 3
docker run -p 3001:3000 longhousedev/localapi

# Terminal 4
python ek_pair_perturb.py --port 3001 --hours 7
```

All scripts save results after every trial, so they can be interrupted safely and progress is never lost.
