# ticket-005: Bounded, lossless JSONL producer

- Status: IN_PROGRESS
- Workflow state: EDIT

Planfile PLF-005; [issue #10](https://github.com/semcod/nfo/issues/10); dependency of maskservice/c2004#738.

SESSION_EXECUTION_AUTHORIZATION: user continued the accepted logger-bound task.

AC-01: Explicit constructor/environment opt-in, legacy default unchanged.
AC-02: Persistent cross-process path lock before opening active file.
AC-03: Complete raw segments and oversized records preserved; no archive pruning.
AC-04: Concurrent writers, process death, opaque tails, symlinks and I/O failure checks.
AC-05: Exact protected Python3.11/3.12/3.13 checks and independent Validator publication.

Local qualification: 54 tests pass; pinned Docs completion passes. Frozen oldsource2d74 fails20 regression checks (0 setup errors). Release0.2.25. Protectedmatrix andindependentValidator remain pending; notDONE.
