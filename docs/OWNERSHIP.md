# Module ownership during the parallel phase

Frozen in Phase 0. Only the owner edits these paths until the integration phase.

| Path | Owner | Tickets |
| --- | --- | --- |
| `extension/` | Developer A | A1-A4 |
| `app/`, `src/standup_pilot/agent/` | Developer B | B1-B4 |
| `src/standup_pilot/storage/`, `src/standup_pilot/api/`, `src/standup_pilot/jira/`, `src/standup_pilot/actions/`, `migrations/` | Developer C | C1-C4 |
| `src/standup_pilot/contracts/`, `src/standup_pilot/settings.py`, `src/standup_pilot/testing/`, `scripts/`, `.env.example`, `.gitignore`, `pyproject.toml` | Developer B as integration lead | Phase 0 |

Tests follow the same ownership: `tests/extension/` (A), `tests/agent/` and `tests/ui/` (B),
`tests/storage/`, `tests/api/`, `tests/jira/`, `tests/actions/` (C), `tests/contracts/` (shared).

## Shared contracts are frozen

`src/standup_pilot/contracts/` defines the caption event, agent output, ticket snapshot,
proposal, action result, proposal states, module protocols, the caption endpoint, the
session-token header, and the local ports. Changing anything there requires agreement
from all three developers, and all three update their tests in the same change.

## Branches

- Developer A: `feat/meeting-bridge`
- Developer B: `feat/streamlit-openrouter`
- Developer C: `feat/jira-actions-auth`

All three start from the baseline commit `chore: scaffold StandupPilot and freeze
integration contracts`. Developer B creates `integration/standup-pilot` from the same
commit and merges C, then B, then A, each with `--no-ff`.

## Conflict ownership

- Extension conflicts: Developer A.
- Streamlit and agent conflicts: Developer B.
- Persistence, API, Jira, authentication, and action conflicts: Developer C.
- Shared-contract conflicts stop the merge until all three agree.
