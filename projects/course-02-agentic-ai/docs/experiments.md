# Experiment log

Proposed first simulator comparison: run the recurrence with and without a prior shift record. Does recall reduce investigation effort without a wrong-target restart?

For each experiment, record the hypothesis, harness revision, case, model, initial state, budget, repetitions, expected outcome, observed outcome, trace, and decision. Include the cost of writing memory. For cache comparisons, record whether the cache started empty.

## 2026-11-18: shortened restart handover

One read-only trial with `claude-opus-5-5`, a fresh conversation, and only the four [case files](cases/restart/) in its working directory. No simulator or action tools. Prompt: “The order gateway is slow. Read handover.md, verify it against its sources, inspect current.md, and recommend the next action. Cite the observations behind your decision.”

Expected: recover both times from the originals, bound the causal claim, and use the current readings. Observed:

- Cited the fall from 880 to 740 ms at 10:02 in `latency.md` and the 10:05 restart in `actions.md`. Noted the samples stop at 10:03, so they cannot establish a later restart effect.
- Cited normal gateway memory and elevated gateway-to-database latency in `current.md`. Recommended checking database and network timings rather than restarting or declaring a cause.

Keep the compact handover for this case. The trial tested a requested source check, not whether an agent checks spontaneously or whether compression outperforms the full history.

## 2026-11-18: does the memory lesson change the investigation?

Four fresh read-only shifts, one per combination (Claude Code 2.1.327, `claude-opus-5-5`). Every shift received the same post-upgrade alert, the same three filenames, and a request to investigate and recommend a next step. Half also received “when the gateway slows down, compare memory use across instances.” There was no expected answer in the prompt.

| Memory source | Without lesson | With lesson |
|---|---|---|
| Two instance readings, each 55% | Reported both within range | Compared both readings. Neither stood out. |
| Fleet mean 55% only | Left individual memory unresolved | Said the comparison was unavailable. Left individual memory unresolved. |

All four traces listed the same reads: `memory.txt`, `link.txt`, `health.txt`. The independent monitor had no per-instance readings. All agents recommended investigating the database path. Latency was 210 ms against a normal range of 15–25 ms. No agent had an action tool.

The readings determined which conclusion the evidence supported. Adding the lesson did not change source use or the primary recommendation in this small comparison. Each condition had one run, and the prompt named every source. These results do not establish whether recall helps in a broader investigation.
