# Dogfood results

The analyzer was run against three real repositories to check runtime, accuracy,
and how useful the rankings are at different scales.

| Size | Repository | Files analyzed | Edges | Time |
| --- | --- | ---: | ---: | ---: |
| Small | `pallets/markupsafe` | 13 / 13 | 11 | ~13 ms |
| Medium | `pallets/flask` | 83 / 83 | 176 | ~140 ms |
| Large | `django/django` | 1000 / 2969 | 3695 | ~1.7 s |

## What worked

- Runtime stayed acceptable up to the 1000-file cap.
- Complexity and large-file detection surfaced real hotspots in Flask and Django
  (e.g. `src/flask/app.py`, `django/db/models/query.py`).
- Entry-point detection found CLI files and console scripts.
- Issue and hub filters kept the graph readable on Flask.

## What needed fixing

- File counts read like whole-repo counts, so insights now show
  `analyzed / found source files`.
- Package `__init__.py` barrels dominated hub and cycle findings; they are now
  labeled as public API facades with lower severity instead of generic bad coupling.
- Large cycles in Django can be inflated by function-local imports. The graph does
  not yet classify edge timing, so truncated large scans should be read as partial
  rankings, not complete repo truth.

## Known follow-ups

- Classify edge timing (top-level vs lazy/local vs type-checking re-exports).
- Background jobs and backend-backed subgraph loading for very large repos.
