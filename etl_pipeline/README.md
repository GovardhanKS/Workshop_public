# ETL Pipeline

This repository contains a simple Extract‑Transform‑Load (ETL) pipeline written in Python.

## File Structure

```
ai_workspace/etl_pipeline/
├── extract.py      # Pull data from a CSV URL
├── transform.py    # Clean & transform the data
├── load.py         # Store the data into a SQLite database
├── main.py         # Orchestrates the three stages
├── etl.db          # SQLite database created by the pipeline
└── .ipynb_checkpoints/main-checkpoint.py  # Notebook checkpoint
```

## Usage

```bash
# Run the ETL pipeline
python3 ai_workspace/etl_pipeline/main.py
```

The script will:
1. **Extract** 150 rows from the Iris dataset.
2. **Transform**: sort by sepal length and remove duplicates.
3. **Load**: store the cleaned data into `etl.db`.

## Dependencies
- Python 3.11
- `pandas`, `sqlalchemy` (installed automatically via pip if not present)

## Extending
Feel free to modify the CSV URL in `extract.py` or add additional transformation steps in `transform.py`.

---
