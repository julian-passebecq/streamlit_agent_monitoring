# Agent Manager V1.2

A local-first **Streamlit control plane for ChatGPT/Codex project agents**. It does not replace ChatGPT, does not execute repository code, and does not require paid OpenAI API usage. It organizes project mapping, selected-app audits, Git/stack metadata, Director organization, feature planning, prompt packaging, conversation links, cycle history and structured returns.

## The key distinction: ChatGPT Project vs managed app

One ChatGPT Project can contain several independent things: a framework, consumer sites, tools, experiments, deployments and stopped work. Agent Manager therefore does **not** assume that one ChatGPT Project equals one application.

The setup wizard first maps the umbrella ChatGPT Project, then you explicitly select the app/subproject you want to manage.

## Five-step onboarding / resume wizard

### 1. Project Map

Create one dedicated **Streamlit Setup / Project Mapper** chat inside the existing ChatGPT Project and save its `chatgpt.com/c/...` URL in Agent Manager.

Prompt 1 asks that chat to inventory the whole ChatGPT Project and return strict `chatgpt_project_map` JSON:

- apps/frameworks/libraries/consumers/tools/experiments;
- lifecycle state: active, paused, stopped or unknown;
- GitHub repositories and roles;
- known branches/latest activity only when evidenced;
- deployments;
- related historical chats/agents;
- relationships between apps;
- current work, evidence and unknowns.

The resulting map is shown as selectable app cards. You can select one app for the current Agent Manager project or create a **separate managed project** from any mapped app.

### 2. App Deep Audit

Prompt 2 goes to the **same Setup Agent chat** after you select an app. It returns `selected_app_audit` JSON with:

- exact app scope and current state;
- languages, frameworks, SDKs, runtimes and tooling;
- detailed repo/Git metadata;
- deployments;
- historical chat/agent inventory;
- completed/in-progress/blocked/standby work;
- decisions, risks, artifacts and open questions;
- Mermaid source for repo topology, work history and agent activity.

This step gathers evidence only. It does not design the future organization.

### 3. Director / Organization

Create or link the Director chat and record the **actual model label** you selected.

Prompt 3 gives Director the selected-app audit and asks for strict `director_organization_plan` JSON:

- smallest useful project-specific agent structure;
- authority boundaries and handoffs;
- recommended model/surface label for each role;
- custom role instructions and reporting contracts;
- shared ChatGPT Project instruction draft;
- optional Pro advisory structure.

Stable agent IDs are preferred so existing conversation links can survive reorganizations.

### 4. Features / Plan

Prompt 4 goes to the same Director chat and returns `director_feature_plan` JSON:

- hierarchical feature / bug / problem / refactor / research / QA / documentation board;
- P0–P4 priority;
- lifecycle status;
- evidence and parent/area relationships;
- milestones where useful;
- concrete next cycle with selected features, active/standby agents, acceptance summary, risks and questions;
- only a lightweight outline of later cycles.

Feature changes are subsequently tracked in an append-only history ledger.

### 5. Agent Setup

Create/link the Prompt Agent first. Agent Manager gives you the Prompt Agent bootstrap from the Director-approved organization.

Prompt 5 asks Prompt Agent to refine the stable instructions into `agent_bootstrap_pack` JSON **without changing Director decisions**. Then Agent Manager shows every agent as its own page in the left sidebar. For each conversation you can store:

- chat URL;
- actual model label;
- role / surface;
- custom instructions;
- reporting contract;
- bootstrap state;
- current cycle prompt.

After that, normal operation is:

```text
Director decision
    ↓
Prompt Agent packaging
    ↓
selected worker chats only
    ↓
QA / Audit
    ↓
Director consolidation
    ↓
next cycle
```

## Sidebar organization

The left sidebar is grouped into:

- **Setup Wizard** — the five onboarding steps;
- **Operate** — Control Room, Organization, Prompt Studio, Features, Cycles, Returns, Pro, Git & Stack and Archive;
- **Agent Chats** — one persistent sidebar page per configured agent;
- **Project** — setup/export and settings.

This avoids the old UX where all agents were hidden behind one selector/tab group.

## Git and technical metadata

Prompt metadata can include:

- project/run/cycle/dispatch IDs;
- agent/model/surface;
- languages/frameworks/SDKs/runtimes;
- primary repository;
- branch/HEAD/latest commit/latest push/deployment;
- packet build timestamp.

Git state is evidence supplied by setup/audit/director chats or edited manually. The Streamlit app does not pretend to query ChatGPT conversations automatically.

## Feature/history model

The durable feature ledger supports hierarchical items and append-only history. Audit-agent returns can include `feature_updates`; each transition records source agent, cycle ID, changed fields and note.

## Archive strategy

Do **not** create a dump repository for every implementation project and do not fill the product repository with raw audits.

V1.2 stores setup artifacts separately under local Agent Manager data and provides an **Archive** page that exports one ZIP containing:

- project config;
- all five setup JSON artifacts;
- feature board/history;
- cycle/run JSON.

ChatGPT Project/chat URLs are redacted from archive exports by default.

If Git history for audits is useful, prefer **one central private archive repository** with a folder per managed project instead of creating a new dump repo per app.

## Privacy of chat links

Live ChatGPT Project and conversation URLs are stored in `data/private/`, which is gitignored. Public/versioned project JSON is written with those links stripped. This reduces the risk of accidentally pushing private conversation links to the public Agent Manager repository.

## Cycles

```text
director_plan
→ optional pro_advisory
→ prompt_packaging
→ dispatch
→ implementation
→ qa
→ audit_update
→ director_consolidation
→ lead_decision
→ closed
```

Active/standby agent selection is part of each cycle.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Windows launchers are included:

- `run_agent_manager.bat`
- `run_agent_manager.ps1`

## Verification

V1.2 currently compiles with Python and the local unit suite reports **16 passed**. A live Streamlit browser smoke still requires an environment where Streamlit is installed.
