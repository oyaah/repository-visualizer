# Repository Visualizer

Local codebase map for onboarding, refactoring, and spotting bloated files.

## What ships in the MVP

- FastAPI backend that scans local directories without executing target code.
- Static dependency extraction for Python, JavaScript/TypeScript, and C/C++ includes, with support for root `.gitignore`, Python `src/` layouts, and TypeScript path aliases.
- React Flow canvas with draggable nodes, zoom, pan, search/type filters, full/neighborhood graph modes, persisted browser layouts, and an inspector panel.
- Repository insights panel for largest files, complexity hotspots, dependency hubs, unresolved references, skipped-file counts, and truncation warnings.
- AI file explanations with OpenAI or Gemini, cached by file-content hash.

## Run the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Optional AI summary keys:

```bash
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
```

Copy `backend/.env.example` if you prefer loading keys from a local env file.
Run this backend on your own machine only. It reads local paths by design and is not hardened for public hosting.

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE` only if the backend is not running on `http://127.0.0.1:8000`.

Open `http://127.0.0.1:5173`, enter a local repository path, and analyze.

For a quick demo, scan:

```text
backend/tests/fixtures/sample_repo
```

## Run with Docker

```bash
docker compose up --build
```

Older Docker installs may need `docker-compose up --build`.

Then open `http://127.0.0.1:5173`. In Docker, the project repository is mounted read-only at:

```text
/workspace/repository-visualizer
```

Use that path for the built-in demo scan, or add another bind mount to `docker-compose.yml` for a different local repository.

## Large repositories

The analyzer defaults to the first 1000 eligible source files, includes tests, and excludes vendor/generated-looking files. Raise or lower the file cap in the UI depending on the machine and repo size.

The API response includes scan metadata:

- `stats.total_files_found`
- `stats.analyzed_files`
- `stats.skipped_files`
- `stats.skipped_reasons`
- `stats.truncated`
- `stats.warnings`

The frontend displays those values and lets you filter the rendered graph by path/folder search, file extension, or one-hop neighborhood around the selected file. This keeps the app responsive without pretending every massive repo should render as one unbounded canvas.

Dragged node positions are saved in browser `localStorage` per repository and graph shape. Use `Reset layout` in the graph toolbar to return to the automatic layout.

## Test

```bash
cd backend && pytest
cd frontend && npm test
cd frontend && npm run build
```

## Known limitations

- Dependency parsing is intentionally static and bounded.
- External dependencies are tracked as metadata, not rendered as graph nodes.
- `.gitignore` support covers common root patterns and directory ignores, not every advanced Git ignore edge case.
- Very large repos still need background jobs and backend-backed subgraph loading.
- Full cyclomatic complexity and dependency-rule validation are follow-up work.
