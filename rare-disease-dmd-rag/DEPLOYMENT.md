# Deployment Guide

This covers three ways to run DMD Clinical Trial Intelligence -- local (for
development), Podman/Docker (for a shareable, reproducible environment), and
a lightweight always-on server setup -- plus the operational tasks around
each (refreshing data, resource sizing, monitoring).

Nothing here requires rebuilding the search index per request. The index
(`data/index_tfidf.pkl`) is built once, ahead of time, and every API/UI
request just searches it -- see [ARCHITECTURE.md](ARCHITECTURE.md) for
why that's safe even under repeated API calls.

## 1. Local (development)

```bash
pip install -r requirements.txt

# Build the index once (also whenever data/raw/*.json changes)
python -m rag.embed_store

# Terminal 1
uvicorn api.main:app --reload --port 8000

# Terminal 2
streamlit run ui/app.py
```

- API: http://localhost:8000 (docs at http://localhost:8000/docs)
- UI: http://localhost:8501

This is what you want while developing -- fastest iteration, easiest to
debug.

## 2. Docker / Podman compose -- one command up, one command down

The `Dockerfile` and `docker-compose.yml` in this repo are plain
OCI/Compose -- no Docker-specific features -- verified working with both
Docker and rootless Podman (podman 4.9 + podman-compose 1.6, the same
combo tested end-to-end for this doc):

```bash
docker compose up --build      # start both services, rebuilding if needed
docker compose down            # stop and remove both containers
```

```bash
# or, with Podman instead of Docker:
podman compose up --build
# if your podman doesn't have the built-in compose provider (`podman
# compose config` errors with "looking up compose provider failed" --
# true on a stock podman 4.9 install): pip install podman-compose, then
# the same `podman compose ...` commands work via that provider.
podman compose down
```

This builds one image and runs two containers from it -- `api` on port
8000 and `ui` on port 8501 -- both mounting `./data` so the index and raw
JSON persist across container restarts and are shared between the two
services. `down` removes both containers cleanly (verified: ports free
immediately after, no orphaned state) -- `up` next time reuses the
already-built image unless `--build` is passed or the Dockerfile/
requirements.txt changed.

Configure the pluggable backends via a `.env` file next to
`docker-compose.yml` (all optional -- omit entirely for the same
extractive/TF-IDF defaults as running locally). This file is read
automatically by `docker compose`/`podman compose` for the `${VAR}`
substitutions in `docker-compose.yml`, and is `.dockerignore`'d so it's
never baked into the image itself -- only ever passed in at container
runtime:

```
LLM_MODE=llm
OPENAI_API_BASE=https://api.groq.com/openai/v1
MODEL_NAME=openai/gpt-oss-20b
OPENAI_API_KEY=<your key>
EMBEDDING_BACKEND=tfidf
RERANK=0
```

To point containers at an LLM server running on the host (Ollama, or the
local llama.cpp setup below), use `http://host.containers.internal:<port>/v1`
instead of `localhost` -- that's podman's equivalent of Docker's
`host.docker.internal` (supported on podman 4.7+; on older podman, run
with `--network=host` instead and use `localhost` directly).

The MCP server (`mcp_server/server.py`) isn't part of `up`/`down` -- it's a
stdio tool an MCP client spawns on demand, not a persistent networked
service. Run it ad hoc against the same image:

```bash
docker compose run --rm api sh -c "pip install -r requirements-mcp.txt && python -m mcp_server.server"
```

To refresh data inside the container environment:

```bash
podman compose run --rm api python -m ingestion.fetch_trials
podman compose run --rm api python -m rag.embed_store
```

