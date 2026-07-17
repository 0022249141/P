# Execution Plans

Use an execution plan for every multi-file, architectural, migration, data-contract, or analytical-engine change.

## Required plan structure

### 1. Objective
State the user-visible or research-visible outcome.

### 2. Jira and specification trace
List Jira key, relevant specifications, and acceptance criteria.

### 3. Current-state evidence
Identify existing modules, tests, behavior, technical debt, and unknowns. Do not infer unseen code.

### 4. Assumptions and domain questions
Separate implementation assumptions from market hypotheses. Block implementation when an unresolved definition would alter labels or backtest results.

### 5. Proposed architecture
Describe boundaries, typed contracts, dependency direction, configuration, event flow, persistence, and compatibility strategy.

### 6. File-level change map
List files to create, modify, move, deprecate, or leave untouched.

### 7. Implementation steps
Use ordered, testable vertical slices. Each step must leave the repository runnable.

### 8. Verification
Include unit, integration, regression, determinism, temporal-integrity, leakage, and performance checks as applicable.

### 9. Data and migration impact
Document schema changes, provenance effects, required rebuilds, compatibility, and rollback.

### 10. Risks and limitations
Explicitly cover look-ahead, repainting, survivorship, timezone/DST, missing spread/fill data, and proxy-vs-observation limitations.

### 11. Progress log
Maintain dated entries of completed steps, decisions, failed approaches, and remaining work.

### 12. Completion evidence
Record exact commands, test results, artifacts, changed interfaces, and acceptance-criteria status.

## Plan location
Create plans under:

`plans/<JIRA-KEY>-<short-name>.md`

A plan is a living control document, not a retrospective summary.
