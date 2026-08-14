# OMP × Pier Benchmark — Canonical Experiment

Status: **Task 3 DS4 baseline complete (ceiling); Phase 1 DS4 baselines
complete (`3/3`); Task 2 controlled review is the next authorized run**.

## 1. Decision we are trying to make

This benchmark is not trying to rank coding models in the abstract. It is trying
to derive a practical, low-cost OMP routing policy:

> For DS4 and K3, what is the cheapest reliable route: direct execution or
> injecting K3 intelligence before, during, or after DS4 implementation?

The focal worker is DS4 Flash. The experiment asks where extra intelligence has
the highest marginal value:

1. **No intervention** — DS4 or K3 performs the task alone.
2. **Before mutation** — native K3 `plan_yolo` or native K3 `prewalk` hands off
   to DS4.
3. **During execution** — DS4 implements with native K3 advisor.
4. **After execution** — DS4 implements, K3 reviews read-only, and DS4 gets
   exactly one repair process.

The output is a routing/escalation policy and Pareto frontier, not a publication-
grade leaderboard.

## 2. Frozen stack

- OMP: `v17.2.15` (`06aecdd51f07e689e970ceaa180abe2be0c14bbb`)
- Pier: `0daf53d3599e58c4506cf0bcff5e12c77dc282d2`
- DeepSWE: `435ee89ec2f2e2289f33b0da4f992f0b7b7266b9`
- Pier local patch: port `4000` added to Squid `Safe_ports`
- Gateway: host auth gateway on `http://host.docker.internal:4000`
- Trial concurrency: `1`
- Implementation subagents: forbidden
- Web search: disabled
- Model thinking: `max` for every benchmark model role unless a later frozen
  experiment explicitly changes that axis

## 3. Models

- focal worker: `deepseek/deepseek-v4-flash`
- fixed smart helper and direct comparator: `kimi-code/k3`
- exploratory advisor-only comparator: `openai-codex/gpt-5.6-luna`

Luna solo, Sol, and prompt-scaffold arms are outside the active benchmark. Luna
appears only in the separately identified `ds4-luna-advisor` diagnostic. Adding
another model or OMP behavior requires a new condition ID and a
decision-relevant hypothesis.

## 4. Current evidence

One real DeepSWE DS4 run has completed under the pre-v2 harness:

- condition: `r1-t01-A`
- task: `datacurve/tengo-callable-instance-isolation`
- infrastructure: valid; no exception; model patch collected and pristine
  verifier completed
- binary reward: `0`
- F2P: `22/23`
- P2P: `122/122`
- partial: `0.993103448275862`
- cost: `$0.129369296`
- duration: approximately `44m 56s`
- patch size: `30,295` bytes

It is retained as a **legacy reference**, not automatically treated as the
causal v4 baseline because the new harness makes treatment/tool/config state
explicit. The hidden failing verifier case must never be placed in any future
planner, worker, advisor, reviewer, repair prompt, or committed review brief.

## 5. Canonical treatment semantics

### `solo`

One worker model receives the original DeepSWE instruction and performs the
implementation. No task/subagent tool.


### `plan_yolo`

The helper model is the active model. OMP native `--plan-yolo` forces read-only
plan mode, auto-approves the plan, and switches to the focal worker via
`--plan-yolo-into` for implementation. The target selector includes `:max`
explicitly so the handoff does not silently lose the benchmark thinking level.

There is deliberately **no separate `plan` treatment**. In earlier drafts, `plan`
was only a shorthand name for this exact native plan-yolo mechanism. Keeping both
would duplicate the same condition and create a false comparison. All future run
configs and metadata use `treatment=plan_yolo`.

### `prewalk`

The helper/prewalker starts active with normal investigative/implementation tools
plus `todo`. OMP native `--prewalk` injects its deep-plan/todo nudge, allows the
helper to inspect the repo, and switches one-way to the focal worker at the
first real edit/write after the prewalk gate. The target selector includes
`:max` explicitly. OMP then injects its consistency/scope/full-module-
verification checklist.

This is intentionally distinct from plan-yolo: plan-yolo is a formal read-only
planning phase; prewalk is a stronger-model reconnaissance/commitment phase that
hands off at the mutation boundary.

### `advisor`

DS4 remains the implementation worker. OMP native `--advisor` runs a separate
advisor agent using `modelRoles.advisor`. Benchmark config freezes:

