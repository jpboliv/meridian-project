# Working on Meridian Agents

1. Read `STATUS.md` and the linked issue first.
2. Keep project work in `projects/course-02-agentic-ai/`. Use the supplied simulator and session materials as references.
3. If a behavior is undecided, present a concrete example and record the open question.
4. Use the states Draft, Agreed, and Implemented for specifications. Only mark a draft Agreed after owner review.
5. Link implementation changes to an agreed contract. Include a trace or case that explains the result.
6. Keep evaluator answers out of agent inputs. Keep credentials and private data out of published evidence.
7. Record the reason for each policy change. Update the issue and `STATUS.md` before handing off work.
8. The orchestrator uses the HERDR CLI to run task agents in their own panes. Close the implementer's pane before a fresh, independent Claude Opus 5.5 reviewer at high effort reviews that PR. Fix High and Medium findings, have a fresh reviewer check the changed head, then merge the clean, checked PR.
9. At planning, implementation, and review, ask: “Is this really necessary?”
10. Merging is delegated; specification agreement (rule 4) and live-run settings and spending still need separate owner decisions.
11. Before tuning, verify from inside the isolated development environment that held-out evaluator material is inaccessible. Stop if it is visible.
