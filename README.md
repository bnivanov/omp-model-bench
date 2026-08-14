# OMP Model Routing Benchmark

Task 1 closeout and Phase 1 roadmap for a bounded OMP × Pier/DeepSWE experiment on where to spend model intelligence in a coding-agent workflow: before implementation, at the mutation boundary, during implementation, after implementation, or on a stronger solo worker.

**Status (2026-08-14):** Task 1 is officially complete after seven canonical routes. Phase 1 is in progress (`1/3`) and now follows a frozen complexity ladder: empirically Very Easy → Medium → Very Hard. Task 2 begins with a fresh DS4 solo baseline.

## Research question

When is a low-cost Max worker sufficient, and when does a stronger planner, prewalker, live advisor, or independent reviewer produce enough value to justify its added cost and latency?

The v4 protocol freezes OMP `17.2.15`, Pier, DeepSWE, Max reasoning, one implementation worker, no implementation subagents, no hidden-verifier feedback, one repair at most, and a 5,400-second agent budget.

## Task 1 aggregate outputs

All seven routes passed all `122/122` P2P checks. Six reached binary reward `1.0` and `23/23` F2P checks. K3 prewalk → DS4 reached `22/23` F2P and partial score `0.9931034483`.

| Route | Validation | Reward / F2P | Runtime | Comparison cost | Cost basis |
|---|---|---:|---:|---:|---|
| DS4 solo | `VALID` | `1.0` / `23/23` | 25m 09s | $0.1047 | recorded |
| K3 plan-yolo → DS4 | `VALID` | `1.0` / `23/23` | 36m 49s | $1.3395 | DS4 recorded + K3 list-price estimate |
| K3 prewalk → DS4 | `VALID` | `0.0` / `22/23` | 18m 51s | $0.6111 | DS4 recorded + K3 list-price estimate |
| DS4 + K3 live advisor | `VALID_MODEL_TIMEOUT` | `1.0` / `23/23` | 1h 31m 50s | $10.3985 | DS4 recorded + K3 list-price estimate |
| DS4 → K3 review → DS4 repair | `VALID` | `1.0` / `23/23` | 46m 40s | $0.8096 | DS4 recorded + K3 list-price estimate |
| K3 plan-yolo → DS4 → K3 review → DS4 repair | `VALID` | `1.0` / `23/23` | 47m 05s | $1.7015 | DS4 recorded + K3 list-price estimate |
| DS4 + Luna live advisor | `VALID_MODEL_TIMEOUT` | `1.0` / `23/23` | 1h 31m 15s | $1.3179 | recorded |

K3 roles were recorded as `$0` by the gateway, so their comparison costs use the official Kimi K3 API rate card retrieved on 2026-08-12. They are estimates, not observed gateway charges. The machine-readable values and cost components are in [`benchmark/results/task1-summary.json`](benchmark/results/task1-summary.json).

## Task 1 findings

1. **DS4 solo dominated every other full-quality Task 1 route.** It reached full measured quality in 25m 09s for $0.1047 recorded cost. No augmented route improved measured quality; prewalk finished faster but scored lower.
2. **Intervention timing did not create uplift on a ceiling task.** Planning and controlled review also reached full quality, but cost about `12.79×` and `7.73×` the solo route respectively. Combining them cost `16.25×` as much.
3. **Prewalk traded quality for speed.** It was the fastest route at 18m 51s, but missed one F2P check and cost an estimated `5.84×` the solo route.
4. **Controlled review was operationally cleaner than live advising.** Review and one repair completed inside the budget. Both live-advisor routes exhausted the 5,400-second model budget.
5. **Live advising was a false economy on this task.** K3 and Luna advisor routes matched solo quality but took more than 90 minutes and cost about `99.31×` inferred and `12.59×` recorded relative to DS4 solo.
6. **The harness evidence is reusable.** Native handoffs, mutation-boundary switching, read-only review, one-repair enforcement, recursive advisor accounting, cancellation-safe snapshots, and independent patch equality all produced auditable evidence.

The detailed reviewed-run ledger, caveats, invalid-attempt classifications, accounting arithmetic, and harness lessons are in [`benchmark/FINDINGS.md`](benchmark/FINDINGS.md).

## Phase 1 complexity ladder

| Task | Target difficulty | Calibration | Status |
|---|---|---|---|
| Task 1 | Very Easy | Empirical: DS4 solo reached full measured quality in 25m 09s | Complete |
| Task 2 | Medium | Pre-run structural review: broad behavior but localized implementation surface | Next |
| Task 3 | Very Hard | Pre-run structural review: cross-layer implementation and integration surface | Queued |

“Very Easy” is a model-relative empirical label, not a claim that Task 1 is intrinsically trivial. Tasks 2 and 3 were selected before execution using instruction breadth, reference patch scope, subsystem coupling, state/algorithmic complexity, and regression surface. Their identities and fixtures remain private until each task closes to reduce benchmark contamination.

## Next run

Task 1 is closed, but Phase 1 remains active. The next authorized benchmark run starts the Medium Task 2 with a fresh DS4 solo baseline:

```sh
python3 benchmark/scripts/run_round1.py --run-one 2 ds4-solo
```

Run it only from a clean committed worktree after the focused tests and local readiness gate pass. Do not use `--force`. Review the new run contract, validation, result, logs, accounting, and both patch captures before authorizing another Task 2 condition.

## Repository map

- [`benchmark/EXPERIMENT.md`](benchmark/EXPERIMENT.md) — protocol, frozen decisions, and causal design
- [`benchmark/architectures.json`](benchmark/architectures.json) — machine-readable route definitions
- [`benchmark/agents/`](benchmark/agents/) — Pier/OMP adapters and treatment orchestration
- [`benchmark/scripts/`](benchmark/scripts/) — run, readiness, freeze, and validation tooling
- [`benchmark/tests/`](benchmark/tests/) — focused harness regression tests
- [`benchmark/SPECIAL_SAUCE.md`](benchmark/SPECIAL_SAUCE.md) — OMP feature-selection rationale
- [`ANNOUNCEMENTS.md`](ANNOUNCEMENTS.md) — ready-to-paste Discord and X drafts

## Safe-publication scope

This public snapshot contains the approach, orchestration code, focused tests, protocol, aggregate outputs, and reviewed findings. It intentionally excludes:

- credentials, provider tokens, and local authentication state;
- raw run transcripts, model session logs, stderr, and provider request metadata;
- hidden verifier output and per-test failure details;
- frozen DeepSWE task fixtures, solutions, and test patches;
- the pinned OMP executable and local vendor checkouts;
- exact Task 2/3 selector pins, unreleased task manifests, and future holdout identities.

The published freeze utility retains the original seeded candidate-pool logic; the exact three-task slot mapping is enforced privately while future task identities are embargoed.

Those exclusions prevent credential disclosure, hidden-test contamination, benchmark leakage, and redistribution of third-party binaries or task material. The public snapshot supports review of the method and aggregate evidence; exact replay requires separately authorized upstream checkouts, model access, and benchmark inputs.