- `advisor.syncBacklog: 1`
- `advisor.immuneTurns: 3`
- `advisor.subagents: false`
- default advisor investigative tools (`read`, `grep`, `glob`)

This tests intelligence injected **during** execution without creating a second
implementation worker.

### `review`

1. DS4 implements.
2. Wrapper captures the candidate patch against the pristine task commit.
3. Reviewer receives only the original task + candidate patch and is hard-
   limited to `read,grep,glob`.
4. Reviewer returns findings only.
5. DS4 receives original task + findings and gets exactly one repair process.

Native OMP `/review` is deliberately not used because frozen OMP's headless
review path itself creates a reviewer subagent, which would confound the timing
experiment.

### `plan_yolo_review`

Native `plan_yolo` → DS4, then the same read-only reviewer → exactly one DS4 repair.
Run only if plan-yolo and/or review individually justify their cost.

### `prewalk_review`

Native K3 `prewalk` → DS4, then the same independent read-only K3 reviewer →
exactly one fresh DS4 repair. This cross was registered later at operator
request despite prewalk's failed task-1 progression gate. It is an exploratory
interaction check, not an adaptively selected finalist.

## 6. OMP “special sauce” decisions

Promote into the pilot:

- **prewalk** — yes; directly tests whether K3 is most valuable during
  reconnaissance until the mutation boundary.

Already represented:

- **plan-yolo** — yes, first-class `plan_yolo` treatment.
- **advisor** — yes, `advisor` treatment.
- **review** — yes, but controlled externally to keep timing causal.

Do not include in the initial benchmark:

- **orchestrate** — explicitly a multi-agent orchestration contract and therefore
  violates the no-fan-out experiment design.
- **workflowz** — deterministic multi-subagent workflow requiring `eval` + `task`;
  same problem, with even more orchestration surface.
- **goal / guided-goal** — persistent autonomous session objective. Useful for
  long-horizon interactive work, but changes session/persistence semantics rather
  than cleanly isolating where intelligence is spent on one DeepSWE task.
- **loop** — re-submits a prompt after yields. This effectively buys repeated
  attempts, confounds cost/quality, and can create runaway spend.
- **vibe** — explicitly out of scope by operator choice.
- **green / CI-green** — oriented around repeatedly iterating on branch CI and
  remote state; DeepSWE's hidden pristine verifier must remain post-hoc and must
  not become a feedback loop.

## 7. Adaptive three-task Phase 1 — do not run a full factorial

### Task 1 route screen — complete

Task 1 exercised seven canonical routes and closed the harness/treatment screen.
Every accepted run produced an auditable verifier result, stage-attributed usage,
the expected model handoff or advisor/reviewer evidence, and no hidden-test
feedback. K3 solo and prewalk plus review were retired unrun for Task 1.

### Frozen complexity ladder

Phase 1 contains exactly three tasks:

1. **Task 1 — Very Easy (empirical):** DS4 solo reached full measured quality in
   `25m 09s`. This is a model-relative outcome label, not a claim that the task
   is intrinsically trivial.
2. **Task 2 — Medium (pre-run structural review):** broad behavior inside a
   localized implementation surface. DS4 solo is a valid near-miss: reward `0.0`,
   F2P `78/79`, P2P `16715/16715`, `23m 28s`, `$0.0820814176` recorded.
3. **Task 3 — Very Hard (pre-run structural review):** a broad cross-layer
   implementation with substantial integration and regression surface.

Tasks 2 and 3 were selected before execution using instruction breadth,
reference patch files/hunks/churn, subsystem coupling, state and algorithmic
complexity, integration depth, and regression surface. Exact identities are
frozen in the private pilot manifest and withheld publicly until each task closes.
The selector preserves the seeded, repository-diverse remainder as holdouts.

### Adaptive progression

Each new task begins with DS4 solo. Review its contract, validation, aggregate
quality, accounting, logs, and both patch captures before authorizing another
condition. Task 1's ceiling result does not justify replaying every route on
Tasks 2 and 3; spend only on routes that resolve a remaining routing decision.
Task 2's DS4 baseline is reviewed. Remaining Task 2 routes are registered but
not authorized. The next authorized run is the Task 3 DS4 solo baseline.

