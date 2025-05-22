# Active Context

This file tracks the project's current status, including recent changes, current goals, and open questions.
2025-05-21 22:46:13 - Log of updates made.

*

## Current Focus

*   Initializing Memory Bank.

## Recent Changes

*   Created `memory-bank/productContext.md`.

## Open Questions/Issues

*
---
2025-05-21 23:41:53 - Updated after resolving sqlite3 datetime warnings.

## Current Focus

*   Updating Memory Bank after resolving `sqlite3` `DeprecationWarning`s.

## Recent Changes

*   Resolved `sqlite3` `DeprecationWarning`s in `src/data_manager.py` by implementing custom `datetime` adapter and converter functions.
*   Modified `src/data_manager.py` to use `import datetime as dt` and updated relevant function calls.
*   Ensured `detect_types` is enabled in `sqlite3.connect()`.

## Open Questions/Issues

*   (None directly from the resolved task)