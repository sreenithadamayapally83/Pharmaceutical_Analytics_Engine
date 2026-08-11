"""
Loads pharma_analytics.db, runs the 4 business queries, prints summaries,
and saves one chart per question into charts/.

Run: python analysis.py   (after data_generator.py)
"""
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

conn = sqlite3.connect("pharma_analytics.db")

# 1. Segmentation
q1 = """
WITH hcp_rx AS (
    SELECT hcp_id, SUM(trx) AS total_trx FROM rx GROUP BY hcp_id
)
SELECT h.hcp_id, h.specialty, h.region, h.potential_score,
       COALESCE(r.total_trx, 0) AS total_trx,
       NTILE(10) OVER (ORDER BY h.potential_score DESC) AS potential_decile,
       NTILE(10) OVER (ORDER BY COALESCE(r.total_trx, 0) DESC) AS actual_decile
FROM hcps h LEFT JOIN hcp_rx r ON r.hcp_id = h.hcp_id;
"""
seg = pd.read_sql(q1, conn)

plt.figure(figsize=(6, 5))
plt.scatter(seg.potential_score, seg.total_trx, alpha=0.6, c=seg.potential_decile, cmap="viridis")
plt.xlabel("Potential score")
plt.ylabel("Total TRx (12mo)")
plt.title("1. HCP Segmentation — Potential vs Actual Rx")
plt.tight_layout()
plt.savefig("charts/1_segmentation.png", dpi=130)
plt.close()

# 2. Call plan gap
q2 = """
WITH call_counts AS (
    SELECT hcp_id, COUNT(*) AS call_count FROM calls GROUP BY hcp_id
),
segmented AS (
    SELECT hcp_id, potential_score,
           NTILE(10) OVER (ORDER BY potential_score DESC) AS decile
    FROM hcps
)
SELECT s.decile,
       SUM(CASE WHEN COALESCE(c.call_count,0) <
             (CASE WHEN s.decile<=2 THEN 12 WHEN s.decile<=5 THEN 6 ELSE 2 END)
           THEN 1 ELSE 0 END) AS under_served,
       COUNT(*) AS total_hcps
FROM segmented s LEFT JOIN call_counts c ON c.hcp_id = s.hcp_id
GROUP BY s.decile ORDER BY s.decile;
"""
gap = pd.read_sql(q2, conn)
gap["pct_under_served"] = 100 * gap.under_served / gap.total_hcps

plt.figure(figsize=(6, 5))
plt.bar(gap.decile, gap.pct_under_served, color="indianred")
plt.xlabel("Potential decile (1 = highest potential)")
plt.ylabel("% under-served")
plt.title("2. Call Plan Gap by HCP Decile")
plt.tight_layout()
plt.savefig("charts/2_call_gap.png", dpi=130)
plt.close()

# 3. Incentive comp
q3 = """
WITH rep_actuals AS (
    SELECT h.assigned_rep_id AS rep_id, SUM(r.trx) AS actual_trx
    FROM hcps h JOIN rx r ON r.hcp_id = h.hcp_id
    GROUP BY h.assigned_rep_id
)
SELECT reps.rep_id, reps.rep_name, reps.quarterly_quota,
       COALESCE(a.actual_trx,0) AS actual_trx,
       ROUND(100.0*COALESCE(a.actual_trx,0)/reps.quarterly_quota,1) AS attainment_pct
FROM reps LEFT JOIN rep_actuals a ON a.rep_id = reps.rep_id
ORDER BY attainment_pct DESC;
"""
comp = pd.read_sql(q3, conn)


def payout(pct):
    if pct < 80:
        return 0
    if pct <= 100:
        return (pct - 80) / 20 * 50000
    return 50000 + (pct - 100) / 100 * 100000


comp["payout_inr"] = comp.attainment_pct.apply(payout)

plt.figure(figsize=(8, 5))
plt.bar(comp.rep_name, comp.payout_inr, color="seagreen")
plt.xticks(rotation=90)
plt.ylabel("Payout (INR)")
plt.title("3. Incentive Payout by Rep")
plt.tight_layout()
plt.savefig("charts/3_incentive.png", dpi=130)
plt.close()

# 4. Marketing lift
q4 = """
WITH monthly_agg AS (
    SELECT hcp_id, month, SUM(trx) AS trx FROM rx GROUP BY hcp_id, month
),
monthly_rx AS (
    SELECT hcp_id, month, trx,
           LAG(trx) OVER (PARTITION BY hcp_id ORDER BY month) AS prev_trx
    FROM monthly_agg
),
call_months AS (
    SELECT DISTINCT hcp_id, strftime('%Y-%m-01', call_date) AS call_month, channel
    FROM calls
)
SELECT cm.channel,
       ROUND(AVG(mr.trx - mr.prev_trx), 2) AS avg_trx_change_after_call
FROM call_months cm
JOIN monthly_rx mr ON mr.hcp_id = cm.hcp_id AND mr.month = cm.call_month
WHERE mr.prev_trx IS NOT NULL
GROUP BY cm.channel ORDER BY avg_trx_change_after_call DESC;
"""
lift = pd.read_sql(q4, conn)

plt.figure(figsize=(6, 5))
plt.bar(lift.channel, lift.avg_trx_change_after_call, color="steelblue")
plt.ylabel("Avg TRx change after call")
plt.title("4. Marketing Channel Lift")
plt.tight_layout()
plt.savefig("charts/4_marketing_lift.png", dpi=130)
plt.close()

print("1. Segmentation (sample)")
print(seg.head(), "\n")
print("2. Call plan gap by decile")
print(gap, "\n")
print("3. Incentive comp (top 5)")
print(comp.head(), "\n")
print(" 4. Marketing channel lift")
print(lift, "\n")

conn.close()
