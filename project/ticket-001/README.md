# ticket-001: Fix Docker healthchecks, SQLite example loops, CLI env setup, and adopt Wellmanifest baseline standards

- **Status**: IN_PROGRESS
- **Workflow state**: VERIFIED

SESSION_EXECUTION_AUTHORIZATION: user requested implementation and publication across Semcod and Subactor.

## Acceptance Criteria
- [x] AC-01: Use 15s healthcheck interval/start_period and curl probe, wire env in _setup_logger, and hoist SQLite queries outside loops in examples (0 PERF-AUDIT findings).
- [x] AC-02: Adopt Wellmanifest `baseline` profile standards in `.governance/`.
