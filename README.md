# Agent Manager V1.1

A local-first **Streamlit control plane for ChatGPT/Codex project agents**. Agent Manager does not replace ChatGPT, does not execute repository code, and does not require paid OpenAI API usage. It organizes projects, role contracts, conversation links, Git/stack metadata, Director cycles, Prompt Agent packaging, feature/history tracking, Pro advisory handoffs and structured returns.

## Core operating model

```text
Start / Resume Auditor
        ↓
Technical Lead
        ↓
Director ───── optional ───→ Pro Liaison → Pro Advisor → Director
        ↓
Prompt Agent
        ↓
selected worker conversations only
(Code A / Code B / QA / Audit / project-specific roles)
        ↓
Director consolidation
        ↓
Technical Lead / next cycle
```

The roles are deliberately separated:

- **Startup / Resume Auditor** reconstructs the real project state and proposes the control plane. It audits project history, Git/repositories, technical stack, backlog and agent organization; it does not stay as routine coordinator.
- **Director** owns objective, priority, active/standby selection, assignments, dependencies and acceptance/QA/Audit policy.
- **Prompt Agent** owns prompt quality, not technical decisions. It converts the Director brief into precise model/role-specific worker prompts.
- **Workers** execute bounded tasks.
- **QA** independently verifies acceptance criteria.
- **Audit / Backlog** owns the durable feature/problem/bug ledger and history.
- **Pro Liaison / Pro Advisor** are optional advisory side channels. Pro advice must return through Director before it can influence implementation.

## Start / Resume workflow

The first page gives you a reusable prompt to paste into an existing knowledgeable chat inside the ChatGPT Project. That chat is asked to perform a full project-control audit and return strict `project_bootstrap_audit` JSON containing:

- project purpose, decisions, constraints and current state;
- optimized project-specific agent organization;
- full custom instructions/reporting contract for every proposed agent;
- programming languages, frameworks, SDKs/libraries, runtimes, package/build/test tooling and deployment targets;
- repository inventory and verified Git snapshot (branches, HEAD, latest commit/push, deployment where visible);
- hierarchical feature/bug/problem/refactor/QA ledger;
- next cycle objective, phase, active/standby agents, risks and questions.

Agent Manager validates the JSON and shows a summary before applying it. Existing conversation URLs/bootstrap state are preserved for stable agent IDs, so reorganizing the project does not destroy useful chats.

## Cycles

A cycle is the durable work unit, with explicit phases:

```text
resume_audit
→ director_plan
→ pro_advisory (optional)
→ prompt_packaging
→ dispatch
→ implementation
→ qa
→ audit_update
→ director_consolidation
→ lead_decision
→ closed
```

Phase transitions and agent-selection changes are stored as cycle history. Each cycle/run also contains active and standby agent IDs.

## Organization page

The organization page shows the control chain and worker pool. For the current cycle you can toggle agents **active/standby**. Prompt Agent is only allowed to create dispatches for the selected agents. Each worker card can expose its current packaged prompt.

## Prompt Studio

1. Director writes the cycle orchestration brief in its own ChatGPT conversation.
2. Paste that brief into Prompt Studio.
3. Agent Manager builds a deterministic packet for the dedicated Prompt Agent, including selected agents, their role contracts/model labels, current Git state and technical stack.
4. Prompt Agent returns strict `agent_manager_run` JSON with bounded prompts.
5. Paste/apply that JSON in Prompt Studio.
6. Control Room exposes `Copy prompt` / `Copy + Open` for each selected ChatGPT/Codex conversation.

Prompt Agent guidance follows current OpenAI prompting principles (clear/specific instructions, instructions before context, explicit output formats when needed, bounded requests and iterative refinement) plus project-control rules: evidence requirements, role authority, model labels, missing-evidence behavior and no invented context.

## Feature / Pilot board

The feature ledger supports hierarchical items with stable IDs and fields such as:

- parent / area;
- kind: feature, bug, problem, refactor, research, QA, documentation;
- priority P0–P4;
- status: idea, planned, ready, in progress, standby, blocked, done, deprecated;
- owner agent;
- problem/goal and evidence;
- cycle last changed.

Every update is appended to a history ledger with cycle ID, source agent, changed fields and note. Audit-agent `agent_return` JSON can include `feature_updates`, which Agent Manager applies automatically while preserving history.

## Git & technical-stack module

Prompt metadata can include:

- project / run / cycle / dispatch IDs;
- agent ID, role, model label and surface;
- languages, frameworks, SDKs and runtimes;
- primary repository, branch, HEAD, last commit, last push and deployment;
- packet build timestamp.

The app itself does not pretend to query GitHub automatically. Startup/Audit/Director can supply verified metadata in JSON, or you can edit it manually.

## Pro advisory workflow

```text
Director/current cycle
        ↓
Pro Liaison standalone brief
        ↓
Pro Advisor
        ↓
Pro answer
        ↓
Director review wrapper
        ↓
accept / reject / verify
        ↓
Prompt Agent / normal worker cycle
```

## Why the OpenAI Responses API is not in scope

API model usage is metered/billed separately from ordinary ChatGPT usage. This project currently requires **no additional API spend**, so V1.1 has no API key, no Responses runner and no fake automatic completion detection for ordinary `chatgpt.com` conversations.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Windows launchers are included:

- `run_agent_manager.bat`
- `run_agent_manager.ps1`

## Main files

- `app.py` — Streamlit control-plane UI
- `agent_manager/schema.py` — project/run/startup-audit validation, cycle/feature constants
- `agent_manager/packets.py` — deterministic bootstrap/startup/Prompt Agent/dispatch/Pro packets
- `agent_manager/storage.py` — local JSON persistence, cycle/feature updates, startup-audit application
- `agent_manager/ui_helpers.py` — light-theme UI helpers
- `data/projects/datapass-v4.json` — current Datapass V4 scenario and precise role contracts
- `data/features/datapass-v4.json` — durable feature/history ledger
- `data/runs/datapass-v4/` — cycle/run history
- `tests/` — schema, packet, feature-history and startup-preservation tests

## Verification

The V1.1 code compiles with Python and the local unit suite currently reports **14 passed**. A live Streamlit browser smoke still requires a local environment with Streamlit installed.
