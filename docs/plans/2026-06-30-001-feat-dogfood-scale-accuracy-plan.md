---
title: "feat: Dogfood and improve scale accuracy"
type: feat
status: completed
date: 2026-06-30
execution: code
---

# feat: Dogfood and improve scale accuracy

## Goal

Make the tool more useful on real repositories without changing the core product: local FastAPI analysis, React Flow graph, static dependencies, OpenAI summaries, and exportable reports.

## Scope

- Dogfood against a real GitHub repo and record findings.
- Improve dependency and entry-point accuracy where the dogfood run exposes cheap wins.
- Make report findings explain why they matter.
- Add graph presets for large repos.
- Replace the README screenshot with one that shows useful output, not graph soup.

## Non-Goals

- No database, background worker, vector search, auth, hosted mode, or agent chat.
- No framework-specific parser rewrite.
- No screenshot/GIF machinery beyond one useful README image.

## Implementation

1. Add static metadata scanning for `package.json`, `pyproject.toml`, and `requirements.txt` so entry points and external context are less blind.
2. Tighten parser coverage for Python `from package import name` and dynamic JS imports with tests.
3. Enrich `start_here` details with impact context: imported-by counts, related files, and ambiguity where relevant.
4. Add graph presets: hide tests, hide leaves, hubs, issues.
5. Dogfood on `pallets/flask`, save a short report, capture a better screenshot, and update README.

## Verification

- `cd backend && .venv/bin/pytest`
- `cd frontend && npm test -- --run`
- `cd frontend && npm run build`
- Analyze the dogfood repo and confirm report/export/graph presets work.
