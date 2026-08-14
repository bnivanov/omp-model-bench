# OMP 17.2.15 Special-Sauce Evaluation

Purpose: decide which OMP-native behaviors are scientifically useful additions
to the cost-vs-quality benchmark without recreating a sprawling multi-agent
matrix.

## Decision summary

| Feature | Frozen behavior | Benchmark decision | Why |
|---|---|---|---|
| `--plan-yolo` | Formal read-only plan, auto-approve, switch to execution model | **First-class `plan_yolo` treatment** | Clean “intelligence before execution” treatment |
| `--prewalk` | Strong model explores/plans, switches one-way at first real mutation | **Add** | Distinct mutation-boundary allocation of intelligence |
| `ultrathink` | Hidden careful multi-step reasoning notice; max effort when auto-thinking | **Add as cheap control** | At fixed `thinking=max`, isolates prompt scaffolding with no helper call |
| `--advisor` | Separate reviewer agent watches live transcript and can steer | Keep | Clean “during execution” treatment |
| native `/review` | Headless path invokes one reviewer task/subagent | Do not use for causal review treatment | Adds its own orchestration layer; wrapper review is cleaner |
| `orchestrate` | Hidden multi-agent delegation contract | Exclude | Violates no-fan-out design |
| `workflowz` | Deterministic multi-subagent eval/task workflow | Exclude | Requires multi-agent surface and broadens cost matrix |
| `/goal` / guided goal | Persistent autonomous objective and token budget | Defer | Better for long-horizon interactive sessions than one-shot DeepSWE |
| `/loop` | Re-submits prompt after yield | Exclude | Effectively repeated attempts; cost/quality confound and runaway risk |
| vibe | Autonomous multi-session mode | Exclude | Explicit operator non-goal |
| bundled `green` | Prompt for iterating on branch CI until green | Exclude | DeepSWE hidden verifier must remain post-hoc, not feedback |

## Canonical naming: `plan_yolo`, not `plan`

Earlier benchmark drafts called the planning condition `plan`, but the implementation
was already OMP native `--plan-yolo`. v4 removes that ambiguity. Future Pier configs
use `treatment=plan_yolo`; the combined post-review variant is
`treatment=plan_yolo_review`. There is no duplicate plain-plan arm because it would
execute the same OMP mechanism and waste benchmark spend.

### First plan-yolo condition

`K3:max --plan-yolo --plan-yolo-into DS4:max`

This directly competes with K3 prewalk → DS4, DS4 + K3 advisor,
DS4 → K3 review → DS4 repair, K3 solo, and Sol solo.

## Why prewalk is worth testing

Frozen OMP describes prewalk as a one-way handoff from the active model to a
fast/cheap target at the first `edit`/`write` after the plan/todo gate. Its
coordinator injects a hidden deep-plan prompt before mutation. That prompt
requires a concrete execution-order plan, exact files/symbols/commands/checks,
risks/edge cases, and a 5–9 item todo list. After the switch, OMP injects a
checklist that forces consistency search, minimal-scope review, and full relevant
module/file verification before completion.

This creates a materially different hypothesis from plan-yolo:

- **plan-yolo**: smart model is forced into formal read-only plan mode and hands
  off when the plan resolves.
- **prewalk**: smart model owns reconnaissance and plan commitment in the normal
  run, then hands off exactly at the implementation boundary.

The cost question is therefore useful: does paying K3/Sol only for repo
understanding and commitment beat either a formal plan or a smart full worker?

### Proposed first prewalk condition

`K3:max --prewalk --prewalk-into DS4:max`

If it helps materially, ladder only the prewalker:

`Luna:max → DS4:max`, `K3:max → DS4:max`, `Sol:max → DS4:max`.

Do not create a prewalk ladder if K3 prewalk does not beat/differentiate from
DS4 solo in a decision-relevant way.

## Why ultrathink is worth a small test

Frozen OMP recognizes the standalone lowercase prose word `ultrathink` and adds
a hidden system notice telling the model that the task requires multi-step
reasoning and to think carefully before responding. When auto-thinking is used,
it can also request the highest supported reasoning effort.

This benchmark already fixes `thinking=max`, so the interesting part is not the
reasoning-tier override. The test asks whether OMP's **hidden reasoning nudge**
changes quality/behavior at essentially zero routing cost.

Use it as an orthogonal `prompt_scaffold` setting, initially only on DS4 solo.
Do not multiply every treatment by ultrathink unless the cheap control first
shows meaningful value.

## Why the other magic words are excluded

`orchestrate` injects a contract to scope the full task, delegate substantial
independent work in parallel, verify phases, and continue until complete.
`workflowz` injects a deterministic multi-subagent contract using the persistent
`eval` kernel and `task`; frozen docs say its notice is injected only when both
`eval` and `task` are active.

Those are legitimate OMP capabilities, but answering their value requires a
separate multi-agent economics experiment. Including them here would recreate
the exact two-worker/fan-out complexity this benchmark was simplified to avoid.

## Other commands considered

### Goal mode

Frozen OMP exposes `/goal` as a persistent autonomous objective with set/show/
pause/resume/drop/budget controls, plus guided-goal setup. It is useful when an
agent should continue toward a long-running objective across turns. DeepSWE here
is a bounded single-task trial with external verification, so goal mode changes
session-control semantics more than it isolates a routing decision.

### Loop mode

Frozen OMP loop mode re-submits the prompt after each yield and can be limited by
count/duration. That is equivalent to granting extra attempts/continuations; it
would be unfair against single-pass conditions and is exactly the kind of spend
amplifier this project is trying to control.

### Native review

OMP 17.2.15 bundles `review`, but its headless request explicitly instructs use
of the `task` tool with exactly one `reviewer` task. That is useful in normal
OMP, but it makes “review timing” inseparable from OMP's reviewer-subagent
implementation. The benchmark therefore keeps a controlled sequential reviewer
with read-only tools and one worker repair pass.

### CI-green

OMP bundles a `green` custom command that generates a prompt to iterate on CI
failures until a branch is green. It is not appropriate here: DeepSWE's hidden
pristine verifier is evaluation evidence, never an iterative feedback channel.

## Pinned OMP source references for reviewer

All references are at `v17.2.15`:

- `docs/magic-keywords.md`
- `packages/coding-agent/src/modes/ultrathink.ts`
- `packages/coding-agent/src/prompts/system/ultrathink-notice.md`
- `packages/coding-agent/src/commands/launch-help.ts`
- `packages/coding-agent/src/session/prewalk.ts`
- `packages/coding-agent/src/prompts/system/prewalk-plan.md`
- `packages/coding-agent/src/prompts/system/prewalk-checklist.md`
- `docs/advisor-watchdog.md`
- `packages/coding-agent/src/extensibility/custom-commands/bundled/review/`
- `packages/coding-agent/src/extensibility/custom-commands/bundled/ci-green/`
- `packages/coding-agent/src/slash-commands/builtin-registry.ts`
