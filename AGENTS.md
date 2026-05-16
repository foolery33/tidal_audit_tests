# AGENTS.md

## Project Context

This project is an automated audit suite for the TIDAL service. It contains pytest tests that verify public page availability, handling of unknown URLs, service metadata endpoints, and saved reference HTML snapshots.

The `html_pages/` directory contains saved pages from the TIDAL service and should be used as reference material when the structure, selectors, or expected page behavior are unclear.

## Rules For Codex

1. After making edits, check whether any generated, local, temporary, or reference files should be added to `.gitignore`.
2. When the structure of TIDAL pages is unclear, inspect `html_pages/`; it contains saved pages from the service.
3. Do not run tests automatically unless the user explicitly asks for it. After edits, only mention which tests should be run when verification is needed.
