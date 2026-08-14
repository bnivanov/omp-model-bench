# Sol Max Review Brief — OMP × Pier Benchmark v4

## Reviewer role

You are the pre-spend technical reviewer for a controlled coding-agent benchmark.
Review the benchmark design, harness implementation, reproducibility, isolation,
and cost accounting. Do **not** solve the underlying DeepSWE task and do **not**
modify repository files during this review.

The objective, constraints, evidence, and requested decisions are specified here.
Do not respond with “what exactly are you trying to do?” If something remains
ambiguous, record it as a concrete finding and state the safest interpretation.

You may run read-only inspection commands (`git status`, `git diff`, `git log`,
`grep`, `find`, syntax checks, reading pinned source). Do not run benchmark trials
unless explicitly asked after this review.

Do not inspect historical hidden DeepSWE verifier failure details under
`benchmark/runs/**`. The aggregate legacy result in
`benchmark/results/round1-baseline.json` is sufficient. Hidden verifier feedback
must never become a hint for future planner/worker/advisor/reviewer/repair runs.

## Decision this project must answer

Derive a practical cost-vs-quality routing policy for OMP:

> For a coding task, when is a cheap Max worker sufficient; when is extra
> intelligence best spent before execution, up to the mutation boundary, during
> execution, or after execution; and when is augmentation a false economy versus
> routing the whole task directly to a stronger model?

The benchmark is not intended to publish a universal model leaderboard. It is a
bounded adaptive experiment to find the most efficient cost/value curve for this
operator's OMP usage.

## Frozen stack

- OMP `v17.2.15`, commit `06aecdd51f07e689e970ceaa180abe2be0c14bbb`
- Pier `0daf53d3599e58c4506cf0bcff5e12c77dc282d2`
- DeepSWE `435ee89ec2f2e2289f33b0da4f992f0b7b7266b9`
- Pier local networking patch: Squid `Safe_ports` permits local gateway port 4000
- one concurrent Pier trial
- web search disabled inside benchmark task agents
- no implementation subagents / no second implementation worker
- all benchmark model roles intended to run at `thinking=max`
- hidden verifier outcomes remain post-hoc evaluation only

Review behavior against these pinned versions, especially OMP 17.2.15, not the
current upstream main branch.

## Model set

- DS4: `deepseek/deepseek-v4-flash` — focal cheap worker
- Luna: `openai-codex/gpt-5.6-luna` — cheap/peer comparator
- K3: `kimi-code/k3` — fixed stronger helper / middle tier
- Sol Max: `openai-codex/gpt-5.6-sol` — expensive quality ceiling

Sol High/xhigh is intentionally outside the first pilot unless a later result
shows a decision-relevant gap that Max cannot resolve.

## Current empirical evidence

One real DS4 trial (`r1-t01-A`) completed under the older harness on
`datacurve/tengo-callable-instance-isolation`:

- infrastructure-valid, no exception
- binary reward `0`
- F2P `22/23`
- P2P `122/122`
- partial `0.993103448275862`
- cost `$0.129369296`
- duration about `44m56s`
- valid model patch and pristine DeepSWE verification

Treat this as a **legacy reference**, not automatically the causal v4 baseline,
because v4 makes treatment/tool/config state explicit. Do not inspect the hidden
failing test identity or message.

## Causal questions

1. What can DS4, Luna, K3, and Sol Max do alone at Max reasoning?
2. Does OMP `ultrathink` improve DS4 enough to be a near-zero-helper-cost default?
3. Does native OMP **plan-yolo** make a smart helper valuable strictly before
   implementation?
4. Does native OMP **prewalk** perform better by letting the smart helper own
   reconnaissance and commitment until the first real mutation?
5. Does a live K3 advisor improve DS4 enough to justify continuous helper overhead?
6. Can independent K3 final review plus exactly one DS4 repair cheaply rescue
   near-misses?
7. For intervention types that work, how smart does the helper need to be?
8. At what point is an augmented DS4 route dominated by K3 or Sol Max solo?

## Canonical treatments in v4

### `solo`
One worker receives the original DeepSWE task and implements it. No task/subagent
tool and no helper model.

### `solo` + `prompt_scaffold=ultrathink`
Same worker, but the initial user task contains the standalone lowercase magic
keyword `ultrathink`. Benchmark thinking is already fixed at Max, so this is
intended to isolate OMP's hidden careful-multi-step-reasoning notice rather than
buying a higher reasoning tier.

### `plan_yolo`
K3 is the active starting model. The harness invokes OMP native `--plan-yolo`,
which forces read-only plan mode, auto-approves the submitted plan, and switches
through `--plan-yolo-into deepseek/deepseek-v4-flash:max` for implementation.

This is the explicit v4 name. Earlier drafts called the same code path `plan`.
There is deliberately **no separate `plan` arm**, because it would duplicate the
same native OMP mechanism under another label.

