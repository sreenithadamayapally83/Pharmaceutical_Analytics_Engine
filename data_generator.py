"""
Generates a synthetic but internally-consistent pharma commercial dataset:
reps, hcps (doctors), calls (visit log), rx (monthly prescriptions).

The data has a real signal baked in on purpose, so the SQL analyses in
queries.sql find something meaningful:
  - higher potential_score -> more calls AND higher baseline TRx
  - a call in a given month gives that HCP's TRx a small bump that month
  - some high-potential HCPs are deliberately under-called (gap to find)

Run: python data_generator.py
Produces: pharma_analytics.db
"""
import random
import sqlite3
from datetime import timedelta

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

DB_PATH = "pharma_analytics.db"
SCHEMA_PATH = "schema.sql"

REGIONS = ["North", "South", "East", "West", "Central"]
SPECIALTIES = ["Cardiology", "Endocrinology", "Oncology", "Neurology", "General Medicine"]
CHANNELS = ["in-person", "virtual", "email"]
PRODUCTS = ["ProductA", "ProductB"]

N_HCPS = 200
N_REPS = 20
MONTHS = pd.date_range("2025-01-01", periods=12, freq="MS")


def build_schema(conn):
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())


def generate_reps():
    # quota is filled in later, once we know each rep's realized panel output,
    # so attainment % ends up spread realistically around 100% instead of random
    rows = []
    for rep_id in range(1, N_REPS + 1):
        region = random.choice(REGIONS)
        rows.append((rep_id, f"Rep_{rep_id}", region, None))
    return pd.DataFrame(rows, columns=["rep_id", "rep_name", "region", "quarterly_quota"])


def assign_quotas(reps_df, hcps_df, rx_df):
    panel_actuals = (
        hcps_df.merge(rx_df.groupby("hcp_id", as_index=False)["trx"].sum(), on="hcp_id", how="left")
        .fillna({"trx": 0})
        .groupby("assigned_rep_id")["trx"].sum()
    )
    reps_df = reps_df.copy()
    reps_df["quarterly_quota"] = reps_df.rep_id.map(
        lambda rid: int(panel_actuals.get(rid, 4000) * random.uniform(0.75, 1.30) / 100) * 100
    )
    return reps_df


def generate_hcps(reps_df):
    rows = []
    for hcp_id in range(1, N_HCPS + 1):
        region = random.choice(REGIONS)
        potential = int(np.clip(np.random.normal(50, 20), 5, 99))
        region_reps = reps_df[reps_df.region == region]
        if region_reps.empty:
            region_reps = reps_df
        rep_id = region_reps.sample(1, random_state=hcp_id).iloc[0].rep_id
        rows.append((hcp_id, random.choice(SPECIALTIES), region, potential, int(rep_id)))
    return pd.DataFrame(
        rows, columns=["hcp_id", "specialty", "region", "potential_score", "assigned_rep_id"]
    )


def generate_calls(hcps_df):
    rows = []
    call_id = 1
    for _, hcp in hcps_df.iterrows():
        # Higher potential -> more calls on average, but with noise so some
        # high-potential HCPs end up genuinely under-served (for the gap query).
        expected_calls = hcp.potential_score / 10
        n_calls = max(0, int(np.random.poisson(expected_calls * 0.7)))
        n_calls = min(n_calls, 12)
        if n_calls > 0:
            call_months = random.sample(list(MONTHS), k=n_calls)
            for m in call_months:
                call_date = m + timedelta(days=random.randint(0, 27))
                channel = random.choices(CHANNELS, weights=[0.5, 0.35, 0.15])[0]
                rows.append((call_id, int(hcp.assigned_rep_id), int(hcp.hcp_id),
                             call_date.date().isoformat(), channel))
                call_id += 1
    return pd.DataFrame(rows, columns=["call_id", "rep_id", "hcp_id", "call_date", "channel"])


def generate_rx(hcps_df, calls_df):
    rows = []
    rx_id = 1
    calls_df = calls_df.copy()
    calls_df["call_month"] = pd.to_datetime(calls_df.call_date).values.astype("datetime64[M]")

    for _, hcp in hcps_df.iterrows():
        hcp_call_months = set(calls_df.loc[calls_df.hcp_id == hcp.hcp_id, "call_month"])
        base = hcp.potential_score * random.uniform(0.8, 1.2)
        for product in PRODUCTS:
            running = base * random.uniform(0.35, 0.55)
            for m in MONTHS:
                bump = 1.15 if pd.Timestamp(m) in hcp_call_months else 1.0
                running = max(running * bump + np.random.normal(0, 3), 0)
                trx = int(running)
                nrx = int(trx * random.uniform(0.10, 0.25))
                rows.append((rx_id, int(hcp.hcp_id), product, m.date().isoformat(), trx, nrx))
                rx_id += 1
    return pd.DataFrame(rows, columns=["rx_id", "hcp_id", "product", "month", "trx", "nrx"])


def main():
    conn = sqlite3.connect(DB_PATH)
    build_schema(conn)

    reps_df = generate_reps()
    hcps_df = generate_hcps(reps_df)
    calls_df = generate_calls(hcps_df)
    rx_df = generate_rx(hcps_df, calls_df)
    reps_df = assign_quotas(reps_df, hcps_df, rx_df)

    reps_df.to_sql("reps", conn, if_exists="append", index=False)
    hcps_df.to_sql("hcps", conn, if_exists="append", index=False)
    calls_df.to_sql("calls", conn, if_exists="append", index=False)
    rx_df.to_sql("rx", conn, if_exists="append", index=False)
    conn.commit()

    print(f"reps: {len(reps_df)} | hcps: {len(hcps_df)} | calls: {len(calls_df)} | rx rows: {len(rx_df)}")
    conn.close()


if __name__ == "__main__":
    main()
