
-- 1. SEGMENTATION
-- Bucket HCPs into potential deciles and actual-Rx deciles so you can see
-- who's "high potential, low actual" (grow), "high/high" (maintain), etc.
WITH hcp_rx AS (
    SELECT hcp_id, SUM(trx) AS total_trx
    FROM rx
    GROUP BY hcp_id
)
SELECT
    h.hcp_id, h.specialty, h.region, h.potential_score,
    COALESCE(r.total_trx, 0)                                   AS total_trx,
    NTILE(10) OVER (ORDER BY h.potential_score DESC)           AS potential_decile,
    NTILE(10) OVER (ORDER BY COALESCE(r.total_trx, 0) DESC)    AS actual_decile
FROM hcps h
LEFT JOIN hcp_rx r ON r.hcp_id = h.hcp_id;


-- 2. CALL PLAN GAP ANALYSIS
-- Compare actual call frequency against an "ideal" cadence by potential
-- decile, and flag what % of each decile is under-served.
WITH call_counts AS (
    SELECT hcp_id, COUNT(*) AS call_count
    FROM calls
    GROUP BY hcp_id
),
segmented AS (
    SELECT hcp_id, potential_score,
           NTILE(10) OVER (ORDER BY potential_score DESC) AS decile
    FROM hcps
)
SELECT
    s.decile,
    SUM(CASE
            WHEN COALESCE(c.call_count, 0) <
                 CASE WHEN s.decile <= 2 THEN 12
                      WHEN s.decile <= 5 THEN 6
                      ELSE 2 END
            THEN 1 ELSE 0
        END)                                    AS under_served,
    COUNT(*)                                      AS total_hcps
FROM segmented s
LEFT JOIN call_counts c ON c.hcp_id = s.hcp_id
GROUP BY s.decile
ORDER BY s.decile;


-- 3. INCENTIVE COMPENSATION CALCULATOR
-- Attribute TRx to each rep via their assigned HCP panel (not via the call
-- log, which would double-count), compute quota attainment %, and apply a
-- tiered payout: 0 below 80%, linear ramp 80-100%, accelerator above 100%.
WITH rep_actuals AS (
    SELECT h.assigned_rep_id AS rep_id, SUM(r.trx) AS actual_trx
    FROM hcps h
    JOIN rx r ON r.hcp_id = h.hcp_id
    GROUP BY h.assigned_rep_id
)
SELECT
    reps.rep_id, reps.rep_name, reps.quarterly_quota,
    COALESCE(a.actual_trx, 0)                                          AS actual_trx,
    ROUND(100.0 * COALESCE(a.actual_trx, 0) / reps.quarterly_quota, 1) AS attainment_pct
FROM reps
LEFT JOIN rep_actuals a ON a.rep_id = reps.rep_id
ORDER BY attainment_pct DESC;
-- payout tiering is applied in analysis.py (easier to express than in SQL)


-- 4. MARKETING / CALL-CHANNEL LIFT
-- For each HCP-month, compare TRx to the prior month. Where a call
-- happened that month, average the TRx change by channel used.
WITH monthly_agg AS (
    SELECT hcp_id, month, SUM(trx) AS trx
    FROM rx
    GROUP BY hcp_id, month
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
SELECT
    cm.channel,
    ROUND(AVG(mr.trx - mr.prev_trx), 2) AS avg_trx_change_after_call
FROM call_months cm
JOIN monthly_rx mr ON mr.hcp_id = cm.hcp_id AND mr.month = cm.call_month
WHERE mr.prev_trx IS NOT NULL
GROUP BY cm.channel
ORDER BY avg_trx_change_after_call DESC;