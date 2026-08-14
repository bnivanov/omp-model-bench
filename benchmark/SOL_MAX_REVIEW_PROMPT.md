# Sol Max benchmark review prompt

You are reviewing the OMP × Pier model benchmark in this repository before we
spend on further DeepSWE runs.

First read `benchmark/SOL_MAX_REVIEW_BRIEF.md` in full. It contains the objective,
frozen stack, model set, current evidence, causal questions, exact treatment
semantics, constraints, architecture assumptions, technical review checklist,
and required output format. Treat it as the authoritative review specification.

Then inspect the actual repository implementation, not just the prose. At
minimum read:

- `benchmark/EXPERIMENT.md`
- `benchmark/SPECIAL_SAUCE.md`
- `benchmark/PATCH_NOTES_V4.md`
- `benchmark/agents/omp_pier.py`
- `benchmark/agents/omp_deepswe.py`
- `benchmark/results/round1-baseline.json`
- `.omp/hooks/pre/benchmark-spawn-cap.ts`
- `benchmark/patches/pier-gateway-port-4000.patch` if present
- any freeze/pin manifests relevant to OMP, Pier and DeepSWE
- current `git status`, `git diff`, and recent benchmark-related commits

Where treatment semantics matter, inspect the **pinned OMP v17.2.15 source** in
`vendor` or the frozen checkout rather than relying on memory or current upstream.
In particular verify native `plan_yolo`, native `prewalk`, advisor behavior,
model-handoff thinking, tool restrictions, session layout and usage accounting.

Important boundaries:

- This is a review, not an implementation task. Do not edit files yet.
- Do not run DeepSWE benchmark trials yet.
- Do not solve the underlying benchmark task.
- Do not inspect historical hidden verifier failure details in `benchmark/runs/**`.
  Use only the aggregate legacy result committed under `benchmark/results/`.
- Do not propose feeding hidden verifier feedback into future model prompts.
- Do not reintroduce two implementation workers, general fan-out, vibe mode, or
  a full factorial design unless you identify a concrete validity requirement.

The central decision is already defined: find the cheapest reliable OMP route
across cheap solo workers, `ultrathink`, K3 `plan_yolo` → DS4, K3 `prewalk` →
DS4, DS4 + K3 advisor, DS4 → K3 review → one DS4 repair, and direct K3/Sol solo.
We want to know where smarter-model intelligence creates the most value relative
to its total workflow cost.

Do not ask what the project is trying to achieve. If you find ambiguity or an
unresolved design choice, treat it as a review finding and recommend the smallest
safe resolution.

Return the seven sections specified in `benchmark/SOL_MAX_REVIEW_BRIEF.md`, with
concrete file/symbol references and minimal fixes. End with a clear `GO`,
`GO WITH FIXES`, or `NO-GO` decision for proceeding to the next benchmark smoke
runs.
