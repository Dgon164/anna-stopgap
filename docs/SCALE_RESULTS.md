# SCALE TEST RESULTS — 2026-08-22

Machine: i9-14900KF / 48GB. Method: `testing/run_scale_test.py` —
seeded generator with exact known answers → full pipeline → the
independent validator (`testing/validate_outputs.py`, shares no
analysis code) recomputes every checkable claim and compares.
21 checks per size. Engine connected (two-tier mode), audit face
off (time separately if needed).

## The numbers

| rows | total wall clock | cache re-hit | checks |
|---|---|---|---|
| 10,000 | 32.5s | 0.01s | 21/21 PASS |
| 100,000 | 61.8s | 0.01s | 21/21 PASS |
| 1,000,000 | 327.1s (5.5 min) | 0.05s | 21/21 PASS |

Stage breakdown at 1M rows: intake ~14s · certified-tier engine
(sampled) 28.6s · describe+charts 39.6s · analytics blocks 243.8s ·
render <1s. The analytics blocks scale linearly (3s → 25s → 244s)
and are the next optimization target if 1M-row turnaround matters.

What passed at every size: row count and revenue preserved to the
cent through intake; every displayed number (KPIs, per-region
totals, leader shares, monthly) matches independent recomputation
at its displayed precision; every planted rule violation recomputed
identically; ZERO false accusations in the reconciliation lists;
the planted biggest order and the planted refund day found and
named. At 1M the reconciliation display caps at 10 listed rows of
100 violations — all 10 real, cap noted here, never silent.

## The bug this run caught and the fix

First 100k attempt: the dc engine's law-discovery pass blew a
30-minute subprocess timeout (measured ~30s at 10k rows — the
search is superlinear in rows). This was the source of multi-hour
runs. FIX (2026-08-22): above 10,000 rows the certified-rule tier
runs on a seeded random 10k sample and the report carries a receipt
saying exactly that; every descriptive number — everything the
validator checks — is still computed on ALL rows. Threshold
overridable via `ANNA_ENGINE_SAMPLE`. 100k went from >1800s to
61.8s with all checks passing.

Standing rule from the owner, same day: every run prints per-stage
wall-clock seconds (intake / engine faces / describe+charts /
analytics / render / total) — now built into process() and
honest_report; long stages are never silent again.

## What "validated" means here, concretely

1. Anna's own grades (200 half-sample stability checks per claim)
   — built in, every report.
2. Planted-truth suites — `demo_data/run_demo_checks.py` (13
   checks) and this scale rig, both exit-code clean for CI.
3. Independent recomputation — `validate_outputs.py` re-reads the
   raw file with its own arithmetic and compares every checkable
   claim class. Same method that caught the July counting bug,
   now automated and repeatable at any size.
