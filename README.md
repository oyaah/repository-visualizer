# Repository Visualizer

A local codebase map for onboarding, refactoring, and spotting bloated files. Point it at a
directory and it statically extracts the dependency graph, ranks the files worth reading first,
and shows the blast radius of any file you select — without executing the target code.

![Repository Visualizer mapping its own backend: dependency graph on the left, ranked "Start here" insights on the right](docs/assets/repository-visualizer.png)

## Why use it

Reading a new codebase file-by-file is slow and you rarely start in the right place. Repository
Visualizer gives you a map and a reading order instead.

- **Start with the queue, not the graph.** The right-side **Start here** panel ranks the first
  files worth inspecting — dependency cycles, bloated files, complexity hotspots, broken imports,
  and dependency hubs — each with a confidence label. It also lists likely entry points and a
  suggested reading order for onboarding.
- **Inspect one file at a time.** Click a risky file and the side panel shows its local
  dependencies, who imports it, the second-order change impact, and the tests likely affected by a
  change. Switch the graph to **Neighborhood** mode to focus on just that file's one-hop graph when
  the full map gets noisy.
- **Hand off the analysis.** Export a Markdown report to paste into notes, share with a teammate,
  or keep as a snapshot before a refactor.

## What it does

- Scans local directories without running any of the target code.
- Static dependency extraction for Python, JavaScript/TypeScript, and C/C++ includes — with support
  for root `.gitignore`, Python `src/` layouts, and TypeScript path aliases.
- A React Flow canvas with draggable nodes, zoom/pan, search and type filters, full and
  neighborhood modes, browser-persisted layouts, and an inspector panel.
- Ranked insights: "Start here" actions, entry points, reading order, largest files, complexity
  hotspots, dependency hubs, unresolved references, skipped-file counts, and truncation warnings.
- Per-file blast radius: direct dependents, second-order dependents, and likely affected tests.
- Optional AI file explanations via OpenAI, cached by file-content hash and prompt version.

## Quickstart

Backend (FastAPI):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend (Vite + React):

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, enter a local repository path, and analyze. For a quick demo, scan
`backend/tests/fixtures/sample_repo`.

Set `VITE_API_BASE` only if the backend is not on `http://127.0.0.1:8000`. To enable AI summaries,
`export OPENAI_API_KEY=...` (or copy `backend/.env.example`). The backend reads local paths by
design — run it on your own machine only; it is not hardened for public hosting.

## Run with Docker

```bash
docker compose up --build
```

Older Docker installs may need `docker-compose up --build`. The project repository is mounted
read-only at `/workspace/repository-visualizer`; use that path for the demo scan, or add another
bind mount in `docker-compose.yml` for a different local repository.

## Large repositories

The analyzer defaults to the first 1000 eligible source files, includes tests, and excludes
vendor/generated-looking files. Adjust the file cap in the UI to match the machine and repo size.
Each response carries scan metadata — `total_files_found`, `analyzed_files`, `skipped_files`,
`skipped_reasons`, `truncated`, and `warnings` — which the UI surfaces so a partial scan is never
mistaken for the whole repo.

To keep the canvas responsive, filter the rendered graph by path/folder search, file extension, or
the one-hop neighborhood around the selected file. Dragged node positions are saved per repository
in browser `localStorage`; use `Reset layout` to return to the automatic layout.

See [docs/dogfood.md](docs/dogfood.md) for results from running the analyzer against markupsafe,
flask, and django.

## Tests

```bash
cd backend && pytest
cd frontend && npm test && npm run build
```

## Known limitations

- Dependency parsing is intentionally static and bounded.
- External dependencies are tracked as metadata, not rendered as graph nodes.
- `.gitignore` support covers common root and directory patterns, not every advanced edge case.
- Very large repos still need background jobs and backend-backed subgraph loading.
- Full cyclomatic complexity and dependency-rule validation are follow-up work.
