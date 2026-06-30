# Three-Repository Dogfood Run - 2026-06-30

## Repositories

| Size | Repository | Files analyzed | Edges | Time | Payload |
| --- | --- | ---: | ---: | ---: | ---: |
| Small | `pallets/markupsafe` | 13 / 13 | 11 | 12.9 ms | 9.9 KB |
| Medium | `pallets/flask` | 83 / 83 | 176 | 139.4 ms | 87.6 KB |
| Large | `django/django` | 1000 / 2969 | 3695 | 1697.0 ms | 1621.1 KB |

## What Held Up

- Runtime was acceptable through the 1000-file cap.
- Large/complex file detection found real hotspots in Flask and Django.
- Entry point detection found console scripts and CLI files after metadata support.
- Issue/hub presets made the graph usable enough on Flask.

## What Was Misleading

- File counts looked like whole-repo counts even though only supported source files are analyzed.
- Package `__init__.py` files dominated hub and cycle findings even when they were public API barrels.
- Large SCCs in Django can be inflated by lazy/function-local imports; the current graph does not classify edge timing.
- Truncated large scans should be treated as partial rankings, not complete repo truth.

## Fixes Made

- Insights now show `analyzed / found source files`.
- Start-here findings include confidence labels.
- Package `__init__.py` hubs are labeled as public API facades with lower severity/confidence.
- Package-facade cycles are caveated instead of treated as plain import-time knots.

## Post-Fix Check

- `markupsafe`: `src/markupsafe/__init__.py` remains large/complex, but its hub role is now `api_facade` with low severity and medium confidence.
- `flask`: `src/flask/app.py` remains high-confidence complexity; `src/flask/__init__.py` is demoted to API facade.
- `django`: `django/db/models/query.py` and `django/db/models/sql/query.py` remain the useful high-confidence hotspots; `django/conf/__init__.py` and `django/db/__init__.py` are API facades instead of generic bad hubs.

## Deferred

- Edge timing taxonomy: top-level, lazy/local, conditional, type-checking, re-export.
- Method/class hotspot ranking inside large files.
- AST extraction cache and streamed graph output for very large repos.
