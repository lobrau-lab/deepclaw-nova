# DeepClaw Nova agent environment

DeepClaw Nova is a local, frozen-model coding harness. Optimize the environment around the model; do not change model weights or silently download models.

## Coding loop

1. Inspect the smallest relevant set of files with `read`, `grep`, or `glob`.
2. Make the smallest safe edit.
3. Run the focused test or verification command immediately.
4. Run the full local suite before claiming completion.

## Tool contract

- Work only inside the approved workspace roots.
- Read a file before editing it.
- Prefer exact, unique edits; if an edit fails, re-read instead of guessing.
- Verify a changed file or behavior before reporting success.
- Treat tool errors as recoverable feedback, not as permission to bypass validation.

## Benchmark discipline

- Keep the model fixed; measure harness changes separately from model changes.
- Do not modify tests or benchmark fixtures to make a task pass.
- Report pass rate, tool failures, retries, and verification failures.
- Keep public benchmark gains secondary to representative held-out tasks.
