# OMP Bench v4 — plan-yolo naming and review refresh

## What changed from v3

- Promoted OMP native plan-yolo to the explicit treatment name `plan_yolo`.
- Renamed the combined treatment to `plan_yolo_review`.
- Removed the misleading `plan` label; there is no duplicate plain-plan arm.
- Kept native implementation semantics: helper starts active with `--plan-yolo`,
  OMP auto-approves the submitted plan, then switches to the worker through
  `--plan-yolo-into <worker>:max`.
- Preserved `prewalk` as a distinct treatment rather than conflating it with
  plan-yolo.
- Bumped benchmark metadata schema to version 4.
- Added fail-fast validation for treatment-specific helper kwargs and froze
  `ultrathink` as a solo-only control, preventing accidental mixed conditions.
- Refreshed experiment and Sol Max review documents so every name matches code.
- Removed the scripted Sol launcher from the active design. The intended review
  workflow is now: `cd` into the repo, launch interactive Sol Max in OMP, then
  paste the review prompt.

## Why there is no `plan` + `plan_yolo` pair

The v3 `plan` branch already invoked OMP native `--plan-yolo`. Running a new
`plan_yolo` arm beside it would be an identical duplicate under a different label.
The scientifically correct change is to rename the condition, not double-count it.

## Benchmark interventions after v4

1. DS4 solo.
2. DS4 solo + `ultrathink`.
3. K3 `plan_yolo` → DS4.
4. K3 `prewalk` → DS4.
5. DS4 + K3 advisor.
6. DS4 → K3 read-only review → one DS4 repair.
7. `plan_yolo_review` only if component results justify combining them.
8. Luna/K3/Sol direct solo frontier.
9. Helper-intelligence ladders only for interventions that first show value.
