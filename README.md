# Claude Workshop Public Repository

Welcome to the **Claude Workshop Public** repository. This repository hosts all the code and documentation for the workshop that covers recent exercise on how to build and run AI‑powered data‑engineering pipelines.

## Project Structure


- **etl_pipeline** – Lightweight CSV‑to‑SQLite pipeline demo.
- **git_MCP_server** – Minimal GitHub MCP server used for test connection scripts.


## Getting Started

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run a sub‑project
uvicorn app.main:app --reload
```

## Contributing

Feel free to fork, open issues, or submit pull requests. All changes should pass `pytest` and keep style consistent.

## License

None

---
**Happy Coding!**
**Note : Most of the pipeline and content are made from public resource with help of AI, AI makes mistakes"**
