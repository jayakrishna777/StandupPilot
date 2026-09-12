# StandupPilot Hackathon MVP Specification

## Problem Statement

Software teams discuss delivery progress in stand-up meetings, but the decisions and status changes spoken in those meetings are not reliably reflected in Jira. A developer may say that a ticket is complete while Jira still shows it as in progress. Someone must notice the mismatch, find the correct ticket, determine whether the workflow permits the requested change, update Jira, and tell the meeting that the action succeeded.

Existing assistants usually require users to leave the meeting and open a separate chat interface. The hackathon challenge instead calls for an agent that belongs in a place where people already work. StandupPilot must participate in the meeting workflow: observe Google Meet captions, reconcile explicit ticket updates with real Jira state, present an evidence-backed action for human review, and announce the verified result.

The team has no access to the CopilotKit starter kit. The implementation must use a free, fast-to-build UI and route model inference through an OpenRouter API key. The working prototype must remain narrow enough for three developers to build in parallel and integrate during the event.

## Solution

StandupPilot is a browser-assisted, voice-enabled Google Meet agent. A modified fork of Google Meet CC Capturer observes Google Meet's native captions and forwards finalized caption events, including the displayed speaker label, to a local FastAPI service. The service validates and stores the events in PostgreSQL.

A Streamlit application displays the live transcript and periodically processes relevant statements. A deterministic prefilter selects captions containing an explicit Jira ticket key and recognizable delivery language. The agent then calls OpenRouter for a structured interpretation of the statement. StandupPilot reads the referenced Jira issue and its currently allowed transitions and presents a proposal containing the original meeting evidence, current Jira state, and proposed change.

An Auth0-authenticated reviewer approves or rejects the proposal in Streamlit. Approval never relies on a spoken response or displayed Meet identity. Immediately before mutation, StandupPilot re-reads Jira, rejects stale proposals, verifies that the transition remains allowed, executes the exact transition, and re-reads Jira to confirm the resulting state. The UI shows the outcome and can speak the proposal and verified result through browser text-to-speech while the Streamlit tab is shared into Google Meet with tab audio.

The golden-path demonstration is intentionally fixed: one Google Meet meeting, one Jira project, one explicit ticket key, one proposed status transition, one authenticated approval, and one verified Jira update.

## User Stories

