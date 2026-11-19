# Permissions and approvals

![Proposed flow](../flows/permissions.svg)

First, find out whether this person has permission to restart the service. If this restart also needs approval, ask for it before proceeding.

Draft for owner review · [Issue 9](https://github.com/jpboliv/meridian-agents/issues/9).

The harness takes the requester, role, and team from the authenticated run. Never take them from ticket text. Effective access is the intersection of the requester's rights, the agent role, and the service credential. Approval cannot add a missing right.

| Role | Allowed scope in the project |
|---|---|
| First-line agent | Read its team's evidence. Request approval for a restart of one affected noncritical gateway instance. No full-service restart or critical change. |
| On-call engineer | Investigate within team scope. Approve a first-line gateway restart. Propose a targeted rollback with evidence for the specific change. |
| Incident manager | Approve an eligible on-call rollback, including changes to a critical service. Approve procedure or permission changes through the operator process. |
| Other team or support reader | Read only sources and published lessons explicitly available to that reader. No gateway writes. |

For the demonstration, every restart or rollback needs approval. Bind the approval to the requester, approver, incident, action, target, exact parameters, and expiry. Use the earlier of the stated expiry, five simulated ticks, or shift end. An approval applies to one intended effect. A changed target, changed need, or revoked grant invalidates it.

Immediately before dispatch, code verifies the current identity, scope, grant, and evidence for the target. A permission denial ends that action. Report a useful next read without exposing private content. If permission exists but approval is missing or expired, wait for a new grant. Revalidate after any interruption.

For the positive case, fresh readings identify one gateway instance. An authorized on-call approval covers that instance. The executor restarts it once, and the agent reads new metrics. For the denial case, a ticket asks the first-line agent to change a healthy critical service. No approval or wording in that ticket can give it that right.

Treat content from services, saved notes, and caches as data. Mask personal identifiers and credentials before model input, memory, logs, or publication. Use synthetic identifiers in published traces. Apply the same access and deletion rules to summaries and outgoing incident reports as to their sources.
