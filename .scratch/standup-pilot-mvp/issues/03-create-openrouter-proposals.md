# 03: Create reviewable OpenRouter proposals in Streamlit

**What to build:** Produce the independently testable review-interface component. A synthetic caption supplied by fake storage must be filtered, interpreted through OpenRouter, reconciled through a fake Jira-read adapter, and rendered as a non-executable Streamlit proposal. The same slice must remain demonstrable through a clearly labelled deterministic fallback when free-model inference is unavailable.

**Suggested owner:** Developer B - Streamlit and agent

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** complete (Ticket 03 review-interface scope)

**Evidence (2026-09-12):**

- Branch: `main` (working directly on the ticket branch structure in use at the time; no sibling-branch parity check was performed here).
- New/changed modules: `src/standup_pilot/agent/openrouter.py` (OpenRouter client), `src/standup_pilot/agent/interpreter.py` (prefilter, rule-based fallback, `build_proposal`, `process_next_caption` orchestration), `src/standup_pilot/agent/speech.py` (shared visible/spoken text formatters), `src/standup_pilot/agent/demo_data.py` (demo-only Jira fixture), `app/streamlit_app.py` (review shell, rewritten on top of the existing UI).
- Focused tests: `pytest tests/agent tests/ui -q` → 39 passed (18 orchestration/prefilter, 8 OpenRouter-transport, 5 speech-text, 4 shell, plus prefilter/openrouter/interpreter split across files).
- Full suite: `pytest -q` → 79 passed, 0 failed.
- Static checks: `ruff check .` and `ruff format --check .` both clean.
- `git diff --cached --check` clean (no trailing-whitespace/conflict-marker issues staged).
- Secret scan: manually inspected the diff; no API keys, tokens, or `.env` contents are staged. `git status --porcelain` shows only source/test files.
- Runtime smoke: FastAPI health-only app and the rewritten Streamlit shell both started under their `scripts/run_api.sh` / `scripts/run_ui.sh` launchers; `GET /healthz` returned 200 and Streamlit served `HTTP 200` with no exceptions or deprecation warnings in `logs/api.log` / `logs/ui.log`.

- [x] Streamlit presents transcript evidence, pending proposal, approval controls, and action result as distinct regions.
- [x] A one-second Streamlit fragment (`live_regions`, `run_every=UI_REFRESH_SECONDS`) refreshes transcript and proposal regions; a synthetic caption is processed on its next tick, well within two seconds.
- [x] Approve and Reject controls call only `st.session_state.action_service` (`StubActionService`) and `is_authorized`; no Auth0 or real Jira write path exists in this ticket.
- [x] `prefilter_caption` requires an explicit Jira-key pattern plus configured delivery language before either inference path runs.
- [x] Ordinary conversation, missing keys, and already-linked captions never reach OpenRouter (`test_irrelevant_captions_are_linked_and_never_reoffered`, `test_only_one_unresolved_proposal_is_processed_at_a_time`); duplicate `event_id`s are deduplicated by `InMemoryCaptionStore.add_caption`.
- [x] `process_next_caption` returns early with an explanation when a proposal is already pending; only one is ever created per session.
- [x] `OPENROUTER_API_KEY` and related settings are read only via `standup_pilot.settings.Settings`, never rendered into the page or sent to the extension.
- [x] `openrouter_model` defaults to `openrouter/free`; the model, base URL, timeout, and retry count are all configuration-driven.
- [x] `OpenRouterClient` sends `temperature: 0`, a configured timeout, at most one retry (only on timeout/rate-limit), and a strict `json_schema` `response_format`.
- [x] `AgentOutput` (validated by both the OpenRouter and rule-based paths) carries relevance, ticket key, reported state, proposed target status, evidence text, and confidence.
- [x] Ticket-key mismatches, invalid JSON, schema violations, timeouts, rate limits, and provider errors all raise a typed `OpenRouterError` and fall back to the labelled rule-based interpreter rather than ever producing an unlabelled proposal (`tests/agent/test_openrouter.py`, `tests/agent/test_interpreter.py`).
- [x] `seed_demo_jira_reader()` (a `FakeJiraReader`) supplies title, current status, snapshot, and allowed transitions for the branch-local proposal; nothing here is imported by Ticket 05.
- [x] `build_proposal` only creates a proposal when `output.proposed_target_status` matches one of `jira_reader.allowed_transitions(...)`'s `to_status` values (`test_unsupported_target_produces_no_proposal`).
- [x] The proposal card shows the caption evidence, Jira title, current/target status, inference source, and confidence; state is always `pending` at creation (`Proposal.state` default).
- [x] `build_proposal` never calls anything but `read_ticket`/`allowed_transitions` on the `JiraReader` (`test_build_proposal_never_calls_anything_but_read_methods_on_jira_reader` uses a reader with no mutation method at all); OpenRouter has no Jira import or credential.
- [x] The rule-based fallback (`interpret_caption_rule_based`) requires the same explicit key and fixed `DELIVERY_STATUS_MAP` vocabulary, is labelled `InferenceSource.RULE_BASED` in the UI badge, and still requires `is_authorized` + Approve/Reject.
- [x] `standup_pilot.agent.speech` formatters are the single source of both the visible text (proposal card, result card) and the `speak_text(...)` argument; manual "🔊 Speak proposal" / "🔊 Speak result" buttons replay the same text for blocked-autoplay browsers.
- [x] `speak_text` sets `st.session_state.suppress_until`; `live_regions` passes `suppress=time.time() < suppress_until` into `process_next_caption`, which returns immediately without consuming a caption while true (`test_suppressed_processing_does_not_consume_the_caption`).
- [x] Automated tests cover prefilter selection, OpenRouter structured-output success/failure, schema validation, ticket-key mismatch, fallback labelling, allowed-transition gating, one-at-a-time processing, suppression, and speech-text identity (`tests/agent/`).
- [x] `pytest -q` (79 passed), `ruff check .`, `ruff format --check .`, and `git diff --cached --check` all pass; `git status --porcelain` confirms no secrets or unrelated files are staged.
- [x] Handoff: see the Evidence block above for commands, results, and runtime smoke; browser-audio verification (actually hearing `speechSynthesis` speak) was not performed in this non-interactive environment - the text-identity guarantee is verified at the formatter level instead. This is the one open item before a live demo rehearsal.

**Remaining limitations:** Real Auth0 authentication, PostgreSQL-backed storage, and the real Jira adapter remain Ticket 04/05's job behind the same frozen interfaces. The demo Jira fixture (`demo_data.py`) is intentionally not part of any frozen contract. Live browser speech-synthesis audio has not been manually verified; only the shared text-formatting functions are tested.
