<div align="center">

# Deepsearch MiroFish

**Prompt-driven web research seeds for local multi-agent social simulation.**

</div>

## What This Project Does

Deepsearch MiroFish turns a scenario prompt into a source-grounded research seed, then uses that seed to prepare and run a local social simulation.

Instead of asking the user to upload a "reality seed" document, the app performs web research first:

1. The user enters a scenario prompt.
2. The backend generates search queries and uses SearXNG to retrieve web results.
3. Source pages are fetched and summarized into an enriched `web_research.md` seed document.
4. The seed document becomes the starting corpus for ontology generation and Neo4j graph construction.
5. The app prepares agents, runs the local simulation, generates a report, and supports report-grounded interaction.

The default stack is local-first:

- Frontend: Vue + Vite
- Backend: Flask
- Search: SearXNG
- Graph storage: Neo4j Community Edition
- LLM and embeddings: Ollama
- Simulation runtime: OASIS / CAMEL components

No `ZEP_API_KEY` is required. No real cloud `LLM_API_KEY` is required for the default local Ollama setup.

## Built Upon

This project is built upon and adapted from:

- Original MiroFish: https://github.com/666ghj/MiroFish
- MiroFish-Offline fork: https://github.com/nikmcfly/MiroFish-Offline

The current workspace continues the offline fork with prompt-driven web research seed generation and the Deepsearch MiroFish frontend positioning.

## Workflow

1. **Web Research Seed** - Generate a source-grounded markdown seed from the scenario prompt using SearXNG search, source fetching, and local LLM summarization.
2. **Graph Build** - Generate ontology from the seed, extract entities and relationships, and build a Neo4j knowledge graph.
3. **Environment Setup** - Create simulation configuration and agent profiles from the graph and research context.
4. **Simulation** - Run local multi-agent interaction over the generated scenario environment.
5. **Report** - Generate a structured report from simulation output and graph evidence.
6. **Interaction** - Ask follow-up questions against the report and simulated context.

## Ports

Default local ports:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:5001`
- Neo4j Browser: `http://localhost:7474`
- Neo4j Bolt: `bolt://localhost:7687`
- Ollama: `http://localhost:11434`
- SearXNG: `http://localhost:8080`

When using ngrok, expose the frontend port:

```bash
ngrok http 3000
```

## Prerequisites

- Conda
- Python 3.11
- Node.js 18+ and npm
- Docker, for local Neo4j and SearXNG
- Ollama, running on the host machine

Pull the default local models:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

You can use a larger chat model by setting `LLM_MODEL_NAME`, for example `qwen2.5:14b` or `qwen2.5:32b`, if your hardware can run it.

## Recommended Run Path In This Workspace

From the parent workspace root:

```bash
cd /path/to/persona_simulation
./scripts/run_local_mirofish.sh
```

The script starts or checks:

- SearXNG on port `8080`
- Neo4j on ports `7474` and `7687`
- Flask backend on port `5001`
- Vue frontend on port `3000`

It uses the Conda environment named `mirofish` by default.

Useful overrides:

```bash
CONDA_ENV=mirofish \
LLM_MODEL_NAME=qwen2.5:7b \
FRONTEND_PORT=3000 \
FLASK_PORT=5001 \
./scripts/run_local_mirofish.sh
```

If you only want the backend:

```bash
START_FRONTEND=false ./scripts/run_local_mirofish.sh
```

## Manual Setup

Run these commands from the `MiroFish-Offline` directory unless noted otherwise.

### 1. Create the Python environment

```bash
conda create -n mirofish python=3.11 -y
conda run -n mirofish pip install -r backend/requirements.txt
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Start Ollama

```bash
ollama serve
```

In another terminal:

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

### 4. Start Neo4j

```bash
docker run -d \
  --name mirofish-neo4j-host \
  --network host \
  -e NEO4J_AUTH=neo4j/mirofish \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=2g \
  -v mirofish-offline_neo4j_data:/data \
  -v mirofish-offline_neo4j_logs:/logs \
  docker.io/library/neo4j:5.18-community
```

### 5. Start SearXNG with JSON enabled

```bash
mkdir -p .cache/searxng
cat > .cache/searxng/settings.yml <<'YAML'
use_default_settings: true
search:
  formats:
    - html
    - json
server:
  limiter: false
  public_instance: false
YAML

docker run -d \
  --name mirofish-searxng \
  -p 8080:8080 \
  -v "$PWD/.cache/searxng:/etc/searxng:rw" \
  docker.io/searxng/searxng:latest
```

### 6. Configure environment variables

```bash
cp .env.example .env
```

Default local values:

```bash
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:7b
OLLAMA_NUM_CTX=8192

EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=mirofish

WEB_RESEARCH_ENABLED=true
WEB_RESEARCH_SEARXNG_URL=http://localhost:8080

OPENAI_API_KEY=ollama
OPENAI_API_BASE_URL=http://localhost:11434/v1
FLASK_PORT=5001
```

### 7. Start the backend

```bash
cd backend
conda run -n mirofish --no-capture-output python run.py
```

The backend should respond at:

```bash
curl http://localhost:5001/health
```

### 8. Start the frontend

In another terminal:

```bash
cd frontend
VITE_API_BASE_URL=/api npm run dev -- --host 0.0.0.0 --port 3000
```

Open:

```text
http://localhost:3000
```

## Docker Compose Notes

`docker-compose.yml` starts the app, Neo4j, and Ollama containers, but the current web research flow also needs a JSON-enabled SearXNG service. For the most complete local run in this workspace, prefer the helper script from the parent workspace root:

```bash
./scripts/run_local_mirofish.sh
```

If you use Docker Compose directly, make sure SearXNG is also running and set:

```bash
WEB_RESEARCH_ENABLED=true
WEB_RESEARCH_SEARXNG_URL=http://host.docker.internal:8080
```

Container-to-container networking may require service-name URLs instead of `localhost`.

## Hardware Guidance

Minimum practical development setup:

- RAM: 16 GB
- Disk: 20 GB free
- CPU: 4 cores
- GPU: recommended for local LLM speed

Model guidance:

- `qwen2.5:7b`: lighter local development
- `qwen2.5:14b`: better quality if hardware allows
- `qwen2.5:32b`: heavier runs with stronger reasoning, requires substantially more memory

## Troubleshooting

Check backend health:

```bash
curl http://localhost:5001/health
```

Check SearXNG JSON output:

```bash
curl 'http://localhost:8080/search?q=test&format=json'
```

Check Ollama models:

```bash
ollama list
```

If the first research or ontology request is slow, Ollama may be cold-starting the model. Let the request continue or warm the model manually:

```bash
curl http://localhost:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen2.5:7b","prompt":"ping","stream":false}'
```

## License

AGPL-3.0. See [LICENSE](./LICENSE).

## Credits

Deepsearch MiroFish is based on:

- https://github.com/666ghj/MiroFish
- https://github.com/nikmcfly/MiroFish-Offline

The simulation runtime uses OASIS / CAMEL components from the CAMEL-AI ecosystem.
