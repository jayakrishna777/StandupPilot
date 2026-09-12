# 04: Approve and verify Jira transitions securely

**What to build:** Deliver a complete governed-action slice in which a reviewer signs into Streamlit through Auth0, reviews a seeded evidence-backed proposal, and either rejects it without side effects or approves it for a single Jira transition. Approval revalidates Jira state and workflow permissions, prevents stale or repeated execution, and reports success only after the resulting Jira status is verified.

**Suggested owner:** Developer C - Jira actions and authentication

**Blocked by:** 01: Establish the runnable StandupPilot foundation

**Status:** ready-for-agent

- [ ] Streamlit uses its native OpenID Connect flow with Auth0 and exposes the authenticated identity needed for application authorization.
- [ ] Real Auth0 configuration is excluded from version control, while a complete non-secret example is provided.
- [ ] Authentication alone does not grant mutation authority; the authenticated identity must also match the configured reviewer allow-list.
- [ ] Unauthenticated and authenticated-but-unauthorized viewers cannot execute Jira transitions.
- [ ] Displayed Google Meet speaker labels and spoken approval never grant authorization.
- [ ] The Jira integration reads the configured real issue and reports its title, current status, snapshot identity, URL, and currently allowed transitions.
- [ ] Jira credentials remain server-side and are redacted from logs and user-visible errors.
- [ ] Rejecting a pending proposal records the reviewer decision and performs no Jira mutation.
- [ ] Approving a proposal records the authenticated reviewer identity and decision time.
- [ ] Approval reloads the pending proposal rather than trusting browser-provided Jira state.
- [ ] Approval re-reads Jira immediately before mutation and compares it with the proposal snapshot.
- [ ] A changed Jira snapshot marks the proposal stale and performs no transition.
- [ ] Approval fetches currently allowed Jira transitions again and uses the exact transition identifier returned by Jira.
- [ ] A transition that is no longer allowed fails without attempting an alternative workflow action.
- [ ] Each proposal can issue at most one Jira transition even when the approval button is clicked repeatedly or the request is retried.
- [ ] After a Jira transition response, StandupPilot re-reads the issue before reporting success.
- [ ] Success is stored and displayed only when the post-transition status matches the approved target state.
- [ ] A timeout or uncertain network result triggers a read-back check and never an automatic repeated write.
- [ ] Permission denial, missing issue, stale state, disallowed transition, verified failure, and uncertain result are distinguishable to the reviewer.
- [ ] PostgreSQL storage preserves sessions, proposals, decisions, and action results with UTC timestamps, legal state transitions, unique execution identity, and transaction-safe concurrent approval handling.
- [ ] Automated tests exercise unauthenticated access, unauthorized identity, rejection, valid approval, stale approval, disallowed transition, repeated approval, permission denial, missing issue, timeout, uncertain write, verified success, and credential redaction.
- [ ] A fictional Jira test issue passes a real read, allowed-transition discovery, transition, and post-transition verification cycle and can be reset for rehearsal.
