# Repository Visualizer

Local codebase map for onboarding, refactoring, and spotting bloated files.

## What ships in the MVP

- FastAPI backend that scans local directories without executing target code.
- Static dependency extraction for Python, JavaScript/TypeScript, and C/C++ includes.
- React Flow canvas with draggable nodes, zoom, pan, metrics, and inspector panel.
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

## Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`, enter a local repository path, and analyze.

## Test

```bash
cd backend && pytest
cd frontend && npm test
```

## Known limitations

- Dependency parsing is intentionally static and bounded.
- External dependencies are tracked as metadata, not rendered as graph nodes.
- Saved canvas layouts are in-memory only.
- Full cyclomatic complexity and dependency-rule validation are follow-up work.