1. As a meeting organizer, I want StandupPilot to operate beside Google Meet, so that the team can use an agent without leaving its existing meeting workflow.
2. As a participant, I want Google Meet's native captions to provide speech text, so that I do not need to install or configure a separate transcription service.
3. As a participant, I want the caption event to include my displayed meeting name, so that the transcript has useful conversational context.
4. As a participant, I want the interface to distinguish displayed names from verified identities, so that nobody mistakes a caption label for authorization.
5. As a participant, I want to be informed that captions are being captured, so that the demonstration is transparent.
6. As a meeting organizer, I want to start and stop caption forwarding, so that I control when StandupPilot observes the meeting.
7. As a meeting organizer, I want to see whether the caption bridge is connected, retrying, or disconnected, so that I can diagnose the demonstration quickly.
8. As a reviewer, I want each completed statement to appear once, so that partial and duplicate captions do not create repeated proposals.
9. As a reviewer, I want captions without an explicit Jira ticket key to remain transcript-only, so that vague conversation cannot trigger work-item changes.
10. As a reviewer, I want only delivery-related statements to reach the model, so that the free inference quota is not wasted on ordinary conversation.
11. As a reviewer, I want the original spoken words preserved with every proposal, so that I can judge the evidence rather than trust an unexplained recommendation.
12. As a reviewer, I want StandupPilot to read the real Jira issue before proposing a change, so that the proposal reflects the system of record.
13. As a reviewer, I want to see the Jira ticket title and current status, so that I can confirm that the agent selected the intended work item.
14. As a reviewer, I want StandupPilot to fetch currently allowed Jira transitions, so that it does not assume every issue can move directly to Done.
15. As a reviewer, I want OpenRouter to return a validated structured interpretation, so that model prose cannot accidentally become an executable command.
16. As a reviewer, I want an obvious indication when the deterministic fallback created a proposal, so that I understand when model inference was unavailable.
17. As a reviewer, I want OpenRouter failures to leave the caption and Jira data visible, so that the system fails transparently.
18. As an authorized reviewer, I want to sign in through Auth0, so that consequential actions are tied to a verified application identity.
19. As an authorized reviewer, I want to approve a proposed Jira transition with a button, so that the system has explicit human authorization.
20. As an authorized reviewer, I want to reject a proposal without changing Jira, so that incorrect interpretations are safely dismissed.
21. As an unauthorized viewer, I want to view the demonstration without gaining mutation authority, so that observation and approval remain separate capabilities.
22. As a security-conscious user, I want Jira and OpenRouter credentials to remain on the server, so that browser code and repository history do not expose secrets.
23. As a Jira administrator, I want StandupPilot to use an account with only the permissions needed for the demo project, so that the integration has limited impact.
24. As an authorized reviewer, I want StandupPilot to re-read Jira immediately before execution, so that an approval cannot apply an outdated proposal.
25. As an authorized reviewer, I want stale approvals rejected, so that concurrent Jira changes are not overwritten or misrepresented.
26. As an authorized reviewer, I want repeated clicks to execute at most one Jira transition, so that UI retries cannot duplicate an action.
27. As a participant, I want StandupPilot to announce success only after Jira confirms the new status, so that the meeting does not hear a false success message.
28. As a participant, I want failed actions explained briefly in the UI, so that the team knows whether the cause was authentication, permissions, workflow state, or network uncertainty.
29. As a participant, I want the proposal and final result spoken aloud, so that the agent feels present in the meeting rather than confined to a dashboard.
30. As a meeting organizer, I want speech processing suppressed while StandupPilot speaks, so that its own output does not generate a new proposal.
31. As a demonstrator, I want a rule-based fallback for the fixed Jira-key-and-status scenario, so that transient free-model availability does not destroy the demo.
32. As a demonstrator, I want to reset the Jira ticket between rehearsals, so that the complete golden path can be shown repeatedly.
33. As a developer, I want the Chrome extension, agent UI, and Jira action service to have frozen contracts, so that three contributors can work in parallel.
34. As a developer, I want exclusive module ownership during the parallel build, so that merges do not become the critical path.
35. As an integration lead, I want every feature branch to contain focused passing tests and complete commits, so that branches can be merged predictably.
36. As a reviewer, I want a public repository with setup instructions and an example configuration, so that the submission can be inspected without exposing credentials.
37. As the original extension author, I want the fork to preserve attribution, disclose modifications, and retain the required license, so that the project complies with the source license.
38. As a hackathon judge, I want a concise end-to-end demonstration using real Jira state, so that I can distinguish a working agent from a UI mock-up.
39. As a hackathon judge, I want known limitations stated honestly, so that the prototype does not claim automatic meeting joining, biometric speaker verification, or general autonomy.
40. As the team, we want the feature scope frozen before the integration period, so that the final hour is spent rehearsing and submitting rather than adding features.

## Implementation Decisions