`plan_yolo_review` has a canonical Task 1 result. `prewalk_review` remains
registered despite prewalk's failed Task 1 progression gate, but is not
automatically authorized on later tasks. Do not add advisor/review or
planner/advisor crosses: canonical advisors are deadline-bound, and live advice
during K3 planning/prewalk would blur role timing and causal attribution.

## 8. Metrics

Capture per workflow:

- DeepSWE binary `reward`
- `partial`
- F2P total/passed
- P2P total/passed
- total workflow cost
- wall-clock duration
- input/output/cache tokens
- stage/role cost and tokens: worker, planner, prewalker, advisor, reviewer,
  repair
- helper interactions where available
- infrastructure validity / exception type

Derived:

- uplift vs DS4 solo
- incremental cost per quality point gained
- cost per successful task
- Pareto frontier
- routing advantage = equivalent-quality solo cost − augmented-DS4 cost
- orchestration inversion point: where helper overhead makes a stronger direct
  worker cheaper or faster for equal/better quality

Never collapse everything into an arbitrary weighted “quality + cost” score.

## 9. Reproducibility controls

- Scientific knobs belong in Pier `AgentConfig.kwargs`, so `config.json` and
  `lock.json` describe the condition.
- `OMP_BENCH_*` environment variables are infrastructure plumbing only.
- Same clean task snapshot, prompt, task environment, verifier, network policy,
  concurrency, timeout policy, and tool policy within a comparison.
- No implementation subagents.
- Reviewer cannot mutate.
- Exactly one post-review repair process.
- All magic keywords are disabled; prompt scaffolds are outside the active
  DS4/K3 condition set.
- Helper-role kwargs are treatment-specific: planner only for `plan_yolo` /
  `plan_yolo_review`, prewalker only for `prewalk`, advisor only for `advisor`,
  reviewer only for `review` / `plan_yolo_review`. Invalid mixtures fail before
  a model call.
- `orchestrate` and `workflowz` magic keywords explicitly disabled.
- Every model-handoff target includes the frozen thinking suffix (`:max`).
- Independent session directories per stage.
- Hidden verifier failures are evaluation-only and never become model input.
- Auth/transport/setup failures are infrastructure-invalid, not model failures.
- Do not overwrite historical run directories.

## 10. Progress and decision ledger

This section is the authoritative current-state reference. Update it whenever a
condition, gate, or frozen decision changes; do not create parallel status files.

### Current status

- Canonical condition IDs and scientific kwargs: `benchmark/architectures.json`
  schema v4.
- Active launcher: `benchmark/scripts/run_round1.py`; it writes only under
  `benchmark/runs/v4/`, passes every scientific knob through Pier
  `--agent-kwarg`, and refuses a dirty worktree.
- Active validator: `benchmark/scripts/validate_run.py`; it checks treatment
  stage/model layout, nested native-advisor evidence, advisor tool isolation,
  JSONL integrity, stderr capture, the v4 run contract, zero implementation
  spawns, stage/total accounting reconciliation, timeout classification, and
  equality between collected and independently captured patches.
- The macOS arm64 OMP 17.2.15 host runtime is pinned in
  `benchmark/bin/omp-darwin-arm64`; normal user OMP upgrades do not affect the
  benchmark.
- Seven task-1 conditions have canonical outcomes: DS4 solo, K3 plan-yolo → DS4,
  K3 prewalk → DS4, DS4 + K3 advisor, DS4 → K3 review → DS4 repair,
  K3 plan-yolo → DS4 → K3 review → DS4 repair, and exploratory DS4 + Luna
  advisor.
- DS4 solo, plan-yolo, controlled review, plan-yolo plus review, and both
  advisor patches reached full aggregate quality. Prewalk completed with partial
  `0.9931034483` and F2P `22/23`.
- K3 and Luna advisor conditions are canonical `VALID_MODEL_TIMEOUT` outcomes.
  K3 timed out while native advisor work drained after DS4's final response;
  Luna timed out while DS4 itself remained active.
- The instrumentation-invalid K3 advisor attempt and infrastructure-interrupted
  first controlled-review attempt remain excluded.
- Active scope is nine conditions: six DS4/K3 core routes, conditional
  `plan_yolo_review` and `prewalk_review` crosses, and one exploratory Luna
  advisor route. Luna solo, Sol, and `ultrathink` remain removed.
