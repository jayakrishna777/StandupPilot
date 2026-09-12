# StandupPilot

A voice-enabled meeting agent that interprets live stand-up updates, reconciles them with Jira, requests human approval, and converts conversations into accountable actions.

A modified fork of Google Meet CC Capturer forwards finalized Google Meet captions to a
local FastAPI service. A Streamlit interface shows the live transcript, and when a caption
names an explicit Jira key with delivery language, StandupPilot reads the real Jira issue
and presents an evidence-backed transition proposal. An Auth0-authenticated reviewer
approves it; only then does the backend re-read Jira, execute the exact allowed transition,
and verify the resulting status before announcing it into the meeting.

The model proposes. It never writes to Jira.

## Quick start

```bash
./scripts/setup.sh        # venv, dependencies, PostgreSQL role and databases, checks
source .venv/bin/activate
./scripts/run_api.sh      # FastAPI   http://localhost:8000
./scripts/run_ui.sh       # Streamlit http://localhost:8501
```

Full instructions, prerequisites, and the list of secrets to supply: [docs/SETUP.md](docs/SETUP.md).

## Layout

| Path | Contents |
| --- | --- |
| [src/standup_pilot/contracts/](src/standup_pilot/contracts/) | Shared contracts frozen in Phase 0: caption event, agent output, proposal, action result, states, module protocols, endpoint and ports |
| [src/standup_pilot/settings.py](src/standup_pilot/settings.py) | Server-side configuration; all credentials enter here |
| [src/standup_pilot/testing/fakes.py](src/standup_pilot/testing/fakes.py) | In-memory implementations of the frozen interfaces, shared by all three branches |
| [src/standup_pilot/agent/](src/standup_pilot/agent/) | Caption prefilter, OpenRouter interpreter, rule-based fallback |
| [src/standup_pilot/api/](src/standup_pilot/api/) | FastAPI caption ingress |
| [src/standup_pilot/storage/](src/standup_pilot/storage/) | PostgreSQL repositories |
| [src/standup_pilot/jira/](src/standup_pilot/jira/) | Jira Cloud REST v3 adapter |
| [src/standup_pilot/actions/](src/standup_pilot/actions/) | Authorization and the only Jira mutation path |
| [app/](app/) | Streamlit review interface |
| [extension/](extension/) | Chrome Manifest V3 caption bridge |
| [migrations/](migrations/) | Versioned PostgreSQL migrations |

Module ownership during the parallel build: [docs/OWNERSHIP.md](docs/OWNERSHIP.md).
Specification and plan: [docs/specs/](docs/specs/).

The Ticket 01 baseline includes a health-only FastAPI shell and a placeholder-only
Streamlit shell. The extension directory declares its Node.js 20+ toolchain; caption
capture and delivery are implemented in the later meeting-bridge ticket.

## Tests

```bash
pytest tests/contracts    # frozen shared contracts
pytest                    # full suite (storage tests need the PostgreSQL test database)
ruff check . && ruff format --check .
```

## Security boundaries

- Jira, OpenRouter, Auth0, and database credentials stay server-side in the git-ignored
  `.env`. The Chrome extension authenticates with a limited meeting-session token only.
- The displayed Google Meet speaker name is evidence, never an authenticated identity, and
  never grants approval authority.
- Authentication is separate from authorization: only identities in `REVIEWER_ALLOWLIST`
  can approve a Jira change.
- Success is reported only after a post-transition Jira read verifies the target status.
