"""
transform.py – Sort and clean the data using pandas.

This example sorts the DataFrame by a column (e.g., 'sepal_length')
and removes any duplicate rows.
"""

import pandas as pd

def transform_data(df: pd.DataFrame, sort_by: str = "sepal_length") -> pd.DataFrame:
    """
    Sort the DataFrame and drop duplicates.

    Parameters
    ----------
    df : pd.DataFrame
        Input data from the extraction step.
    sort_by : str
        Column name to sort by. Default is 'sepal_length'.

    Returns
    -------
    pd.DataFrame
        Transformed (sorted & deduplicated) data.
    """
    if sort_by not in df.columns:
        raise ValueError(f"[transform] Column '{sort_by}' not found in DataFrame.")

    # Sort ascending; you can change to descending if needed
    df_sorted = df.sort_values(by=sort_by, ascending=True).reset_index(drop=True)

    # Remove exact duplicate rows
    df_clean = df_sorted.drop_duplicates()

    print(f"[transform] Sorted by '{sort_by}' and removed duplicates. "
          f"Result shape: {df_clean.shape}")
    return df_clean