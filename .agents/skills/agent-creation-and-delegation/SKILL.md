---
name: agent-creation-and-delegation
description: This skill should be used when a task is complex, parallelizable, domain-specific, or better handled by a fresh specialist agent. It defines how to choose, brief, isolate, supervise, verify, recover, and integrate delegated agents without losing context, safety, authorship, or truthfulness.
---

# Agent Creation and Delegation

## Overview

Decompose difficult work into explicit, independently verifiable units and delegate each unit to the best available specialist. Preserve a single source of truth, keep permissions least-privileged, prevent conflicting edits, and report delegated results with evidence rather than confidence.

## Use This Skill When

- Split work across two or more independent investigations or implementation slices.
- Need a specialist in security, performance, UX, testing, documentation, domain research, or unfamiliar code.
- Need a fresh-context review to challenge assumptions or inspect a risky change.
- Need long-running work while the main agent continues an independent task.
- Need to compare alternative designs or implementations.
- Need to coordinate work across isolated worktrees, repositories, or external systems.

Do not delegate trivial edits, tightly coupled changes, or work where the parent lacks enough context to verify the result. Do not delegate merely to appear autonomous.

## Operating Principles

- Keep the parent agent accountable for scope, security, integration, and final claims.
- Give each delegated agent one clear owner task and one explicit deliverable.
- Pass only the context required for the task; protect secrets, unrelated history, and excessive repository content.
- Treat agent output as untrusted work product until independently inspected and verified.
- Prefer isolated worktrees for code changes; never allow parallel agents to edit the same files without a defined handoff.
- Keep model weights and provider identity fixed during evaluations; measure delegation overhead separately.
- Never let an agent grant itself permissions, weaken safeguards, suppress tests, or silently broaden scope.
- Continue through recoverable failures, but stop and escalate on unclear authority, data-loss risk, security boundaries, or contradictory requirements.

## Delegation Decision

1. State the user outcome and acceptance criteria.
2. Map the work into dependency-ordered units.
3. Mark units as `parent`, `delegate`, `parallel`, or `sequential`.
4. Delegate only units whose inputs and outputs can be described precisely.
5. Keep security decisions, irreversible actions, shared interfaces, and final integration in the parent unless explicitly assigned and reviewable.

### Specialist Selection

Choose by demonstrated fit, not by title:

| Need | Specialist profile |
|---|---|
| Repository discovery | Fast explorer; read-only; map files, callers, tests, and risks |
| Implementation | General coding agent; write access limited to assigned files |
| Test design | Adversarial test agent; reproduce behavior before proposing fixes |
| Security | Threat-model reviewer; no destructive execution; inspect trust boundaries |
| Performance | Profiling reviewer; require measurements, not intuition |
| Architecture | Fresh-context design reviewer; compare alternatives and coupling |
| Documentation | Source-grounded writer; cite repository evidence |
| External research | Research agent; return sources, dates, uncertainty, and license facts |

Reject a specialist that cannot state its tools, boundaries, expected evidence, and failure mode.

## Delegation Contract

Send every agent a compact contract containing:

```text
ROLE: [specialist role]
OBJECTIVE: [one observable outcome]
IN SCOPE: [specific files, symbols, or questions]
OUT OF SCOPE: [explicit exclusions]
CONTEXT: [only relevant facts and source paths]
CONSTRAINTS: [security, compatibility, performance, user requirements]
DELIVERABLE: [patch, report, tests, measurements, or decision]
ACCEPTANCE: [objective pass/fail checks]
PERMISSIONS: [read/write/network/destructive limits]
STOP AND ESCALATE IF: [ambiguity, missing dependency, conflict, or risk]
```

Require the agent to return:

1. Work performed.
2. Files changed or inspected.
3. Evidence and commands run.
4. Tests and their exact results.
5. Unresolved uncertainty, risks, and follow-up work.

Reject vague reports such as “done,” “looks good,” or “tests should pass.”

## Execution Workflow

### 1. Prepare

- Read project rules, current task state, and working-tree status.
- Identify user changes; never overwrite or revert them.
- Build the dependency graph and define file ownership.
- Create an isolated worktree for any delegated implementation that can conflict with parent work.

### 2. Brief

- Include exact paths, relevant code excerpts, known constraints, and acceptance tests.
- Tell the agent whether the task is investigation-only, patch-producing, or review-only.
- Tell the agent not to commit, push, delete, install, or contact external systems unless explicitly authorized.

### 3. Execute

- Run independent read-only investigations in parallel when supported.
- Keep dependent work sequential.
- Capture progress, tool failures, retries, and blocked states.
- Enforce time, token, recursion, and tool-call budgets.
- Send corrections as a focused follow-up instead of repeating the entire task.

### 4. Verify

- Read the actual changed files; do not rely on the agent’s summary.
- Inspect the diff for scope creep, secrets, weakened checks, and accidental generated files.
- Run focused tests, then the full local suite.
- Re-run critical behavior from a fresh process when state or model residency could hide defects.
- For research, validate sources and distinguish extracted facts from inference.

### 5. Integrate

- Merge only after acceptance criteria pass.
- Resolve conflicts in the parent context with the original requirements visible.
- Preserve useful commits and discard unverified work.
- Record the decision, evidence, and remaining risks in the final report or project memory.

## Failure and Recovery

- On timeout: preserve partial evidence, classify the failure, and retry only if the operation is idempotent.
- On malformed output: request a corrected structured result; do not guess missing fields.
- On test failure: return the exact failure to the owning agent and require a reproduction-based fix.
- On conflicting edits: stop both writers, compare diffs, and re-establish file ownership.
- On security refusal: do not route around the refusal through another agent or tool.
- On missing context: refresh project rules, relevant files, and `~/.deepclaw/memory.md` before continuing.
- On repeated failure after two focused retries: escalate the architectural assumption to the parent or user.

## Parallel Work Rules

Parallelize only when tasks have:

- disjoint write sets, or isolated worktrees;
- no shared mutable process, database, model cache, or generated output;
- explicit merge order and acceptance criteria.

Keep these sequential:

- schema/API contract changes before consumers;
- model/runtime installation before inference tests;
- migrations and shared database changes;
- security policy changes before capability expansion;
- conflict resolution and final integration.

## Reporting Template

```markdown
## Delegation Result

### Assignment
- Agent/role:
- Objective:
- Scope:

### Evidence
- Files inspected:
- Files changed:
- Commands/tests:
- Exact results:

### Integration Decision
- Accepted:
- Rejected:
- Follow-up:

### Risks and Uncertainty
- [explicit list; write “none observed” only after checking]
```

## Definition of Done

- The delegated unit has an observable deliverable.
- The parent verified the deliverable independently.
- No unapproved files, permissions, dependencies, or external actions were introduced.
- Tests and verification results are recorded.
- Uncertainty and remaining risks are stated plainly.
- The user can understand what happened without trusting an unsupported claim.