- Task 1 is officially closed; Task 2 DS4 solo is a reviewed near-miss; Task 3
  DS4 solo is a reviewed ceiling; Phase 1 DS4 baselines are complete at `3/3`.
  Remaining Task 3 routes stay registered but unauthorized.
- Phase 1 remains frozen as empirically Very Easy → Medium → Very Hard. The next
  authorized run is Task 2 `ds4-k3-review-ds4` to test recovery of the only
  remaining quality gap. No other Task 2 or Task 3 condition is authorized until
  that review passes artifact review.
- Historical `benchmark/results/round1-baseline.json` remains a legacy reference,
  not a causal v4 baseline.

### Frozen decisions

1. Phase 1 contains exactly three tasks in the frozen Very Easy → Medium → Very
   Hard order; future task identities remain private until their task closes.
2. No implementation subagents or second implementation worker.
3. Every model role and handoff uses `thinking=max`.
4. `plan_yolo` and `prewalk` remain separate mutation-boundary hypotheses.
5. Review is an independent read-only process followed by exactly one fresh DS4
   repair process; no native `/review`.
6. Hidden verifier results are post-hoc only.
7. `plan_yolo_review` was authorized only after controlled review completed
   validly; its Task 1 result does not justify an advisor cross.
8. `prewalk_review` is registered at operator request as a conditional
   interaction check despite prewalk failing its original progression gate.
9. Advisor/review and planner/advisor crosses are not registered because the
   advisors are deadline-bound and those combinations blur timing attribution.
10. New conditions must receive a unique condition ID, state one unresolved
    routing decision, declare a phase, and pass constructor/manifest validation
    before becoming runnable.
11. The canonical advisor outcomes receive no result-based retries.
12. Do not raise the timeout or alter advisor prompt, tools, synchronization,
    immunity, thinking, or model under an existing condition ID. Any such run is
    a separately named, non-comparable diagnostic.

### Local validation gate

Repeatable command:

```sh
~/AgentWork/bin/uv run --project vendor/pier --python 3.12 --frozen \
  python benchmark/scripts/check_v4_ready.py
```

- [x] Canonical condition manifest and runner kwargs agree.
- [x] Invalid treatment/helper/thinking combinations fail before a model call.
- [x] Candidate patch captures tracked, deleted, binary, and untracked files.
- [x] Repository is clean and frozen revisions/checksums match.
- [x] Per-role accounting and advisor de-duplication confirmed against the first
  treatment-specific output.
- [x] Plan-yolo and prewalk handoffs confirmed on their own smoke outputs.
- [x] Reviewer workspace identity confirmed on both canonical review outputs.
- [x] Gateway isolation confirmed by the network smoke; current advisor
  collected/final patch equality confirmed.

### Operator launch contract

Task 3's DS4 solo baseline is reviewed and closed as a valid ceiling. Remaining
Task 3 routes stay registered but must not be launched. Phase 1 DS4 baselines
are complete. The next authorized run returns to the Task 2 quality gap with
controlled review:

```sh
python3 benchmark/scripts/run_round1.py --run-one 2 ds4-k3-review-ds4
```

Expected canonical job directory: `benchmark/runs/v4/v4-t02-ds4-k3-review-ds4/`.
Never use `--force`. Launch only from a clean committed worktree after the
focused harness tests and repeatable local readiness gate pass. After the
command exits, inspect `run-contract.json`, `validation.json`, `result.json`,
Pier config/lock, every stage JSONL/stderr, accounting, and both patch captures
before authorizing any additional Task 2 condition.

### Change log

- 2026-08-12 — Sol Max review returned `NO-GO`: missing v4 runner plumbing,
  unfrozen dirty state, advisor double counting, incomplete candidate patches,
  insufficient reviewer isolation, fragile handoff attribution, and weak failure
  classification.
- 2026-08-12 — Remediation implemented: schema-v4 condition manifest and runner,
  treatment-aware validation, strict Max/advisor constructor controls,
  canonical model attribution, disjoint advisor accounting, complete temporary-
  index candidate patches, reviewer workspace invariant, per-stage stderr and
  exit-code capture.
- 2026-08-12 — Added repeatable no-model readiness validation and froze the
  operator/reviewer handoff: operator runs one exact command; reviewer inspects
  outputs before authorizing any next condition.
