---
title: "feat: Add package summaries and cycle detection"
type: feat
status: completed
date: 2026-06-29
---

# feat: Add package summaries and cycle detection

## Summary

Add backend-owned folder summaries and static dependency-cycle detection to the existing graph response, then surface both in the current insights panel.

## Problem Frame

Large repository scans currently show useful file-level hotspots, but users still need package-level context and a fast way to spot circular dependencies.

## Requirements

- R1. The analyzer returns deterministic folder summaries for analyzed files only.
- R2. The analyzer returns local dependency cycles without executing target code.
- R3. The insights panel displays backend-provided folder summaries and cycles without adding a new endpoint.
- R4. Existing graph, summary, filter, and OpenAI behavior remain unchanged.

## Key Technical Decisions

- **Extend `GraphResponse`:** keep `/api/analyze` as the single graph contract instead of adding a second summary endpoint.
- **Use strongly connected components for cycles:** detect cycles in `O(nodes + edges)` from local graph edges and return each component once.
- **Keep UI rendering shallow:** the frontend displays summaries and lets users select a representative cycle member; it does not recompute backend metrics.

## Implementation Units

### U1. Backend graph summaries

- **Goal:** Add folder summaries and cycle summaries to the graph API response.
- **Requirements:** R1, R2, R4.
- **Dependencies:** None.
- **Files:** `backend/app/models.py`, `backend/app/graph.py`, `backend/tests/test_graph.py`, `backend/tests/test_api.py`.
- **Approach:** Add typed summary models, compute folder metrics after node metrics are finalized, and detect local edge cycles with a tiny SCC helper.
- **Patterns to follow:** `backend/app/graph.py` deterministic sorting, `backend/tests/test_graph.py` fixture-style graph assertions.
- **Test scenarios:** Verify root and nested folders aggregate file count and LoC. Verify a two-file import loop returns one cycle. Verify an acyclic graph returns no cycles. Verify the API response includes the new fields.
- **Verification:** Backend tests pass and `/api/analyze` still returns existing node, edge, stats, and ignored-directory data.

### U2. Insights rendering

- **Goal:** Render backend summaries and cycles in the existing insights panel.
- **Requirements:** R3, R4.
- **Dependencies:** U1.
- **Files:** `frontend/src/types/graph.ts`, `frontend/src/components/RepositoryInsights.tsx`, `frontend/src/styles.css`, `frontend/tests/repository-insights.test.tsx`.
- **Approach:** Extend frontend graph types, replace client-derived top folders with API summaries, and add a compact cycles section that selects the first file in a cycle.
- **Patterns to follow:** Existing `FolderList`, `InsightList`, and `repository-insights.test.tsx` fixture style.
- **Test scenarios:** Verify folder summaries render from `graph.folder_summaries`. Verify cycle rows render member paths and count. Verify clicking a cycle selects the first cycle member. Verify the empty/no-cycle fallback remains readable.
- **Verification:** Frontend tests and build pass.

## Scope Boundaries

- No semantic runtime analysis of decorators, `Depends`, or route registration.
- No background jobs or backend-backed subgraph loading.
- No AI calls for package summaries.
