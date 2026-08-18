"""
ETL Pipeline for Pharma Analytics Engine.
Extracts raw CSVs, transforms (cleans, standardises schemas), and loads to SQLite.
"""
import os
import sqlite3
import pandas as pd

DB_PATH = "pharma_analytics.db"
SCHEMA_PATH = "schema.sql"
RAW_DATA_DIR = "raw_data"

def build_schema(conn):
    """Initializes the SQLite database with the defined schema."""
    print("Initializing database schema...")
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

def extract_data():
    """Extracts raw data from CSV exports."""
    print("Extracting raw data...")
    reps_df = pd.read_csv(os.path.join(RAW_DATA_DIR, "reps_export.csv"))
    hcps_df = pd.read_csv(os.path.join(RAW_DATA_DIR, "hcps_export.csv"))
    calls_df = pd.read_csv(os.path.join(RAW_DATA_DIR, "calls_export.csv"))
    rx_df = pd.read_csv(os.path.join(RAW_DATA_DIR, "rx_export.csv"))
    return reps_df, hcps_df, calls_df, rx_df

def transform_reps(df):
    """Cleans the reps dataframe."""
    df = df.drop_duplicates(subset=['rep_id']).copy()
    
    # Impute missing quota with the median quota to maintain statistical distribution
    median_quota = df['quarterly_quota'].median()
    df['quarterly_quota'] = df['quarterly_quota'].fillna(median_quota)
    
    # Ensure datatypes
    df['quarterly_quota'] = df['quarterly_quota'].astype(int)
    return df

def transform_hcps(df):
    """Cleans the hcps dataframe."""
    df = df.drop_duplicates(subset=['hcp_id']).copy()
    
    # Impute missing potential score with median
    median_score = df['potential_score'].median()
    df['potential_score'] = df['potential_score'].fillna(median_score)
    df['potential_score'] = df['potential_score'].astype(int)
    
    # Impute missing specialty with a placeholder
    df['specialty'] = df['specialty'].fillna('Unknown')
    return df

def transform_calls(df):
    """Cleans the calls dataframe."""
    df = df.drop_duplicates(subset=['call_id']).copy()
    
    # Standardise date schema: Force all dates to ISO format (YYYY-MM-DD)
    # The errors='coerce' turns completely unparseable dates into NaT (Not a Time)
    df['call_date'] = pd.to_datetime(df['call_date'], format='mixed', errors='coerce')
    
    # Drop rows where the date is entirely missing or unparseable, as they are useless for timeline analysis
    df = df.dropna(subset=['call_date']).copy()
    
    # Convert back to standard string format for SQLite
    df['call_date'] = df['call_date'].dt.strftime('%Y-%m-%d')
    
    # Impute missing channels
    df['channel'] = df['channel'].fillna('unknown')
    return df

def transform_rx(df):
    """Cleans the rx dataframe."""
    df = df.drop_duplicates(subset=['rx_id']).copy()
    
    # Standardise date schema
    df['month'] = pd.to_datetime(df['month'], format='mixed', errors='coerce')
    df = df.dropna(subset=['month']).copy()
    df['month'] = df['month'].dt.strftime('%Y-%m-%d')
    
    # Impute missing prescription numbers with 0 (safe assumption for missing data in this context)
    df['trx'] = df['trx'].fillna(0).astype(int)
    df['nrx'] = df['nrx'].fillna(0).astype(int)
    return df

def load_data(conn, reps_df, hcps_df, calls_df, rx_df):
    """Loads the cleaned dataframes into the SQLite database."""
    print("Loading data into SQLite...")
    reps_df.to_sql("reps", conn, if_exists="replace", index=False)
    hcps_df.to_sql("hcps", conn, if_exists="replace", index=False)
    calls_df.to_sql("calls", conn, if_exists="replace", index=False)
    rx_df.to_sql("rx", conn, if_exists="replace", index=False)

def main():
    conn = sqlite3.connect(DB_PATH)
    
    # Build fresh schema
    build_schema(conn)
    
    # Extract
    raw_reps, raw_hcps, raw_calls, raw_rx = extract_data()
    
    # Transform (Clean and standardise)
    print("Transforming and standardising schemas...")
    clean_reps = transform_reps(raw_reps)
    clean_hcps = transform_hcps(raw_hcps)
    clean_calls = transform_calls(raw_calls)
    clean_rx = transform_rx(raw_rx)
    
    # Load
    load_data(conn, clean_reps, clean_hcps, clean_calls, clean_rx)
    
    conn.commit()
    print("ETL Pipeline complete. Data is clean and ready for analysis.")
    conn.close()

if __name__ == "__main__":
    main()