### `prewalk`
K3 starts active with worker investigative/implementation tools plus `todo`.
Native `--prewalk` injects OMP's deep-plan/todo checkpoint and switches one-way to
`DS4:max` at the first qualifying edit/write after the gate. OMP then injects its
consistency/scope/verification checklist.

This differs causally from `plan_yolo`: the smart model is not forced into a
formal read-only plan phase and remains responsible through reconnaissance and
commitment up to the mutation boundary.

### `advisor`
DS4 remains the implementation worker. Native OMP `--advisor` runs K3 initially
through `modelRoles.advisor`. Freeze `syncBacklog=1`, `immuneTurns=3`, and
`subagents=false`; advisor stays investigative rather than becoming a second
implementer.

### `review`
DS4 implements first. The wrapper captures the candidate patch against the
pristine task commit. A separate K3 reviewer receives only original task + patch,
has `read,grep,glob`, and returns findings. DS4 then receives original task +
findings and gets exactly one repair process. Native OMP `/review` is intentionally
not used because its headless implementation introduces reviewer-subagent
orchestration and would confound the timing experiment.

### `plan_yolo_review`
Native `plan_yolo` → DS4 implementation → read-only K3 review → exactly one DS4
repair. This is conditional and should only run if plan-yolo and/or review alone
justify combining them.

## Special-sauce scope decisions

Included as decision-useful interventions:

- native plan-yolo
- native prewalk
- native advisor
- controlled independent review + one repair
- small ultrathink control

Excluded initially:

- vibe — explicit operator non-goal
- orchestrate — parallel multi-agent contract; violates no-fan-out design
- workflowz — deterministic multi-subagent eval/task workflow; same confound
- goal/guided-goal — changes persistent long-horizon session semantics rather
  than isolating intelligence allocation on one DeepSWE task
- loop — repeated submissions/attempts confound quality and cost and risk runaway
  spend
- CI-green — would turn hidden/post-hoc verification into iterative feedback

## Intended adaptive experiment

Do not recommend a full factorial unless there is an overwhelming validity reason.
The intended funnel is:

### Harness validation on one task

1. fresh v4 DS4 solo
2. K3 `plan_yolo` → DS4
3. K3 `prewalk` → DS4
4. DS4 + K3 advisor
5. DS4 → K3 review → DS4 one repair

Goal: verify model handoffs, tool isolation, final patch collection, DeepSWE
verification, stage attribution, and no hidden-test leakage.

### Solo frontier on two tasks

- DS4 solo
- Luna solo
- K3 solo
- Sol Max solo

### Cheap scaffold

- DS4 solo + ultrathink

### K3 intervention timing

- K3 plan-yolo → DS4
- K3 prewalk → DS4
- DS4 + K3 advisor
- DS4 → K3 review → one DS4 repair

### Conditional combinations/ladders

- `plan_yolo_review` only if component evidence makes it plausible
- advisor intelligence ladder only if advisor has value
- prewalk intelligence ladder only if prewalk has value
- repeat finalists/ties only

## Metrics

Per complete workflow capture:

- binary DeepSWE reward
- partial score
- F2P and P2P totals/passed
- total workflow cost
- wall-clock duration
- input/output/cache tokens
- per-role usage/cost: worker, planner, prewalker, advisor, reviewer, repair
- helper interactions where available
- infrastructure validity / exception type

Derived:

- uplift versus DS4 solo
- incremental cost per quality point
- cost per successful task
- Pareto frontier
- routing advantage versus equivalent-quality direct solo
- orchestration inversion point where helper overhead makes a stronger direct
  worker cheaper/faster for equal or better quality

Do not invent a weighted composite score that mixes cost and quality arbitrarily.

## Harness architecture to inspect

Read these before reaching a verdict:

1. `benchmark/EXPERIMENT.md`
2. `benchmark/SPECIAL_SAUCE.md`
3. `benchmark/PATCH_NOTES_V4.md`
4. `benchmark/agents/omp_pier.py`
5. `benchmark/agents/omp_deepswe.py`
6. `benchmark/results/round1-baseline.json`
7. `.omp/hooks/pre/benchmark-spawn-cap.ts`
8. `benchmark/patches/pier-gateway-port-4000.patch` if present
9. benchmark freeze/pin manifests found with `glob`
10. current `git status`, `git diff`, and recent benchmark-related commits
11. pinned OMP/Pier/DeepSWE source where needed to validate semantics

Do **not** open historical `benchmark/runs/**` verifier logs or hidden test output.

Architecture assumptions:

- `omp_pier.py` owns OMP install/gateway plumbing, one-process execution, JSONL
  parsing, and generic usage extraction.
- `omp_deepswe.py` owns scientific treatments and DeepSWE-specific controls.
- scientific knobs are Pier constructor kwargs so resolved Pier config/lock
  records the condition.
