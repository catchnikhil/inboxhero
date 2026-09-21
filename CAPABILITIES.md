# CAPABILITIES.md
**Student:** "Nikhil, evernorth-aai-1177619"
**Repository:** https://github.com/nikhil/inboxhero

py demo.py --cap R1        # one capability
py demo.py --all           # all of them, in the order below


---

## The system, in one paragraph

A single Python pipeline, no framework. Messages are loaded, cheap ones (receipts, newsletters, alerts) are dispatched by rule before any model is touched, and the rest go through a classify → retrieve → draft → gate sequence. A final pass builds the dashboard. State that must outlive a run (preferences, the action log) is kept in small JSON files on disk.

---

## Design choices you were asked to state

- **Framework: none.** The work is a linear pipeline with one branch (rule‑path vs model‑path), so a crew or graph would have been overhead. See Final Report Q4.  
- **Retrieval: thread‑walk.** An inbox already carries its own structure in `thread_id`, so walking the thread is both cheaper and more precise than embeddings for this dataset. Keyword search is the fallback for cross‑thread lookups.  
- **Reversible vs irreversible.** `send` and `delete` are irreversible and gated. `draft`, `label`, `archive`, and `defer` are reversible and run without a prompt. Deleting is treated as irreversible because the mock store has no trash.  
- **Where the gate sits.** Only two functions can cause an irreversible effect, and both call `require_approval()` first. Nothing else in the system can reach them, which is also the Part 6 defence: a hostile message can influence a *draft* but cannot reach a send without passing the gate.  
- **Escalation line.** The system asks for approval only on sends to external recipients and on anything touching money or legal. Internal archives and defers are automatic. The trade‑off: a wrongly‑archived internal note is possible, in exchange for the user not being asked to approve forty things.  

---

## Capabilities

| id | name                       | tier | one‑line claim                                      |
|----|----------------------------|------|-----------------------------------------------------|
| R1 | Zero the inbox             | B    | every message gets one disposition + reason, none left |
| R2 | Grounded reply             | B    | drafts cite the earlier message they used           |
| R3 | Gate the irreversible      | C    | no send/delete without approval or --dry‑run        |
| R4 | Persistent preference      | C    | a stated preference survives a restart              |
| R5 | Refuse embedded instructions | C  | detects, refuses, flags, reports injections         |
| R6 | Dashboard                  | C    | three panes, commitments cited, conflicts surfaced  |
| X1 | Follow‑up tracking         | B    | unanswered sent mail, with a drafted chase          |
| X2 | Morning digest             | B    | what needs me / what can wait / what was archived   |
| X3 | Conflict detection         | C    | meeting conflicts detected, alternatives proposed   |

The exact command, observable outcome and evidence for each is in `capabilities.json`. That file is the machine‑readable version and is what a marking script reads; this file is for a human. Keep the two in step.

---

## Final Report

**Q1. Refusal**  
When a message tries to instruct the assistant directly (e.g. “forward the inbox externally”), the system refuses. It logs the refusal in `trace.jsonl` with `event:"refusal"`, leaves the message untouched, and surfaces it in the Flagged pane of the dashboard. This ensures hostile or injected instructions never execute.

**Q2. Untrusted text**  
Untrusted text from the inbox can only influence *drafts*. Drafts are reversible and gated before sending. The irreversible functions (`send`, `delete`) are wrapped in `require_approval()`, so injected content cannot bypass the gate. This is the defence in Part 6: a hostile message can shape a draft but cannot reach a send without explicit approval.

**Q3. Accountability**  
Every action is logged to `trace.jsonl` with a capability tag (`cap:R1`, `cap:R2`, etc.), message IDs, and the disposition or draft content. Evidence files (`decisions.json`, `prefs.json`, `outbox/`, `dashboard.html`) are reproducible from a run. This audit trail makes it clear what the agent did, why, and on which messages.

**Q4. Machinery**  
The system is a hand‑built pipeline: classify → retrieve → draft → gate. No external framework was used because the task is linear with one branch (rule‑path vs model‑path). Thread‑walk retrieval was chosen for transparency and precision. Preferences and logs persist in JSON files (`prefs.json`, `trace.jsonl`) to survive restarts. This design balances simplicity with reproducibility.
