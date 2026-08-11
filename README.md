# Pharma Commercial Analytics Engine

A small SQL + Python project simulating the core commercial-analytics workflows
in a pharma/healthcare consulting engagement: **HCP segmentation, call plan
gap analysis, incentive compensation, and marketing-channel lift** — the same
four use cases named in commercial analytics BA job descriptions.

## Data model (SQLite — `schema.sql`)

- `reps` — sales reps, region, quarterly TRx quota
- `hcps` — doctors, specialty, region, potential score, assigned rep (territory)
- `calls` — rep visit log (date, channel: in-person / virtual / email)
- `rx` — monthly prescription volume (TRx, NRx) per HCP per product

`data_generator.py` builds a synthetic but internally-consistent 12-month
dataset (200 HCPs, 20 reps, ~5k Rx rows) with a real signal: higher-potential
HCPs get more calls and higher baseline Rx, and a call in a given month gives
that month's Rx a small bump — so the SQL below finds genuine patterns, not noise.

## The four analyses (`queries.sql`, run via `analysis.py`)

| # | Question | SQL technique | Business use case |
|---|----------|---------------|--------------------|
| 1 | Which HCPs are high-potential but under-prescribing? | `NTILE()` window function, two decile rankings | **Segmentation** |
| 2 | Which HCP tiers are under-called relative to an ideal cadence? | CTE + `CASE` benchmark logic | **Call planning** |
| 3 | What should each rep be paid this quarter? | CTE, tiered `CASE` payout curve | **Incentive compensation** |
| 4 | Which call channel drives the biggest Rx lift? | `LAG()` window function, self-referencing join | **Marketing analytics** |

## Results (this run)

- **Segmentation**: clear potential/actual split — see `charts/1_segmentation.png`
- **Call gap**: 100% of the top 2 potential deciles fall short of a monthly-cadence
  benchmark — a concrete under-investment finding, `charts/2_call_gap.png`
- **Incentive**: attainment spreads 78%–143% across reps, payouts follow the
  tiered curve, `charts/3_incentive.png`
- **Marketing lift**: in-person calls show the largest average Rx bump,
  `charts/4_marketing_lift.png`

## Run it yourself

```bash
pip install pandas numpy matplotlib
python data_generator.py   # builds pharma_analytics.db
python analysis.py         # runs the 4 queries, saves charts/
```

## Notes / honest limitations

- Rep→HCP attribution is territory-based (one rep owns a fixed panel), which
  simplifies real-world credit assignment (shared/split territories, sample
  drops, speaker programs) — flagged here rather than hidden.
- "Ideal call cadence" benchmarks (12/6/2 visits per year by decile) are an
  assumption for demo purposes, not a validated commercial model.
- Data is fully synthetic — no real patient, prescriber, or company data.