- each OMP stage gets a separate session directory.
- plan-yolo/prewalk helper-to-worker usage is split from recorded provider/model
  events inside the one OMP process.
- advisor usage is added from advisor session JSONL.
- reviewer and repair are fresh OMP processes in the same Pier task sandbox.
- candidate review patch is captured against the pristine task commit.

## Required technical scrutiny

Validate, do not merely summarize:

1. **Treatment naming and plumbing** — are `plan_yolo`, `prewalk`, `advisor`,
   `review`, `plan_yolo_review`, prompt scaffold, helper models, thinking and
   repair count correctly accepted, persisted and represented in metadata?
2. **Native plan-yolo fidelity** — does the current invocation faithfully execute
   OMP 17.2.15 plan-yolo? Confirm that the active tool restrictions still permit
   plan proposal/submission and handoff. Check the actual `write`/`xd://propose`
   flow rather than assuming a legacy `resolve` tool.
3. **Handoff thinking** — confirm `:max` on `--plan-yolo-into` and
   `--prewalk-into` is the right way to preserve Max for the target model.
4. **Prewalk fidelity** — is `todo` sufficient/necessary, and do the active tools
   preserve OMP's intended mutation-boundary switch semantics?
5. **No fan-out** — confirm no implementation task/subagent route remains exposed
   despite the defensive spawn-cap hook.
6. **Magic-keyword isolation** — confirm only the explicit ultrathink condition
   can trigger magic-keyword behavior; orchestrate/workflowz remain disabled.
7. **Advisor fidelity** — confirm `modelRoles.advisor`, `--advisor`, Max thinking,
   `syncBacklog=1`, `immuneTurns=3`, and no advisor subagents behave as intended.
8. **Advisor accounting** — detect double counting or omission between primary
   print JSONL and nested advisor session JSONL.
9. **Plan-yolo/prewalk accounting** — verify provider/model events are sufficient
   to split helper and worker usage without losing or double-counting calls.
10. **Review isolation** — confirm reviewer cannot mutate either directly or via
    indirect device/tool behavior.
11. **Candidate patch** — verify the diff against captured base commit contains
    exactly the implementation state the reviewer should critique, including
    new/deleted files.
12. **One-repair semantics** — confirm the repair worker sees current workspace +
    findings but no hidden verifier feedback and does not receive a second review.
13. **Final artifact compatibility** — confirm final commit/patch still satisfies
    Pier/DeepSWE artifact collection and pristine verification.
14. **Session paths** — validate stage `--session-dir` assumptions, especially
    where advisor JSONL is expected to land.
15. **Prompt-template behavior** — confirm the decorator does not transform the
    original DeepSWE task differently between treatments except the intentional
    ultrathink insertion.
16. **Network isolation** — validate gateway allowlist + Pier port-4000 patch and
    identify any accidental internet path.
17. **Failure classification** — ensure model failure is distinguishable from
    auth/transport/setup/verifier infrastructure failure.
18. **Token/cost semantics** — verify cache reads, top-level Pier token fields,
    per-stage fields, and total cost are interpreted consistently.
19. **Fresh v4 comparability** — identify any unintended effective prompt/tool/
    config differences across treatment arms.
20. **Adaptive design economy** — remove any proposed run that does not answer a
    distinct routing decision before suggesting additions.
21. **Legacy contamination** — ensure hidden historical verifier details are not
    present in committed prompts/docs used by benchmark agents.
22. **Frozen-source consistency** — ground findings in pinned versions rather
    than current upstream behavior.

## Constraints to preserve

- no full factorial unless essential
- no two implementation workers / general fan-out
- no vibe mode
- no hidden verifier feedback as model input
- no opportunistic upgrade of the frozen stack during this experiment
- no web search inside task agents
- bounded spend and adaptive stopping
- practical routing policy over publication-grade benchmarking

## Requested output

Return exactly these sections:

### 1. Verdict
`GO`, `GO WITH FIXES`, or `NO-GO`, with a 2–4 sentence rationale.

### 2. Blocking findings
Only issues that threaten correctness, comparability, isolation, reproducibility,
or cost accounting. For each: severity, exact file/symbol, why it matters, and
minimal fix.

### 3. Non-blocking improvements
Useful hardening/clarity changes that should not delay the next smoke run.

### 4. Experiment critique
Identify decision-useful, redundant, or missing conditions. Prefer deletions over
expansion.

### 5. Special-sauce verdict
Compare `plan_yolo`, `prewalk`, `ultrathink`, `advisor`, and controlled review as
separate economic interventions. State whether each asks a genuinely different
question and whether it deserves pilot spend.

### 6. Minimal validation sequence
Smallest ordered set of local checks/smoke runs required before the two-task
pilot, with evidence to inspect after each.

### 7. Final go/no-go checklist
A concise checklist to use immediately before spending on the next benchmark run.
