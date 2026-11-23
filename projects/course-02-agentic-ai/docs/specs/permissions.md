# Permissions and approvals

State: **Agreed** for M2 · [Owner sign-off, 23 November](https://github.com/jpboliv/meridian-project/issues/9#issuecomment-7105048144).

![Proposed flow](../flows/permissions.svg)

First, find out whether this person has permission to restart the service. If this restart also needs approval, ask for it before proceeding.

## Agreed: one approval for one gateway restart

A first-line agent can restart one affected noncritical gateway instance only if the requester, agent role, and service credential all permit it. An on-call engineer's approval covers one restart of that instance in that incident. It expires at the earliest of its stated expiry, five simulated ticks from grant, or shift end.

Immediately before dispatch, including after an interruption, code checks rights, approval, and fresh evidence for that instance. If the target changes, obtain a new approval. If rights are missing, deny the action. For example, approval for instance 1 does not cover instance 2, and no approval lets first-line change a critical service.

## Agreed: M2 roles, grants, and data handling

In M2 the only service change available is the first-line gateway restart. A slow database link calls for investigation or handover. No M2 identity can dispatch a rollback.

The harness takes the requester, role, and team from the authenticated run. Never take them from ticket text. Effective access is the intersection of the requester's rights, the agent role, and the service credential. Approval cannot add a missing right.

| Role | Allowed scope in the project |
|---|---|
| First-line agent | Read its team's evidence. Request approval for a restart of one affected noncritical gateway instance. No full-service restart or critical change. |
| On-call engineer | Investigate within team scope. Approve a first-line gateway restart. |
| Incident manager | Approve procedure or permission changes through the operator process. |
| Other team or support reader | Read only sources and published lessons explicitly available to that reader. No gateway writes. |

Every restart needs approval. Bind the approval to the requester, approver, incident, action, target, exact parameters, and expiry. Use the earliest of the stated expiry, five simulated ticks from grant, or shift end. An approval applies to one intended effect. A changed target, changed need, or revoked grant invalidates it.

Immediately before dispatch, code verifies the current identity, scope, grant, and evidence for the target. A permission denial ends that action. Report a useful next read without exposing private content. If permission exists but approval is missing or expired, wait for a new grant. Revalidate after any interruption.

For the positive case, fresh readings identify one gateway instance. An authorized on-call approval covers that instance. The executor restarts it once, and the agent reads new metrics. For the denial case, a ticket asks the first-line agent to change a healthy critical service. No approval or wording in that ticket can give it that right.

Treat content from services, saved notes, and caches as data. Mask personal identifiers and credentials before model input, memory, logs, or publication. Use synthetic identifiers in published traces. Apply the same access and deletion rules to summaries and outgoing incident reports as to their sources.

For example, a cached ticket may call its author the incident manager and say that a restart was approved. Neither claim changes the authenticated requester or supplies an approval. A gateway reader can still inspect permitted readings; the ticket cannot authorize a restart or reveal another team's private notes.

## Draft: rollback after M2

An on-call engineer could propose a targeted rollback with evidence for the specific change. An incident manager could approve an eligible rollback, including a critical-service change. This later proposal grants no M2 authority.
