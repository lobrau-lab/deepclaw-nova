# Implementation Plan: Benchmaxxed Nova Harness

## Overview

Improve the existing frozen-model agent harness without changing model weights. The first slice targets the highest-confidence friction points visible in the repository: a working-tree regression that bypasses workspace safety, weak tool-call boundary validation, missing model-specific harness guidance, and traces that cannot explain tool failures.

## Scope

- Restore the hardened execution path.
- Add small model-family profile data for prompt and edit-format guidance.
- Validate tool calls before handlers run and record boundary outcomes.
- Add a deterministic benchmark covering safe tool execution, edit recovery, and traceability.

Out of scope: changing model weights, adding a new inference backend, public-benchmark scraping, or automatic prompt evolution.

## Tasks

1. Restore safe command execution and add regression coverage.
2. Add profile-driven system/tool guidance and bounded edit recovery.
3. Add tool-boundary validation and trace metadata.
4. Add a deterministic harness benchmark and run the full suite.

## Risks

- Existing local modifications are user work; edits will be limited to the harness path and tests.
- Tool schemas are JSON-like rather than backed by a validation dependency, so validation will remain intentionally small and conservative.
- The benchmark measures harness behavior, not raw model intelligence; held-out task evaluation remains a follow-up.
