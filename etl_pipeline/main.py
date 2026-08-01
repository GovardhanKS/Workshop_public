"""
main.py – Orchestrates the ETL pipeline:
    Extract → Transform → Load
"""

from extract import extract_data
from transform import transform_data
from load import load_data

def run_etl(
    source: str = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv",
    db_path: str = "etl.db",
    table_name: str = "iris_data",
    sort_by: str = "sepal_length"
) -> None:
    """
    Execute the full ETL workflow.

    Parameters
    ----------
    source : str
        Data source for extraction.
    db_path : str
        Destination SQLite file.
    table_name : str
        Target table name.
    sort_by : str
        Column to sort during transformation.
    """
    print("=== Starting ETL Pipeline ===")
    # 1️⃣ Extract
    raw_df = extract_data(source=source)

    # 2️⃣ Transform
    transformed_df = transform_data(df=raw_df, sort_by=sort_by)

    # 3️⃣ Load
    load_data(df=transformed_df, db_path=db_path, table_name=table_name)

    print("=== ETL Pipeline Completed Successfully ===")


if __name__ == "__main__":
    # You can adjust parameters here or expose them via CLI/environment variables.
    run_etl()