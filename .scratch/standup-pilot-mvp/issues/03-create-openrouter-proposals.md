# 03: Create reviewable OpenRouter proposals in Streamlit

**What to build:** Produce the independently testable review-interface component. A synthetic caption supplied by fake storage must be filtered, interpreted through OpenRouter, reconciled through a fake Jira-read adapter, and rendered as a non-executable Streamlit proposal. The same slice must remain demonstrable through a clearly labelled deterministic fallback when free-model inference is unavailable.

**Suggested owner:** Developer B - Streamlit and agent

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** ready-for-agent

- [ ] Streamlit presents transcript evidence, pending proposal, approval controls, and action result as distinct regions.
- [ ] A one-second Streamlit fragment refreshes transcript and proposal regions, and synthetic data becomes visible within two seconds.
- [ ] Approve and Reject controls call only the baseline fake reviewer and action interfaces; real Auth0 and Jira wiring is reserved for Ticket 05.
- [ ] Only captions containing an explicit Jira-key pattern and configured delivery language are eligible for inference.
- [ ] Ordinary conversation, missing keys, duplicate events, and events already linked to proposals do not consume OpenRouter calls.
- [ ] Only one unresolved proposal is processed at a time.
- [ ] The OpenRouter API key and related settings remain server-side.
- [ ] `openrouter/free` is the default model, while configuration can select a pinned compatible model without code changes.
- [ ] OpenRouter uses temperature zero, a short timeout, at most one retry, and a strict structured-response request.
- [ ] Validated output contains relevance, Jira key, reported state, proposed target state, supporting evidence, and confidence.
- [ ] Ticket-key mismatches, unsupported targets, invalid JSON, schema violations, timeouts, rate limits, and provider failures cannot create an unlabelled proposal.
- [ ] Fake Jira reads provide the current title, state, snapshot, and allowed transitions needed to build the branch-local proposal; Ticket 05 replaces the fake with Developer C's real adapter.
- [ ] A proposed target is shown only when the read adapter exposes a matching allowed transition.
- [ ] The proposal displays original caption evidence, displayed-speaker context, Jira title, current state, target state, inference source, and pending state.
- [ ] The model has no Jira mutation capability or credential.
- [ ] The deterministic fallback requires the same Jira key and fixed delivery vocabulary, is labelled rule-based, and continues to require validation and human approval.
- [ ] Browser speech synthesis speaks text identical to the visible proposal or result and offers manual Speak controls when autoplay is blocked.
- [ ] Caption interpretation is suppressible while StandupPilot speech is active.
- [ ] Automated tests cover all selection, structured-output, validation, fallback, speech-text, and non-mutation behavior.
- [ ] The branch passes its focused tests, formatting checks, staged-diff check, secret scan, and clean-worktree check before handoff.
- [ ] Handoff reports the branch, final commit, commands run, results, browser evidence, and remaining limitations.
