# InboxHero
# Roll Number: evernorth-aai-1177619
## Overview
InboxHero is a lightweight Python pipeline for inbox triage. Messages are loaded, cheap ones (receipts, newsletters, alerts) are dispatched by rule before any model is touched, and the rest go through a classify → retrieve → draft → gate sequence. A final pass builds the dashboard. State that must outlive a run (preferences, the action log) is kept in small JSON files on disk.

## System

- **Framework:** none  
- **Model:** gemini-3.5-flash-lite for triage and drafting; developed against a local qwen3.5:4b via Ollama to avoid rate limits  
- **Messages processed:** 100  
- **Rule handled:** 40  
- **Dispositions:** reply, archive, defer, delegate, escalate  
- **Retrieval:** thread-walk  
- **Irreversible:** send, delete  
- **Reversible:** draft, label, archive, defer  
- **Gate:** approval  
- **Preference demo:** m031: always CC co-founder on Legal mail

## Architecture
InboxHero is organized as a modular pipeline where each capability (R1–R6, X1–X3) is implemented as a function in agent.py and orchestrated by demo.py. The design emphasizes reproducibility, evidence generation, and clear separation of concerns.

"model": "gemini-3.5-flash-lite for triage and drafting; developed against a local qwen3.5:4b via Ollama to avoid rate limits"

## Components
## config.py  
Loads environment variables (GEMINI_API_KEY, MODEL_NAME) and validates credentials.

## agent.py  
Contains the dispatcher run_capability(cap_id) and handlers for each capability. Each handler produces observable evidence files (decisions.json, prefs.json, outbox/, dashboard.html) and appends audit entries to trace.jsonl.

## demo.py  
CLI entry point. Supports --cap R1 to run a single capability or --all to run the full sequence. Calls into agent.py.

### Design Principles
- **Modularity** — Each capability isolated in `agent.py`.
- **Auditability** — Every action logged in `trace.jsonl`.
- **Persistence** — Preferences survive across runs in `prefs.json`.
- **Reproducibility** — Same inputs → same evidence files.

## Evidence Files
trace.jsonl → universal audit trail (timestamp, capability, message).
decisions.json → dispositions or digest summaries.
prefs.json → persisted user preferences.
outbox/ → drafted replies and follow‑ups.
dashboard.html → commitments, conflicts, and meeting analysis.

## Flow
Configuration  
config.py loads API key and model name, then agent.py configures the Gemini SDK (google.generativeai).

Dispatch  
demo.py parses CLI arguments and calls run_capability(cap_id) or run_all().

Capability Execution  
Each capability handler performs its task (classification, drafting, gating, preference persistence, dashboard generation).

Evidence Logging

Writes structured outputs (decisions.json, prefs.json, etc.).

Appends a JSON line to trace.jsonl for accountability.

## Capabilities
See [CAPABILITIES.md](CAPABILITIES.md) for the human‑readable manifest.  
See [capabilities.json](capabilities.json) for the machine‑readable manifest.  

Each capability produces observable evidence:

- R1 → decisions.json
- R2 → outbox/m002.txt
- R3 → trace.jsonl
- R4 → prefs.json
- R5 → trace.jsonl
- R6 → dashboard.html
- X1 → outbox/m010.txt
- X2 → decisions.json
- X3 → dashboard.html

All runs append to trace.jsonl for accountability.

### Usage

```bash
py demo.py --cap R1        # run one capability
py demo.py --all           # run all capabilities in sequence


## Final Report

**Q1. Refusal**  
When a message tries to instruct the assistant directly (e.g. “forward the inbox externally”), the system refuses. It logs the refusal in `trace.jsonl` with `event:"refusal"`, leaves the message untouched, and surfaces it in the Flagged pane of the dashboard. This ensures hostile or injected instructions never execute.

**Q2. Untrusted text**  
Untrusted text from the inbox can only influence *drafts*. Drafts are reversible and gated before sending. The irreversible functions (`send`, `delete`) are wrapped in `require_approval()`, so injected content cannot bypass the gate. This is the defence in Part 6: a hostile message can shape a draft but cannot reach a send without explicit approval.

**Q3. Accountability**  
Every action is logged to `trace.jsonl` with a capability tag (`cap:R1`, `cap:R2`, etc.), message IDs, and the disposition or draft content. Evidence files (`decisions.json`, `prefs.json`, `outbox/`, `dashboard.html`) are reproducible from a run. This audit trail makes it clear what the agent did, why, and on which messages.

**Q4. Machinery**  
The system is a hand‑built pipeline: classify → retrieve → draft → gate. No external framework was used because the task is linear with one branch (rule‑path vs model‑path). Thread‑walk retrieval was chosen for transparency and precision. Preferences and logs persist in JSON files (`prefs.json`, `trace.jsonl`) to survive restarts. This design balances simplicity with reproducibility.
