# OMP × Pier Benchmark v4 — Findings and Insights Ledger

Updated after every reviewed v4 run. This is the ongoing empirical record; `benchmark/EXPERIMENT.md` remains the experiment specification and decision ledger.

> **Status (2026-08-14): official Task 2 DS4 baseline closeout; Phase 1 in progress (`2/3`).**
> Task 2 DS4 solo is a valid near-miss (`78/79` F2P, `16715/16715` P2P). Remaining
> Task 2 routes are registered but unauthorized. The next evidence run is a
> fresh DS4 solo baseline on the preselected Very Hard Task 3.

## Recording rules

- Add a run only after its contract, validation, configuration, stage logs, accounting, stderr, and patch evidence have been reviewed.
- Preserve provider-recorded cost exactly as `recorded cost`.
- When a role has tokens but no provider-recorded cost, estimate it from the current official API rate card and label it **inferred**. Never replace or merge it silently with recorded cost.
- Record the pricing date, source, token classes, arithmetic, and whether taxes or provider-specific discounts are excluded.
- Hidden verifier failure details under `benchmark/runs/**` are never copied here. Only aggregate reward, F2P, P2P, and partial scores are recorded.
- Insights are provisional until repeated across tasks. A ceiling result validates the harness but cannot demonstrate quality uplift.

## Pricing references

### Kimi K3

