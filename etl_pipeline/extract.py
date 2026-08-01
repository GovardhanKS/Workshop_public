"""
extract.py – Pull raw data into a pandas DataFrame.

For demonstration we read a CSV from a public URL.
Replace the source with your actual data source (API, DB, file, etc.).
"""

import pandas as pd

def extract_data(source: str = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv") -> pd.DataFrame:
    """
    Load raw data from `source` and return a DataFrame.

    Parameters
    ----------
    source : str
        Path or URL to the CSV file. Default is the Iris dataset.

    Returns
    -------
    pd.DataFrame
        The extracted data.
    """
    try:
        df = pd.read_csv(source)
        print(f"[extract] Loaded {df.shape[0]} rows and {df.shape[1]} columns from {source}")
        return df
    except Exception as e:
        print(f"[extract] Failed to load data: {e}")
        raise