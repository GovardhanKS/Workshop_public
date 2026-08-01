"""
load.py – Load the transformed DataFrame into an SQLite database.

Creates a table (if it doesn't exist) matching the DataFrame columns
and inserts the rows using `to_sql`.
"""

import sqlite3
import pandas as pd

def load_data(df: pd.DataFrame,
              db_path: str = "etl.db",
              table_name: str = "iris_data",
              if_exists: str = "replace") -> None:
    """
    Store `df` into an SQLite database.

    Parameters
    ----------
    df : pd.DataFrame
        Data to be loaded.
    db_path : str
        Path to the SQLite file. Will be created if absent.
    table_name : str
        Name of the table to store the data.
    if_exists : str
        Behavior if the table already exists ('fail', 'replace', 'append').
        Default is 'replace' for a clean ETL run.
    """
    try:
        # Ensure the directory for db_path exists (optional, depends on your env)
        conn = sqlite3.connect(db_path)
        # Use pandas' built‑in SQLite writer
        df.to_sql(name=table_name, con=conn, if_exists=if_exists, index=False)
        conn.commit()
        conn.close()
        print(f"[load] Loaded {df.shape[0]} rows into '{table_name}' in {db_path}")
    except Exception as e:
        print(f"[load] Failed to load data into SQLite: {e}")
        raise