Official Kimi API rate card, retrieved 2026-08-12: [Flagship Model Kimi K3 Pricing](https://platform.kimi.ai/docs/pricing/chat-k3)

| Token class | USD per 1M tokens |
|---|---:|
| Cache-hit input | $0.30 |
| Cache-miss input | $3.00 |
| Output | $15.00 |

The official page states that 1M means 1,000,000 tokens and that prices exclude applicable taxes. Inferred values below assume benchmark `input_tokens` are cache misses and `cache_read_tokens` are cache hits. They do not include taxes, negotiated discounts, subscription allocation, or gateway-specific billing behavior.

## Reviewed runs

### Task 1 — DS4 solo

- **Run:** `v4-t01-ds4-solo`
- **Condition:** `ds4-solo`; treatment `solo`
- **Commit:** `973d2ce9a8310583997b843974591e85a7d1bfe0`
- **Validation:** `VALID`; no violations
- **Models:** worker `deepseek/deepseek-v4-flash:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `25m 09s`
- **Tokens:** input including cache `19,256,890`; cache read `19,168,768`; uncached input `88,122`; output `138,212`
- **Recorded workflow cost:** `$0.1047089904`
- **Evidence:** one DS4 worker; empty stderr; no implementation subagents; no retries or exceptions; aggregate verifier success.
- **Artifact caveat:** this run predates the committed per-run final-patch equality capture. Its collected patch applies cleanly, but equality was not recorded by the current validator.

### Task 1 — K3 plan-yolo → DS4

- **Run:** `v4-t01-k3-plan-yolo-ds4`
- **Condition:** `k3-plan-yolo-ds4`; treatment `plan_yolo`
- **Commit:** `b6f24b3d3aa62743fed783860329a8ad2aba517b`
- **Validation:** `VALID`; no violations
- **Models:** planner `kimi-code/k3:max`; worker `deepseek/deepseek-v4-flash:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `36m 49s`
- **Recorded workflow cost:** `$0.0533104656`
- **Recorded planner cost:** `$0`
- **Inferred K3 planner cost:** **`$1.2861534` (inferred)**
  - cache-miss input: `84,552 / 1,000,000 × $3.00 = $0.253656`
  - cache-hit input: `1,047,808 / 1,000,000 × $0.30 = $0.3143424`
  - output: `47,877 / 1,000,000 × $15.00 = $0.718155`
- **Inferred combined workflow cost:** **`$1.3394638656` (inferred)** = recorded DS4 worker cost `$0.0533104656` + inferred K3 planner cost `$1.2861534`. This is a planning estimate, not a gateway charge.
- **DS4 worker usage:** uncached input `109,642`; cache read `8,724,352`; output `48,330`; recorded cost `$0.0533104656`.
- **Handoff evidence:** K3 started in native read-only plan mode; wrote the canonical `local://` plan; submitted through `write xd://propose`; OMP emitted `model_changed`, preserved `thinking=max`, and switched to DS4; first working-tree edit occurred under DS4.
- **Isolation and artifact evidence:** no task/subagent calls; empty stderr; collected and independently captured final patches matched SHA-256 `16671639efb52679991c06249049052fac321d69479776842c6903cd67f97a33`.
- **Accounting evidence:** planner and worker stage totals reconcile exactly to top-level tokens and recorded cost.

### Task 1 — K3 prewalk → DS4

- **Run:** `v4-t01-k3-prewalk-ds4`
- **Condition:** `k3-prewalk-ds4`; treatment `prewalk`
- **Commit:** `644c98a8850f3daff3ea0c095a7494ea55ba1d29`
- **Validation:** `VALID`; no violations
- **Models:** prewalker `kimi-code/k3:max`; worker `deepseek/deepseek-v4-flash:max`
- **Quality:** reward `0.0`; partial `0.9931034483`; F2P `22/23`; P2P `122/122`
- **Runtime:** `18m 51s`
- **Recorded workflow cost:** `$0.0376059880`
- **Recorded prewalker cost:** `$0`
- **Inferred K3 prewalker cost:** **`$0.5734584` (inferred)**
  - cache-miss input: `50,480 / 1,000,000 × $3.00 = $0.151440`
  - cache-hit input: `252,928 / 1,000,000 × $0.30 = $0.0758784`
  - output: `23,076 / 1,000,000 × $15.00 = $0.346140`
- **Inferred combined workflow cost:** **`$0.6110643880` (inferred)** = recorded DS4 worker cost `$0.0376059880` + inferred K3 prewalker cost `$0.5734584`. This is a planning estimate, not a gateway charge.
- **DS4 worker usage:** uncached input `82,379`; cache read `4,892,160`; output `44,196`; recorded cost `$0.0376059880`.
- **Handoff evidence:** K3 performed repository reconnaissance, received the native prewalk deep-plan nudge, produced the complete plan and todo checkpoint, and retained ownership through the first qualifying edit call. OMP then emitted `model_changed`, preserved `thinking=max`, and switched one-way to DS4 immediately after that first edit.
- **Isolation and artifact evidence:** no task/subagent calls; empty stderr; collected and independently captured final patches matched SHA-256 `613f4100eaea27a0b37c1fd0dbd266a9488b16b3ff5c2af070ad8046a1135605`.
- **Accounting evidence:** the corrected prewalker and worker transcript totals reconcile to the top-level usage and recorded cost. The earlier ledger values duplicated the single mixed-model transcript; they were not a second invocation and are superseded by these values.

### Task 1 — DS4 + K3 advisor

- **Run:** `v4-t01-ds4-k3-advisor`
- **Condition:** `ds4-k3-advisor`; treatment `advisor`
- **Commit:** `f920a0e758caedf17c4af1ee3dcbeb72e5852b9b`
- **Validation:** `VALID_MODEL_TIMEOUT`; no violations. This is the canonical resource-bounded outcome.
- **Models:** worker `deepseek/deepseek-v4-flash:max`; native advisor `kimi-code/k3:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `1h 31m 50s` overall; agent execution reached the frozen `5,400s` limit (`5,403.994s` observed including cancellation cleanup).
- **Recorded workflow cost:** `$0.1215292232`
- **Recorded advisor cost:** `$0`
- **Inferred K3 advisor cost:** **`$10.2769536` (inferred)**
  - cache-miss input: `233,120 / 1,000,000 × $3.00 = $0.699360`
  - cache-hit input: `29,235,712 / 1,000,000 × $0.30 = $8.7707136`
  - output: `53,792 / 1,000,000 × $15.00 = $0.806880`
- **Inferred combined workflow cost:** **`$10.3984828232` (inferred)** = recorded DS4 worker cost `$0.1215292232` + inferred K3 advisor cost `$10.2769536`. This is a planning estimate, not a gateway charge.
- **DS4 worker usage:** uncached input `107,033`; cache read `22,134,144`; output `159,175`; recorded cost `$0.1215292232`.
- **Advisor lifecycle evidence:** the continuously running K3 advisor produced `240` assistant records over `76` processed transcript-update batches. It made four explicit `advise` tool calls and used only advisor-safe investigative tools (`read` 142, `grep` 33, `glob` 3); no advisor mutation tools or implementation subagents were observed. Four is the advice-delivery count, not the number of monitoring cycles or model responses.
- **Timeout and artifact evidence:** DS4 emitted its normal final response after about `88m 27s`, while K3 was still processing advisor backlog. Native print mode drains outstanding advisor work for up to ten minutes, but the outer `5,400s` model deadline cancelled the recorded OMP process group first. The candidate was committed without stash recovery; collected and independently captured final patches matched SHA-256 `635c75a084e950abbc2115639a0b24224f9a94e55dc1a099d5f02c71d6511d94`; stderr was empty; worker and advisor stage totals reconciled exactly.
- **Interpretation:** the aggregate verifier reached full quality, but native advisor catch-up did not finish within the frozen agent budget. The deadline result is canonical and receives no result-based retry.

### Task 1 — DS4 → K3 review → DS4 repair

- **Run:** `v4-t01-ds4-k3-review-ds4`
- **Condition:** `ds4-k3-review-ds4`; treatment `review`
- **Commit:** `9118fd197ecedb0171a5e25687998f32bc7cadfa`
- **Validation:** `VALID`; no violations
- **Models:** worker `deepseek/deepseek-v4-flash:max`; read-only reviewer `kimi-code/k3:max`; one fresh repair `deepseek/deepseek-v4-flash:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `46m 40s`
- **Recorded workflow cost:** `$0.1310344504`
- **Recorded reviewer cost:** `$0`
- **Inferred K3 reviewer cost:** **`$0.6785400` (inferred)**
  - cache-miss input: `52,804 / 1,000,000 × $3.00 = $0.158412`
  - cache-hit input: `463,360 / 1,000,000 × $0.30 = $0.139008`
  - output: `25,408 / 1,000,000 × $15.00 = $0.381120`
- **Inferred combined workflow cost:** **`$0.8095744504` (inferred)** = recorded DS4 implementation/repair cost `$0.1310344504` + inferred K3 reviewer cost `$0.6785400`.
- **Isolation and artifact evidence:** the reviewer used its independent read-only stage, followed by exactly one fresh DS4 repair stage; strict validation found no violations. No cancelled stash was recovered; collected and final patches matched SHA-256 `cba1b32e2d8912f794afdbcd72b82033b87993ebfaaa4859305fd83cfa0bf86f`.
- **Accounting evidence:** worker, reviewer, and repair totals reconcile exactly to the top-level tokens and recorded cost.

### Task 1 — K3 plan-yolo → DS4 → K3 review → DS4 repair

- **Run:** `v4-t01-k3-plan-yolo-ds4-k3-review`
- **Condition:** `k3-plan-yolo-ds4-k3-review`; treatment `plan_yolo_review`
- **Commit:** `9118fd197ecedb0171a5e25687998f32bc7cadfa`
- **Validation:** `VALID`; no violations
- **Models:** planner and read-only reviewer `kimi-code/k3:max`; worker and one fresh repair `deepseek/deepseek-v4-flash:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `47m 05s`
- **Recorded workflow cost:** `$0.0693773584`
- **Recorded K3 cost:** `$0`
- **Inferred K3 planner cost:** `$0.9885276`; inferred K3 reviewer cost: `$0.6436044`
- **Aggregate K3 usage and inferred cost:** cache-miss input `119,854` (`$0.359562`); cache-hit input `1,280,000` (`$0.384000`); output `59,238` (`$0.888570`); **`$1.6321320` total inferred**.
- **Inferred combined workflow cost:** **`$1.7015093584` (inferred)** = recorded DS4 implementation/repair cost `$0.0693773584` + inferred K3 planner/reviewer cost `$1.6321320`.
- **Isolation and artifact evidence:** the native plan-yolo handoff preceded DS4 implementation; the later K3 reviewer was independent and read-only; exactly one fresh DS4 repair followed. No cancelled stash was recovered; collected and final patches matched SHA-256 `0fda57f89d00baf57c2ca84bce10d54734a146688aaaf248fb0e4a9e2b28f2e9`.
- **Accounting evidence:** planner/worker, reviewer, and repair totals reconcile exactly to the top-level tokens and recorded cost.

### Task 1 — DS4 + Luna advisor

- **Run:** `v4-t01-ds4-luna-advisor`
- **Condition:** `ds4-luna-advisor`; treatment `advisor`; exploratory extension
- **Commit:** `b9b84a40e17d7dbc9e440002db71afbc074dce1b`
- **Validation:** `VALID_MODEL_TIMEOUT`; no violations
- **Models:** worker `deepseek/deepseek-v4-flash:max`; native advisor `openai-codex/gpt-5.6-luna:max`
- **Quality:** reward `1.0`; partial `1.0`; F2P `23/23`; P2P `122/122`
- **Runtime:** `1h 31m 15s` overall; agent execution reached the frozen `5,400s` limit (`5,403.849s` observed including cancellation cleanup).
- **Recorded workflow cost:** `$1.3179138976`
- **DS4 worker usage:** uncached input `107,994`; cache read `19,294,592`; output `168,658`; recorded cost `$0.1163682576`.
- **Luna advisor usage:** uncached input `706,607`; cache read `39,896,832`; output `218,573`; recorded cost `$1.2015456400`.
- **Advisor lifecycle evidence:** the continuously running Luna advisor produced `240` assistant records over `119` processed transcript-update batches. It made `47` explicit `advise` calls (`8` nit, `23` concern, `16` blocker) and used only advisor-safe investigative tools (`read` 128, `grep` 23, `glob` 2).
- **Timeout and artifact evidence:** unlike the K3 advisor run, DS4 had not emitted a final response; its final recorded action was still awaiting a tool result near the deadline. Cancellation stopped the process group before finalization. No cancelled stash was recovered; collected and final patches matched SHA-256 `3f72e7deb344212d062f70485d0e94246f584797641cbefd2b1d5c4b6911ccc2`.
- **Interpretation:** the saved patch reached full aggregate quality, but the primary worker itself remained active at the frozen deadline. The result is canonical for this exploratory condition and receives no result-based retry.

## Invalid attempts

### Task 1 — DS4 + K3 advisor

- **Run:** `v4-t01-ds4-k3-advisor.invalid-instrumentation-20260813`
- **Condition:** `ds4-k3-advisor`; treatment `advisor`
- **Commit:** `7f3f40e893f3bdacdf1f63d08a4463aad6d9e989`
- **Validation:** `INVALID_HARNESS`
- **Exception:** `AgentTimeoutError`; agent execution reached the frozen `5,400s` limit.
- **Runtime:** `1h 31m 11s` including setup and aggregate verification.
- **Aggregate verifier output, not comparable as a benchmark score:** reward `0.0`; partial `0.8413793103`; F2P `0/23`; P2P `122/122`.
- **Recorded workflow cost:** unavailable because timeout prevented post-run context population.
- **DS4 worker transcript usage:** uncached input `106,983`; cache read `12,155,904`; output `114,098`; recorded cost `$0.0809615912`.
- **K3 advisor transcript usage:** uncached input `183,024`; cache read `20,485,888`; output `46,290`; recorded cost `$0`.
- **Inferred K3 advisor cost:** **`$7.3891884` (inferred)**
  - cache-miss input: `183,024 / 1,000,000 × $3.00 = $0.549072`
  - cache-hit input: `20,485,888 / 1,000,000 × $0.30 = $6.1457664`
  - output: `46,290 / 1,000,000 × $15.00 = $0.694350`
- **Inferred combined attempt cost:** **`$7.4701499912` (inferred)** = recorded DS4 transcript cost `$0.0809615912` + inferred K3 advisor cost `$7.3891884`. This is a planning estimate, not a gateway charge.
- **Advisor lifecycle evidence:** DS4 remained the implementation worker. The separate K3 transcript made four `advise` calls and used only advisor-safe tools (`read` 71, `grep` 133, `glob` 7); no advisor mutation tools or implementation subagents were observed.
- **Latency diagnosis:** K3's four completed advice batches occupied about `40m 58s` of wall time (`293.1s`, `147.8s`, `187.2s`, and `1,829.6s`). At `09:14:26Z`, DS4 launched a two-pass `go test -bench . -benchtime 50x` comparison that temporarily used `git stash` and requested a `600s` tool timeout. The tool had no completion event when Pier cancelled the run about 18 minutes later. The same 50x workload completes in about `4.7s` on the untouched task image, so the evidence is consistent with candidate-induced nontermination and failed per-tool timeout enforcement; the deleted candidate workspace prevents separating those causes.
- **Stderr:** empty.
- **Artifact failure:** timeout occurred before the wrapper's final commit and independent patch capture. The collected `model.patch` is empty and `agent/final.patch` is absent, so patch equality cannot be established.
- **Harness diagnosis:** the validator also incorrectly expected K3 events inside `worker.jsonl`, although native OMP stores advisor events in a nested `__advisor.jsonl`. The adapter had the same non-recursive lookup defect for advisor accounting. Both parsers were corrected after this attempt; the timeout and missing final patch remain independently disqualifying.
- **Decision:** exclude this attempt from quality comparisons. Its result did not authorize review/repair; the later canonical replacement closes the advisor gate independently.

### Task 1 — interrupted DS4 → K3 review → DS4 repair

- **Run:** `v4-t01-ds4-k3-review-ds4.invalid-infrastructure-20260813`
- **Condition:** `ds4-k3-review-ds4`; treatment `review`
- **Status:** infrastructure-invalid; excluded from every quality and cost comparison
- **Failure:** the host-side coordinator and frozen auth services received `SIGTERM` while the in-container repair process remained orphaned. The attempt never reached evaluation and produced no usable result.
- **Decision:** stop the orphaned containers, archive the directory, re-establish frozen readiness, and authorize one infrastructure replacement. The later canonical review run completed normally.

### Task 2 — DS4 solo

- **Run:** `v4-t02-ds4-solo`
- **Condition:** `ds4-solo`; treatment `solo`
- **Commit:** `62d3dbb8cd8bf7898a328f97cb2d554c33cb9d64`
- **Validation:** `VALID`; no violations
- **Models:** worker `deepseek/deepseek-v4-flash` with `thinking=max`
- **Quality:** reward `0.0`; partial `0.9999404549`; F2P `78/79`; P2P `16715/16715`
- **Runtime:** `23m 28s` wall (`1,408s`); agent execution `22m 08s` (`1,328s`)
- **Tokens:** input including cache `11,020,384`; cache read `10,916,992`; uncached input `103,392`; output `132,282`
- **Recorded workflow cost:** `$0.0820814176`
- **Evidence:** one DS4 worker; empty stderr; no implementation subagents; no retries or exceptions; collected and independently captured final patches matched SHA-256 `605b35fab7b9a35a415074917fecaa59a87f892e31db16f8720d13d2d3fb407a`; worker stage totals reconcile exactly to top-level tokens and recorded cost.
- **Interpretation:** this is a near-miss rather than a ceiling. Binary reward fails on a single F2P check while the P2P suite is perfect. Empirical cost and latency remain comparable to Task 1 DS4 solo, so the pre-run Medium label did not produce a DS4 struggle.

## Infrastructure evidence

### Network isolation smoke

- **Run:** `v4-network-isolation-smoke`
- **Commit:** `b6f24b3d3aa62743fed783860329a8ad2aba517b`
- **Result:** `NETWORK_ISOLATION_OK`
- `gateway_allowed=True`
- `external_dns_allowed=False`
- `external_ip_allowed=False`

### Pinned host OMP runtime

- **Commit:** `7f3f40e893f3bdacdf1f63d08a4463aad6d9e989`
- The macOS arm64 OMP `17.2.15` host executable is pinned as `benchmark/bin/omp-darwin-arm64`.
- SHA-256: `0182e96e401b1d9b2fb219b0aa696b497b373f8a0f54fc4073af489882ec0a50`.
- The runner and readiness gate now invoke this binary directly. The user's normal OMP installation can upgrade independently.

### Timeout artifact finalization

- Pier enforces the frozen agent timeout with `asyncio.wait_for`, which cancels the adapter coroutine before normal post-stage finalization.
- OMP stages now run in a recorded in-container process group. On cancellation the adapter terminates that group before attempting the final commit, preventing the cancelled Docker exec from racing the deadline snapshot.
- After the process group is stable, the adapter attempts its final commit and independent patch capture, then re-raises the original timeout. A capture failure never masks the original exception and remains independently detectable by patch validation.
- Stage registration now precedes OMP execution, so a cancelled stage retains separately attributed worker and advisor usage.
- The validator reconciles stage totals to Pier totals and distinguishes an artifact-valid frozen deadline (`VALID_MODEL_TIMEOUT`) from infrastructure failure.
- The final comparison command could have been cancelled while the candidate was temporarily stored by `git stash`. Deadline finalization now records the base stash set, restores exactly one new stash only when tracked state is otherwise clean, and treats multiple stashes or concurrent tracked changes as ambiguous infrastructure failure rather than silently certifying an empty patch.
- Focused regression coverage confirms direct cancellation, `asyncio.wait_for` timeout cleanup, partial advisor accounting, and preservation of the original cancellation when capture itself fails.
- This hardening protects future runs only. It cannot reconstruct the deleted workspace from the invalid advisor attempt.

## Current cross-run insights

1. **Harness validity:** seven task-1 conditions have canonical outcomes. DS4 solo, plan-yolo, prewalk, controlled review, and plan-yolo plus review completed normally. K3 and Luna native-advisor runs are artifact-valid at the frozen deadline. Native handoffs/advice, read-only reviewer isolation, exactly one repair, Max-thinking preservation, no-fan-out enforcement, accounting, timeout cleanup, and patch equality are evidenced.
2. **Prewalk semantics are valid but quality regressed:** K3 owned reconnaissance, planning, and the first qualifying edit before OMP switched one-way to DS4. It achieved reward `0.0`, partial `0.9931034483`, and F2P `22/23`; every other completed canonical task-1 condition reached full aggregate quality.
3. **Corrected K3 economics:** K3 roles report `$0` through the gateway, so official list pricing is required for comparable estimates. Inferred combined costs are plan-yolo `$1.3394638656`, prewalk `$0.6110643880`, controlled review `$0.8095744504`, plan-yolo plus review `$1.7015093584`, and K3 advisor `$10.3984828232`.
4. **DS4 solo dominates every other full-quality task-1 route:** it reached full quality in `25m 09s` for `$0.1047089904` recorded. Plan-yolo cost about `12.79×` as much; controlled review `7.73×`; plan-yolo plus review `16.25×`; Luna advisor `12.59×`; and K3 advisor `99.31×`. Prewalk cost `5.84×` as much and finished faster, but scored lower.
5. **Review completed without advisor-style deadline pressure:** controlled review/repair reached full quality in `46m 40s`; adding plan-yolo also reached full quality in `47m 05s`. Neither improved aggregate quality over DS4 solo on this ceiling task.
6. **Live advisors differed behaviorally, not architecturally:** both used the same native OMP advisor lifecycle. K3 emitted four advice notes across `76` processed update batches and was still draining after DS4's final response. Luna emitted `47` advice notes across `119` batches, and DS4 itself remained active at timeout. Advice-call count is not a proxy for whether monitoring was continuously enabled.
7. **Advisor cost/latency:** K3 advisor reached full aggregate quality for `$10.3984828232` inferred combined and Luna advisor for `$1.3179138976` recorded; both exhausted the `5,400s` agent budget. On task 1, DS4 solo dominates both on equal measured quality, cost, and latency.
8. **Accounting lesson:** mixed-model handoff stages must be partitioned by provider/model within the one stage transcript. The superseded prewalk ledger accidentally duplicated that transcript; canonical artifacts contain one K3 prewalk and one DS4 implementation, now reconciled to top-level usage.
9. **Harness lesson:** native advisor evidence and usage live below the worker session in `__advisor.jsonl`, not in the primary `worker.jsonl`. Validation and accounting must discover that transcript recursively while excluding it from primary-worker totals and adding it exactly once as advisor usage.
10. **Timeout lesson:** an exact resource deadline can remain scientifically usable when the process group is stopped before snapshotting, partial role accounting reconciles, stderr is clean, and independently captured patches match. Instrumentation- and infrastructure-invalid attempts remain excluded.

11. **Task 2 DS4 solo is a valid near-miss:** reward `0.0`, F2P `78/79`, P2P `16715/16715`, partial `0.9999404549`, `23m 28s`, `$0.0820814176` recorded. The Medium structural label is retained; empirically DS4 still finished cheaply and quickly.

## Task 2 decision and Phase 1 continuation

The Task 2 DS4 solo baseline is accepted as `VALID`. Remaining Task 2 routes stay registered but are not authorized: the operator decision is to spend the next run on the Very Hard task rather than chase the one remaining Task 2 F2P miss.

The two canonical Task 1 advisor conditions remain `VALID_MODEL_TIMEOUT` with no result-based retry. `k3-solo` and `k3-prewalk-ds4-k3-review` remain retired unrun for Task 1 and are not part of the reported Task 1 evidence.

Advisor + review and plan/prewalk + advisor crosses remain excluded because live advising is already deadline-bound and those combinations blur role timing. OMP `orchestrate`, `workflowz`, native `/review`, loop, goal/guided-goal, CI-green, and Vibe remain excluded because they introduce fan-out, repeated attempts, persistence, or feedback-loop semantics.

Phase 1 remains a three-task ladder: Task 1 Very Easy by empirical DS4 baseline, Task 2 Medium by pre-run structural review with an empirical DS4 near-miss, and Task 3 Very Hard by pre-run structural review. The next authorized evidence run is the fresh Task 3 `ds4-solo` baseline. No later Task 3 condition is authorized until that baseline passes full artifact review. An extended-time or runtime-repaired advisor experiment still requires a new diagnostic condition ID and remains non-comparable to v4.
