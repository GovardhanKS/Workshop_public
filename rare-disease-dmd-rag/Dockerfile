FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build the TF-IDF index at image build time so the container starts
# ready to serve -- it's cheap (seconds, tens of MB) for this corpus size.
# Re-run `python -m rag.embed_store` (or rebuild the image) after refreshing
# data/raw/*.json via the ingestion/ scripts.
RUN python -m rag.embed_store

EXPOSE 8000 8501

# Overridden by docker-compose.yml's `command:` per service; this default
# just runs the API if the image is used standalone.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
