---
title: "feat: Harden Large Repository Analysis"
type: feat
status: completed
date: 2026-06-28
---

# feat: Harden Large Repository Analysis

## Summary

This plan improves the repository visualizer for large local codebases by adding configurable scan policy, user-visible truncation metadata, frontend filtering controls, and scale-focused tests/docs. It keeps the current synchronous MVP architecture, but prevents the UI from blindly rendering unbounded graphs.

---

## Problem Frame

The MVP can analyze a large public repo such as Django, but returning and rendering thousands of files by default makes the canvas hard to use and easy to overload. The next useful step is not a queue system yet; it is honest limits, clear warnings, and controls that let users narrow the graph without hardcoded repo-specific behavior.

---

## Requirements

- R1. Users can configure maximum analyzed files and whether tests/vendor-like files are included before starting a scan.
- R2. Backend responses include total discovered files, analyzed files, skipped counts, truncation state, and warning messages.
- R3. Large-repo behavior is generic across repositories, using policy-based ignores and limits rather than fixture-specific or Django-specific rules.
- R4. The frontend lets users search/filter the visible graph and see large-graph warnings without losing access to node metrics and summaries.
- R5. Tests cover scan policy, duplicate-edge prevention, API metadata, and frontend controls.

---

## Key Technical Decisions

- **Keep analysis synchronous for this iteration:** Job queues and subgraph APIs are the right long-term architecture, but they would be a bigger feature than the deadline needs. Scan limits and warnings reduce risk now while leaving room for background jobs later.
- **Make scan policy explicit in the API:** `AnalyzeRequest` should carry max files and include/exclude flags so behavior is reproducible from UI, tests, and scripts.
- **Return metadata with the graph:** The frontend should not infer truncation or skipped files from node counts. Backend-owned metadata keeps the UI honest.
- **Filter after analysis on the frontend:** Search and extension filters make the canvas usable without requiring a new backend query protocol.

---

## Implementation Units

### U1. Add Backend Scan Policy and Metadata

- **Goal:** Add configurable limits and response metadata to the scanner, graph builder, and API.
- **Requirements:** R1, R2, R3
- **Dependencies:** None
- **Files:** `backend/app/models.py`, `backend/app/scanner.py`, `backend/app/graph.py`, `backend/app/main.py`, `backend/tests/test_scanner.py`, `backend/tests/test_graph.py`, `backend/tests/test_api.py`
- **Approach:** Introduce a scan options model, skip vendor/generated/test files through reusable predicates, cap analyzed files deterministically, preserve ignored directory reporting, and dedupe dependency edges.
- **Patterns to follow:** Existing Pydantic request/response models and pytest fixture style.
- **Test scenarios:** Analyze a synthetic repo with a low max-file limit and expect truncation metadata; disable tests/vendor files and expect generic path/name-based skipping; duplicate imports should produce one edge; invalid max-file values should be rejected by the API contract.
- **Verification:** Backend tests pass and a direct Django scan reports bounded analyzed files plus warnings.

### U2. Add Frontend Large-Graph Controls

- **Goal:** Add scan controls, visible metadata, warnings, and graph filtering.
- **Requirements:** R1, R2, R4
- **Dependencies:** U1
- **Files:** `frontend/src/types/graph.ts`, `frontend/src/api/client.ts`, `frontend/src/components/RepoPathForm.tsx`, `frontend/src/App.tsx`, `frontend/src/graph/GraphCanvas.tsx`, `frontend/src/styles.css`, `frontend/tests/graph-view.test.tsx`
- **Approach:** Extend the analyze request shape, render max-files/tests/vendor controls in the form, display backend warnings, and filter nodes/edges by search text plus extension while keeping selected-node behavior stable.
- **Patterns to follow:** Current component-local state and existing Vitest/Testing Library tests.
- **Test scenarios:** Submitting options sends the expected API payload; a warning appears for truncated graphs; search hides non-matching nodes and keeps matching edges only when both endpoints remain visible.
- **Verification:** Frontend tests and production build pass; Browser smoke test works against the sample repo and Django checkout.

### U3. Document and Validate Large-Repo Workflow

- **Goal:** Make the large-repo behavior reproducible for demos and reviewers.
- **Requirements:** R2, R3, R5
- **Dependencies:** U1, U2
- **Files:** `README.md`, `docs/demo-notes.md`, `docs/plans/2026-06-28-001-feat-large-repo-hardening-plan.md`
- **Approach:** Document scan defaults, privacy/localhost caveats, Django-scale validation, and mark the plan completed after verification.
- **Patterns to follow:** Existing README setup sections and demo notes.
- **Test scenarios:** Documentation should name the commands/workflow without embedding machine-specific paths.
- **Verification:** Final backend tests, frontend tests, build, browser smoke, Django scan, git status, and push all complete cleanly.

---

## Scope Boundaries

- **Deferred to Follow-Up Work:** Background analysis jobs, cancellation, persisted graph snapshots, backend neighborhood/subgraph APIs, AST-grade JavaScript parsing, and `.gitignore` parity belong in later commits.
- **Out of Scope:** Hardcoded behavior for any specific public repository, hosted multi-user scanning, and sending source files to OpenAI without the existing explicit local API-key setup.

---

## Risks & Dependencies

- Very large repos can still exceed the synchronous request model if users raise limits aggressively.
- Regex dependency parsing remains approximate for complex Python, TypeScript, and C/C++ build systems.
- Frontend filtering improves usability, but true large-graph exploration eventually needs backend-backed aggregation or neighborhood loading.

---

## Sources & Research

- Subagent review identified full-graph rendering, hardcoded ignores, duplicate edges, and missing scale tests as the top gaps.
- A local Django checkout produced 3035 nodes and 8936 edges in roughly 3.7 seconds before this hardening pass, which is enough to expose canvas usability issues without requiring repo-specific fixes.
