# 05: Integrate the live meeting golden path

**What to build:** Combine the independently qualified meeting-input, proposal, and governed-action slices into one coherent StandupPilot demonstration. A participant's completed Google Meet caption must become an evidence-backed OpenRouter or visibly rule-based proposal, receive an Auth0-authorized review decision, change Jira through an allowed transition, and produce a visible and audible verified result without duplicate processing or unsafe fallback behavior.

**Suggested owner:** Developer B - integration lead, with Developers A and C resolving their owned boundaries

**Blocked by:** 02: Stream Google Meet captions into the live transcript; 03: Create evidence-backed Jira proposals through OpenRouter; 04: Approve and verify Jira transitions securely

**Status:** ready-for-agent

- [ ] The integration branch starts from the frozen baseline and preserves the independent feature histories through explicit merge commits.
- [ ] The Jira, persistence, caption-ingestion, and authorization slice is merged and verified before UI-agent integration.
- [ ] The Streamlit and OpenRouter slice is merged and verified against the real storage and read-only Jira seams.
- [ ] The meeting bridge is merged last and produces the already-qualified caption contract without special integration-only payloads.
- [ ] Any extension conflict is resolved by Developer A, any Streamlit or agent conflict by Developer B, and any persistence, Jira, authentication, or action conflict by Developer C.
- [ ] A shared-contract conflict stops integration until all three developers agree and update their respective tests.
- [ ] A synthetic caption sent through the extension boundary is accepted once, stored once, displayed within two seconds, and linked to at most one proposal.
- [ ] An actionable caption invokes OpenRouter once or activates the visibly labelled deterministic fallback.
- [ ] The proposal contains the original caption evidence and current real Jira evidence.
- [ ] Auth0 login and reviewer authorization gate the approval control.
- [ ] Approval revalidates Jira and executes exactly one currently allowed transition.
- [ ] The Streamlit action result reflects Jira's verified post-transition state.
- [ ] Proposal and result speech exactly match the visible text.
- [ ] Processing is suppressed while StandupPilot speaks so its output cannot create another proposal.
- [ ] Replaying the same caption and approval does not duplicate the caption, proposal, or Jira transition.
- [ ] OpenRouter unavailability does not prevent the fixed demonstration, weaken approval, or bypass Jira validation.
- [ ] Jira state changed after proposal creation produces a stale result without mutation.
- [ ] The complete automated suite passes after all merges.
- [ ] Integration fixes are committed separately and identify the boundary repaired.
- [ ] The final branch contains no application secrets, private meeting data, downloaded transcripts, PostgreSQL dumps, or exported database contents.
