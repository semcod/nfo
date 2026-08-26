# Ticket 001: Route NFO analysis through SubLLM

- **ID**: ticket-001
- **Owner**: founder
- **Status**: ACTIVE
- **Created**: 2026-08-26

## Goal and scope

Replace the default LiteLLM log-analysis transport with the public
`subactor-subllm` API and the exact `semcod-nfo/analyze` route. Keep LiteLLM
only as an explicit operator-selected compatibility mode.

## Acceptance criteria

- [x] Production analysis uses public SubLLM and central provider policy.
- [x] Direct Z.AI GLM 5.3 is the policy-owned default.
- [x] A failed SubLLM request is not replayed to another paid provider.
- [x] Legacy LiteLLM requires explicit opt-in and a separate extra.
- [x] CI covers the supported Python 3.11 through 3.13 range.
- [x] Tests cover routing and fail-closed behavior.
