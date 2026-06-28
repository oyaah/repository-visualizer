# Demo Notes

1. Start backend from `backend/`.
2. Start frontend from `frontend/`.
3. Analyze the absolute path to `backend/tests/fixtures/sample_repo`.
4. Click `app/main.py` and inspect local imports, unresolved imports, LoC, and complexity.
5. Click "Explain file" without an API key to show the disabled AI state.
6. Set `OPENAI_API_KEY` or `GEMINI_API_KEY` and retry to show cached summaries on the second request.
7. For a scale demo, clone a large public repo outside this project and analyze it with a lower max-file cap first.
8. Use the graph search and extension filter to narrow the canvas instead of dragging through every file manually.

## Large repo validation

Django was used as the scale smoke test because it is large enough to expose rendering and scan-limit behavior without needing private code. Before scan limits, a direct analyzer run returned 3035 nodes and 8936 edges in about 3.7 seconds. With the default UI cap, the app now reports truncation metadata and renders a bounded graph.

## Commit story

- `feat: scaffold repository visualizer mvp`
- `chore: ignore generated build artifacts`
- `feat: harden graph analysis coverage`
- `feat: expose ai provider selection`
- `feat: add bounded repository analysis`
- `feat: add large graph controls`

Keep later commits similarly small and real.