- The product name used by the repository and implementation is **StandupPilot**.
- The MVP is a local browser-assisted prototype. Google Meet and Streamlit run in Chrome on the organizer's computer; Jira and OpenRouter are external services.
- Google Meet CC Capturer remains the caption-capture foundation. The team will modify and distribute a fork, preserve its license and copyright notices, state that the work is derived from Google Meet CC Capturer, and document modifications.
- Google Meet native captions provide speech-to-text. The MVP does not capture or transcribe raw meeting audio.
- The captured speaker label is the displayed Google Meet name. It is contextual evidence, not verified identity and never grants approval authority.
- The extension uses Chrome Manifest V3. Its content script observes finalized captions; a background worker sends validated events to the backend.
- Caption stabilization and deduplication occur before network delivery. The backend additionally enforces uniqueness by event identifier.
- Caption delivery uses an HTTP POST endpoint on the local FastAPI service. Each request carries a limited meeting-session token rather than an OpenRouter, Auth0, or Jira credential.
- The caption endpoint returns HTTP 202 after validating and durably recording an event. Model inference is not performed inside the ingestion request.
- Python 3.11 or newer is the application language. FastAPI and Uvicorn provide the caption ingress service.
- Streamlit replaces CopilotKit. It provides the transcript, proposal, approval, result, connection status, and demonstration controls.
- Streamlit periodically refreshes only the live portions of the page. A one-second refresh interval is sufficient for the prototype and avoids a WebSocket dependency.
- PostgreSQL 16 is the required shared store between FastAPI and Streamlit. Both processes connect through the same server-side `DATABASE_URL`; there is no SQLite fallback.
- Database schema changes are applied through versioned migrations. Transactions, unique constraints, parameterized SQL, connection pooling, and UTC `TIMESTAMPTZ` values protect concurrent API writes and UI reads.
- The persisted records are meeting sessions, caption events, proposals, and action results.
- The primary agent is a narrow statement interpreter, not an open-ended autonomous loop. It converts one caption into a structured proposed Jira action.
- A deterministic prefilter requires an explicit Jira-key pattern and delivery-related language before invoking OpenRouter.
- The OpenRouter API key is supplied through server-side configuration. It is never committed, sent to the extension, or rendered into the Streamlit page.
- Model selection is configurable. The zero-cost default is `openrouter/free`; the demo can pin a more reliable compatible model through configuration without code changes.
- OpenRouter responses use a strict JSON schema when supported. The result is validated again by the application before it can become a proposal.
- The agent output includes relevance, ticket key, reported state, proposed target status, evidence text, and confidence.
- The agent cannot call the Jira mutation function. It only produces a proposal; deterministic application code owns all reads, authorization checks, and writes.
- A rule-based fallback recognizes the fixed demo vocabulary and creates a visibly labelled fallback proposal if OpenRouter times out, is rate-limited, or returns invalid structured data.
- Jira Cloud REST API v3 is the system-of-record integration.
- Jira status changes use workflow transitions. StandupPilot fetches allowed transitions and executes an exact transition identifier instead of writing a status field directly.
- The Jira integration exposes three conceptual operations: read a ticket, list allowed transitions, and execute a transition.
- Auth0 remains the identity provider. Streamlit's native OpenID Connect flow provides login state and identity claims.
- Authorization is separate from authentication. Only configured reviewer identities can approve a Jira change.
- A proposal records the Jira status and version observed when it was created. Approval re-reads the issue and rejects the proposal as stale if the relevant snapshot changed.
- Proposal states are pending, approved, rejected, stale, executed, and failed. Terminal states cannot return to pending.
- Jira execution is idempotent by proposal identifier. Repeated button clicks or retries return the recorded result rather than issuing another transition.
- Network uncertainty after a Jira write triggers a Jira re-read. StandupPilot reports success only if the target state is verified; otherwise it reports an uncertain result and does not retry the write automatically.
- Browser speech synthesis is the initial text-to-speech mechanism. The spoken words exactly match visible proposal or result text.
- The Streamlit tab must be shared into Google Meet with tab audio enabled for remote participants to hear the agent.
- Caption processing is suppressible while StandupPilot speaks to avoid feedback from its own output.
- Three developers work from one frozen baseline commit and own non-overlapping modules: meeting bridge, Streamlit/OpenRouter, and persistence/Jira/Auth0.
- Shared contracts define the caption event, proposal, action result, endpoint, session-token header, local ports, and proposal-state vocabulary before feature branches begin.
- The integration lead owns repository-wide configuration and final merges. Shared contracts change only through an explicit three-person decision.
- Feature branches are merged into a temporary integration branch. Persistence and action services merge first, Streamlit and the agent second, and the extension third.
- The submission must include a public repository, example configuration without secrets, setup instructions, known limitations, a two-minute video, project description, and sponsor-tagged social post.

## Testing Decisions