- 2026-08-12 — Before any v4 model call, the operator approved re-freezing OMP
  from 17.2.11 to 17.2.15 (`06aecdd51f07e689e970ceaa180abe2be0c14bbb`).
  Pinned Linux binaries and host broker/gateway must all report 17.2.15.
- 2026-08-13 — Pinned the macOS arm64 OMP 17.2.15 host executable in
  `benchmark/bin`, isolating benchmark broker/gateway services from normal OMP
  upgrades.
- 2026-08-13 — The task-1 DS4 + K3 advisor attempt reached the frozen
  5,400-second agent timeout. The attempt is excluded, the advisor arm is
  stopped, and nested `__advisor.jsonl` model/tool/accounting validation was
  corrected.
- 2026-08-13 — Added cancellation-safe final commit and independent patch
  capture so future agent timeouts preserve candidate artifacts while retaining
  their original timeout classification.
- 2026-08-13 — OMP stages now run in a recorded process group. On Pier
  cancellation the adapter stops that in-container group before snapshotting,
  preventing a detached `docker compose exec` process from mutating the
  workspace concurrently with final patch capture.
- 2026-08-13 — Reopened the advisor arm for exactly one pre-registered
  replacement run without changing its 5,400-second budget or scientific
  treatment. A clean deadline exhaustion is now a resource-bounded model
  outcome (`VALID_MODEL_TIMEOUT`), while any missing/mismatched artifact,
  attribution, accounting, stderr, or non-timeout exception remains
  infrastructure-invalid.
- 2026-08-13 — Deadline capture now detects stashes created during a cancelled
  stage. It restores exactly one unambiguous new stash before snapshotting and
  rejects ambiguous stash/working-tree combinations instead of certifying a
  potentially empty patch.
- 2026-08-13 — The exact advisor replacement reached the frozen deadline and
  was accepted as canonical `VALID_MODEL_TIMEOUT`: full aggregate quality,
  exact worker/advisor attribution and accounting, advisor-safe tools only,
  empty stderr, clean process-group cancellation, and matching final patches.
- 2026-08-13 — Narrowed the active benchmark to DS4 and K3. Removed Luna solo,
  Sol solo, and DS4 `ultrathink`; retained six core routes and conditional
  `plan_yolo_review`. Rejected prewalk/review and advisor crosses unless a future
  newly registered hypothesis independently justifies them.
- 2026-08-13 — Canonical controlled review and plan-yolo plus review both
  completed normally at full aggregate quality with exact accounting and
  matching patches. The first controlled-review attempt was archived as an
  infrastructure interruption before evaluation.
- 2026-08-13 — Added and ran exploratory DS4 + Luna native advisor. Its saved
  patch reached full aggregate quality at the frozen deadline; unlike K3, DS4
  itself was still active when cancellation began.
- 2026-08-13 — Audited all canonical task-1 accounting. Corrected prewalk values
  that had duplicated its single mixed-model transcript; no run artifact or
  quality result changed.
- 2026-08-13 — Registered conditional `prewalk_review` at operator request and
  retained `k3-solo` as the next authorized task-1 run.
- 2026-08-14 — Officially closed Task 1 after seven canonical routes. Retired
  K3 solo and prewalk plus review unrun for Task 1, froze Phase 1 as a three-task
  Very Easy → Medium → Very Hard ladder, and authorized only the Medium Task 2
  DS4 solo baseline as the next run.
- 2026-08-14 — Reviewed Task 2 DS4 solo as a valid near-miss (`78/79` F2P,
  `16715/16715` P2P, reward `0.0`, `23m 28s`, `$0.0820814176`). Left remaining
  Task 2 routes unauthorized and authorized only the Very Hard Task 3 DS4 solo
  baseline as the next run.
- 2026-08-14 — Reviewed Task 3 DS4 solo as a valid ceiling (`82/82` F2P, `2/2`
  P2P, reward `1.0`, `46m 56s` wall / `27m 00s` agent, `$0.0952155512`). Left
  remaining Task 3 routes unauthorized and authorized Task 2 controlled review
  as the next run to test recovery of the only remaining quality gap.

## 11. Review gate

The original pre-spend Sol Max gate is historical and was satisfied through the
bounded v4 remediations recorded above. Every new condition must now pass the
repeatable local readiness gate, focused harness tests, a clean committed
worktree, and the one-run-at-a-time operator contract. A completed paid run must
pass strict artifact validation before any queued condition is authorized.
