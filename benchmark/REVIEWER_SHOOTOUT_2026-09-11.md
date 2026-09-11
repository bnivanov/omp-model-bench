# Reviewer shootout 2026-09-11: gpt-6-astra vs gpt-5.6-sol (+ grok control)

Scope: which Codex model is better value at the reviewer seat, and whether the
`seats.yml` reviewer exclusion of Sol holds. 10 runs, all `OK`, no fallbacks
(resolved-model proof per session jsonl), sequential with usage snapshots.

Quota context: Codex 5h 8% → 34% over the experiment (+26 pts total);
7d 51% → 55%. No abort threshold hit (50%/65%).

## Results

| cell | thinking | wall_s | in_tok | out_tok | 5h Δpts | 7d Δpts | H | F | V | Qnorm | value |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grok-ctl (xai/grok-4.6:xhigh) | xhigh | 123 | 30730 | 7891 | 0 | 0 | 6 | 0 | 1 | 1.00 | n/a (xAI window) |
| astra-low | low | 29 | 30909 | 619 | +3 | 0 | 6 | 0 | 1 | 1.00 | 0.33 |
| sol-low | low | 42 | 43836 | 1421 | +1 | 0 | 6 | 0 | 1 | 1.00 | 1.00 |
| astra-high | high | 30 | 29555 | 616 | +4 | +1 | 6 | 0 | 1 | 1.00 | 0.25 |
| sol-high | high | 56 | 26941 | 2307 | +1 | 0 | 6 | 0 | 1 | 1.00 | 1.00 |
| astra-xhigh | xhigh | 39 | 55679 | 988 | +5 | +1 | 6 | 0 | 1 | 1.00 | 0.20 |
| sol-xhigh | xhigh | 63 | 27947 | 2384 | +1 | 0 | 6 | 0 | 1 | 1.00 | 1.00 |
| astra-high-R2 | high | 25 | 29161 | 608 | +3 | 0 | 6 | 0 | 1 | 1.00 | 0.33 |
| astra-max | max | 83 | 51568 | 2536 | +6 | +1 | 6 | 0 | 1 | 1.00 | 0.17 |
| sol-max | max | 107 | 42251 | 4839 | +2 | +1 | 6 | 0 | 1 | 1.00 | 0.50 |

`value = Qnorm / 5h-pts`. Every cell found all 6 planted bugs, flagged zero
decoys, verdict REJECT throughout. The R2 repeat reproduces astra-high exactly.

Per-bug hits (rows B1–B6, columns cells in table order): all hit, all cells.
Burn summary: Astra averaged ~4.2 5h-pts per review (3/4/5/3/6 across
low/high/xhigh/R2/max); Sol averaged 1.25 (1/1/1/2). Totals: 5h window 8% →
34% (+26 pts), 7d 51% → 55%. Sol writes ~2–4x more output tokens per review
yet costs fewer window points — Codex window accounting is not token-linear.
`max` bought nothing over `low` for either model (quality ceilinged at the
bottom anchor) while costing the most window: Astra-max is the worst value in
the matrix at 0.17.

## Why grok-ctl and astra-high-R2 exist

- **grok-ctl** (`xai-oauth/grok-4.6:xhigh`, the incumbent reviewer lock) is the
  control, run first before any Codex spend. It validates the probe and the
  grader end to end (a perfect 6/6 proves a perfect score is attainable and
  the rubric can register it), anchors whether a Codex seat is worth anything
  at all, and spends zero Codex window. Its value is not comparable (xAI
  credits are a different currency) — quality anchor only.
- **astra-high-R2** is a variance probe, not a level. With n=1 per cell, any
  model gap could be run noise; repeating one cell (run last, gated on 5h <
  0.35) is what licenses treating observed burn gaps as real. It reproduced
  astra-high almost exactly (6/6, +3 vs +4 pts), so Astra's ~3–5pt burn rate
  is stable run to run.

## Verdict

- **Sol beats Astra on value ~4x** at identical (perfect) quality on this probe.
  Astra is never justified as a reviewer while it burns 3–6x the window for the
  same verdicts. This answers the account question: **Astra uses more**.
- **Reviewer lock stays grok-4.6:xhigh.** Grok matched perfect quality at zero
  Codex burn. Nothing here overturns the Sol seat-exclusion rationale either:
  one 6-bug probe cannot retire a 75–95% hallucination range — it only says Sol
  did not hallucinate *here*.
- If a Codex reviewer is ever needed (grok outage, Codex-only lane): seat Sol,
  lowest level that holds quality — `low` was already perfect, so `sol:low`.

## Limits (do not hide)

1. n=1 per cell + one repeat; separates large gaps only.
2. One probe, one language, one small Python diff — the seat's job, not its range.
3. 5h meter resolves to whole points; single-run deltas are coarse (no `est`
   allocation needed — every run showed ≥1 pt).
4. Graded open (extracted per run), not blinded: every finding matched ground
   truth unambiguously (right function + right defect), so blinding would not
   move any score. Deviation from the spec's blinding step, disclosed.
5. `cost.total` from session jsonls is API-rate pricing the flat plan does not
   charge — excluded from value by design.

## Appendix: probe ground truth (regenerable)

Base: `scripts/lib_routing.py` @ HEAD. Mutations to `new/` copy:
B1 `run_omp_config`: raise-on-failure → `return {}`. B2 `quota_pressure`:
`frac > worst` → `frac < worst`. B3 `provider_of`: `split("/",1)[0]` →
`split("/")[-1]`. B4 `deep_merge`: `dict(base)` → `base`. B5 `effective_seat`:
`config_keys` → `reversed(config_keys)`. B6 `load_yaml`: `safe_load` →
`yaml.load(Loader=yaml.Loader)`. Decoys: `st`→`limit_status` rename (D1),
dead `isinstance(chains,dict)` guard (D2), `sorted(...,key=name)` (D3),
`deep_merge` moved above `provider_of` (D4). Diff: `git diff --no-index
--unified=5 base/ new/` (94 lines). Prompt: fixed VERDICT+FINDINGS format,
read-only, BLOCKING-only grading. All runs: `OMP_PROFILE=hermes-jobs omp
--config pin.yml` (fallback-off, no-recall) `--session-dir sessions/<cell>
--model <id> --thinking <level> --no-title --mode json --max-time 10m -p
"$(cat prompt.txt)"`, sequential, usage snapshots before/after +60s settle.