- Tests assert observable behavior rather than private implementation details. A good test supplies an event or user action at a public boundary and verifies the stored state, rendered decision, external request, or returned result.
- The primary and highest-value test seam is the complete application workflow: accept a caption event, create an evidence-backed proposal, authorize an approval, execute an allowed Jira transition, and return a verified result. OpenRouter, Auth0 identity claims, and Jira are controlled fakes at this seam so the test is deterministic.
- The extension boundary has a focused browser-fixture test because Google Meet DOM observation is outside the Python application seam. It verifies speaker extraction, stabilization, deduplication, event construction, and delivery to a mocked endpoint.
- The caption API has contract tests for valid acceptance, invalid schemas, missing or invalid session tokens, inactive sessions, oversized text, and idempotent duplicates.
- Storage tests run against PostgreSQL and verify migrations, uniqueness, state transitions, UTC timestamps, idempotent results, transaction rollback, and safe concurrent API writes and UI reads. Tests use an isolated test database or schema and remove their data afterward.
- Agent tests verify Jira-key prefiltering, suppression of irrelevant conversation, valid OpenRouter structured output, invalid output rejection, timeouts, rate limits, ticket-key mismatch rejection, and visible rule-based fallback behavior.
- Jira adapter tests use a fake HTTP transport to verify issue reads, transition discovery, exact transition identifiers, permission failures, missing issues, timeouts, and uncertain post-write outcomes.
- Approval tests verify Auth0 login requirements, reviewer allow-list enforcement, rejection without mutation, stale-snapshot detection, allowed-transition revalidation, idempotent repeated clicks, and verified success reporting.
- Speech tests verify that visible and spoken response text match and that the suppression state is active while speech is requested.
- One live Jira test project provides real-system qualification for issue read, allowed-transition discovery, transition execution, and post-transition verification. Test tickets contain fictional data and can be reset.
- One two-device Google Meet rehearsal qualifies displayed speaker names, single delivery of finalized captions, extension reconnection, and meeting-wide shared-tab audio.
- The final acceptance test uses the actual demonstration sentence and configured ticket key. It passes only when the Streamlit UI shows the spoken evidence, Jira's starting state, the pending proposal, the authenticated reviewer, and Jira's verified final state.
- There is no existing test prior art in the repository; the repository currently contains only its initial README. The tests established by this specification become the initial project convention.

## Out of Scope

- Automatic admission to or joining of Google Meet calls.
- Google Meet APIs, raw meeting audio capture, custom speech recognition, or direct audio-to-audio inference.
- Biometric voice identification or treating displayed meeting names as authenticated identity.
- Spoken approval, automatic approval, or Jira mutation without an authenticated button action.
- General conversation summarization, meeting minutes, sentiment analysis, or open-ended agent chat.
- Jira issue creation, editing descriptions, assigning users, commenting, sprint management, or bulk changes.
- Microsoft Teams, Slack, Zoom, email, calendar, and additional work-management systems.
- Multi-tenant SaaS operation, production deployment, horizontal scaling, and high-availability infrastructure.
- Hosted persistence, Redis, message queues, background-worker platforms, or WebSocket infrastructure.
- Mobile applications or packaged desktop applications.
- Commercial distribution of the modified caption extension without a separate licensing review or permission from its author.
- A polished design system beyond the clear Streamlit controls needed for the demonstration.
- Reliance on free-model availability as the only demonstration path.

## Further Notes

- The golden path is: a participant says that an explicit Jira ticket is fixed; the caption bridge forwards the completed statement; StandupPilot reads Jira; the agent proposes an allowed target state with evidence; an Auth0-authorized reviewer approves; the backend revalidates and executes the transition; StandupPilot verifies and announces the result.
- The extension license includes Commons Clause and additional terms. The hackathon fork must retain notices, publish modifications under the required terms, disclose changes, and obtain participant consent for caption capture. A future commercial product should replace this dependency or obtain explicit permission.
- The free OpenRouter router is appropriate for low-volume prototyping but may vary in provider, latency, and availability. The model slug remains configurable and the deterministic fallback is part of the acceptance criteria.
- PostgreSQL 16.15 is installed on the development host. The server must be started and pass a readiness check before implementation or tests begin; installation alone is not treated as a working database dependency.
- The repository had no issue-tracker configuration or triage-label vocabulary when this specification was created. This specification is stored in the repository but is not published as an issue or labelled `ready-for-agent`.
- The scope should not expand until the complete golden path passes twice from separate meeting devices.
