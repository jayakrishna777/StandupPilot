# 03: Create evidence-backed Jira proposals through OpenRouter

**What to build:** Deliver a complete proposal slice in which a stored caption containing an explicit Jira key and delivery update is selected deterministically, interpreted through OpenRouter, reconciled with current Jira evidence, and displayed in Streamlit as a non-executable proposal. If free-model inference is unavailable or invalid, the fixed demonstration vocabulary produces a clearly labelled rule-based proposal rather than silently fabricating a model response.

**Suggested owner:** Developer B - Streamlit and agent

**Blocked by:** 01: Establish the runnable StandupPilot foundation

**Status:** ready-for-agent

- [ ] The live Streamlit view presents transcript evidence separately from pending proposals and action results.
- [ ] A caption must contain an explicit Jira-key pattern before it is eligible for model inference.
- [ ] A caption must contain configured delivery language before it is eligible for model inference.
- [ ] Ordinary conversation and captions without Jira keys remain visible but do not consume OpenRouter requests.
- [ ] An event already associated with a proposal is not interpreted again.
- [ ] Only one unresolved proposal is processed at a time for the hackathon workflow.
- [ ] The OpenRouter key, model, application title, and referring site are supplied only through server configuration.
- [ ] The zero-cost default model route is configurable and can be replaced with a pinned compatible model without changing application code.
- [ ] OpenRouter is called with a short timeout, deterministic sampling, bounded retry behavior, and a requested structured response.
- [ ] The returned interpretation is validated before use and contains relevance, Jira key, reported state, proposed target state, supporting evidence, and confidence.
- [ ] A response containing a Jira key different from the caption is rejected.
- [ ] A response containing an unsupported target state is rejected.
- [ ] Current Jira title, state, and allowed transitions are obtained through the frozen read-only Jira seam before the proposal is presented.
- [ ] The proposed target is shown only when Jira currently exposes a matching allowed transition.
- [ ] The proposal displays the original caption evidence, displayed speaker context, Jira title, current state, proposed state, inference source, and pending status.
- [ ] The model has no capability or credential that can mutate Jira.
- [ ] Invalid structured data, timeouts, rate limits, and provider failures are visible to the reviewer and do not create an unlabelled proposal.
- [ ] The deterministic fallback requires the same explicit Jira key and fixed delivery vocabulary, is visibly labelled rule-based, and still requires Jira validation and human approval.
- [ ] The proposal and verified-result regions can speak their exact visible text using browser speech synthesis.
- [ ] Manual Speak controls remain available when browser autoplay is blocked.
- [ ] Caption interpretation can be suppressed while StandupPilot speech is active to prevent feedback.
- [ ] Automated tests cover selection, non-selection, valid structured output, schema failures, key mismatch, unsupported targets, timeout, rate limit, provider failure, fallback, and non-mutation.

