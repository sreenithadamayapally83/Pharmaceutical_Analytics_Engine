"""
Generates a synthetic but internally-consistent pharma commercial dataset.
Outputs messy, raw CSV files to simulate real-world CRM data extraction.
"""
import os
import random
from datetime import timedelta

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

REGIONS = ["North", "South", "East", "West", "Central"]
SPECIALTIES = ["Cardiology", "Endocrinology", "Oncology", "Neurology", "General Medicine"]
CHANNELS = ["in-person", "virtual", "email"]
PRODUCTS = ["ProductA", "ProductB"]

N_HCPS = 200
N_REPS = 20
MONTHS = pd.date_range("2025-01-01", periods=12, freq="MS")


def generate_reps():
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


def inject_noise_and_export(df, filename, date_column=None):
    """Simulates real-world CRM data decay by injecting nulls, bad dates, and duplicates."""
    df_dirty = df.copy()
    
    # 1. Inject missing values (NaN) into random columns (simulating incomplete data entry)
    if not df_dirty.empty:
        for col in df_dirty.columns:
            if col not in ['hcp_id', 'rep_id']: # Never drop primary/foreign keys
                mask = np.random.rand(len(df_dirty)) < 0.05
                df_dirty.loc[mask, col] = np.nan
    
    # 2. Corrupt date formats (simulating user input errors)
    if date_column and date_column in df_dirty.columns:
        def mess_up_date(val):
            if pd.isna(val): return val
            if random.random() < 0.1: # 10% chance to write a weird format
                try:
                    dt = pd.to_datetime(val)
                    return dt.strftime("%m/%d/%Y") # Switch from ISO to US format
                except:
                    return val
            return val
        df_dirty[date_column] = df_dirty[date_column].apply(mess_up_date)
        
    # 3. Add duplicate rows (simulating CRM sync errors)
    if len(df_dirty) > 10:
        duplicates = df_dirty.sample(n=max(1, len(df_dirty)//20)) # Duplicate ~5%
        df_dirty = pd.concat([df_dirty, duplicates], ignore_index=True)
        # Shuffle to hide the duplicates
        df_dirty = df_dirty.sample(frac=1).reset_index(drop=True)
        
    df_dirty.to_csv(filename, index=False)
    print(f"Exported dirty {filename} ({len(df_dirty)} rows)")


def main():
    # Ensure export directory exists
    os.makedirs("raw_data", exist_ok=True)

    reps_df = generate_reps()
    hcps_df = generate_hcps(reps_df)
    calls_df = generate_calls(hcps_df)
    rx_df = generate_rx(hcps_df, calls_df)
    reps_df = assign_quotas(reps_df, hcps_df, rx_df)

    # Export to CSV with intentional corruption
    inject_noise_and_export(reps_df, "raw_data/reps_export.csv")
    inject_noise_and_export(hcps_df, "raw_data/hcps_export.csv")
    inject_noise_and_export(calls_df, "raw_data/calls_export.csv", date_column="call_date")
    inject_noise_and_export(rx_df, "raw_data/rx_export.csv", date_column="month")

    print("\nSimulated CRM extraction complete. Data is raw and requires standardisation in the ETL pipeline.")

if __name__ == "__main__":
    main()