(Restart the `api`/`ui` containers afterward so their in-memory index
cache -- see `rag/embed_store.py`'s `get_store()` -- picks up the rebuilt
file; it's loaded once per process.)

### Using a local llama.cpp model instead of the extractive default

If you already have llama.cpp built with a model downloaded (e.g. under
`~/llama.cpp/build/bin/llama-server` and
`~/llama.cpp/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf`), run it directly
on the host rather than containerizing it -- a host-compiled binary
dropped into a container with a different base image risks missing
shared libraries, and there's no benefit to re-downloading a model you
already have:

```bash
~/llama.cpp/build/bin/llama-server \
  -m ~/llama.cpp/models/Llama-3.1-8B-Instruct-Q4_K_M.gguf \
  --host 0.0.0.0 --port 8080
```

Then, whether the API/UI run natively or in podman containers, point
them at it:

```
LLM_MODE=llm
OPENAI_API_BASE=http://localhost:8080/v1          # native API/UI
# or, from inside a podman container:
OPENAI_API_BASE=http://host.containers.internal:8080/v1
MODEL_NAME=llama3.1
```

`agents/llm.py` falls back to the extractive summary automatically if
this endpoint is unreachable, so nothing breaks if the llama-server isn't
running.

## 3. Always-on server (small VM / on-prem box)

For something more permanent than a laptop demo but without a full
container orchestrator:

1. Clone the repo, create a venv, `pip install -r requirements.txt`, run
   `python -m rag.embed_store` once.
2. Run the API under a process manager so it restarts on crash/reboot,
   e.g. **systemd**:

   ```ini
   # /etc/systemd/system/dmd-rag-api.service
   [Service]
   WorkingDirectory=/opt/dmd-clinical-trial-intelligence
   ExecStart=/opt/dmd-clinical-trial-intelligence/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
   Restart=always
   Environment=LLM_MODE=extractive

   [Install]
   WantedBy=multi-user.target
   ```

   Same pattern for the UI, pointing `ExecStart` at
   `.venv/bin/streamlit run ui/app.py --server.address 0.0.0.0`.
3. Put a reverse proxy (nginx/Caddy) in front for TLS if this is
   reachable outside a private network.
4. Schedule ingestion refreshes with cron, e.g. weekly:

   ```cron
   0 3 * * 1 cd /opt/dmd-clinical-trial-intelligence && .venv/bin/python -m ingestion.fetch_trials && .venv/bin/python -m ingestion.fetch_literature && .venv/bin/python -m rag.embed_store && systemctl restart dmd-rag-api dmd-rag-ui
   ```

   `fetch_regulatory.py` and the `regulatory_guidance_dmd.json` seed file
   are curated/manual (see README and ARCHITECTURE.md) -- re-verify those
   by hand rather than cron-refreshing them blindly.

## Resource sizing

This is intentionally light:

- **TF-IDF backend (default)**: no GPU, no model download. The index is a
  few tens of MB on disk regardless of corpus size; fits comfortably in
  under 512 MB RAM per process. A single small VM (1 vCPU, 1-2 GB RAM)
  runs API + UI fine for moderate traffic.
- **HF/Chroma backend** (`EMBEDDING_BACKEND=hf`): downloads and loads
  `BAAI/bge-base-en-v1.5` (~400 MB) into memory per process -- budget at
  least 2 GB RAM if you switch to this, and expect a slower cold start
  (model download + load).
- **LLM_MODE=llm**: no local compute cost if pointed at a remote endpoint
  (Groq, HF Inference). If pointed at a local llama.cpp/Ollama server --
  e.g. the `Llama-3.1-8B-Instruct-Q4_K_M.gguf` setup above, a ~4.9 GB
  file -- budget 6-8 GB RAM for that server process alone, separate from
  whatever the API/UI containers use. Run it natively on the host (not
  in a container) as described above.

Since `get_store()` caches the loaded index in memory per process (see
[ARCHITECTURE.md](ARCHITECTURE.md)), each `uvicorn`/`streamlit` worker
pays the load cost once at startup, not per request -- so it's safe to
run this on modest hardware even under sustained query traffic.

## Health checks

- `GET /health` -- liveness (always cheap, no corpus access).
- `GET /stats` -- corpus size + query counters; useful as a readiness
  check that the index actually loaded (all counts > 0).
