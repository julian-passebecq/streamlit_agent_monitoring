# Agent Manager V1

A local-first Streamlit control plane for managing several ChatGPT/Codex conversations as project agents. It **does not execute code and does not call the OpenAI API**. The intelligence stays in your existing ChatGPT/Codex conversations; Agent Manager stores role contracts, model labels, Git metadata, Director dispatches, JSON handoffs, statuses and conversation links.

## Why the Responses API is not in V1

OpenAI API model usage is metered/billed separately from ordinary ChatGPT usage. The project's requirement is no additional API spend, so V1 has no API-key field, no Responses API runner, and no automatic completion polling. Normal `chatgpt.com` Project conversations also do not expose a free supported completion-status API to this app.

The schema is deliberately execution-agnostic so a future paid runner can be added later without replacing project/run/dispatch data.

## Core workflow

1. **ChatGPT Project** holds shared project instructions/files.
2. Each agent has a persistent conversation, custom bootstrap, model label and link.
3. **Director** writes the next multi-agent dispatch in natural language.
4. **Streamlit Companion** converts that Director message to strict `agent_manager_run` JSON.
5. Paste the JSON into **Import / Returns**. The app validates it and creates/updates the run.
6. **Dispatch Board** shows every agent, model, status and prompt. `Copy + Open` copies the packet and opens the saved conversation link; paste/send remains manual.
7. Agents finish with an `agent_return` JSON object. Import those returns to mark work returned and retain evidence.
8. Build a **Director consolidation packet** from the stored returns.

## Pro advisory workflow

The Pro path is deliberately isolated from the main Director conversation:

- **Pro Liaison** gets a deterministic packet containing current project/run/Git state and is asked to produce one standalone advisory prompt.
- Paste that Liaison output into **Pro Desk**, then `Copy + Open Pro` to the stored Pro conversation.
- Paste the Pro answer back into **Pro Desk**. Agent Manager wraps it with metadata and a handling contract for Director.
- Director decides what to accept/reject/verify and converts accepted advice into bounded agent work.

No AI prompt generation happens inside Streamlit; it only assembles deterministic packets from stored data.

## Prompt metadata

Every bootstrap/dispatch starts with metadata such as:

- project + run + dispatch IDs
- agent ID, role, **model label**, surface
- repository URL
- branch
- HEAD SHA
- last commit SHA/message
- last push timestamp
- Git snapshot timestamp

The Git snapshot can be edited manually or supplied by the Streamlit Companion in the imported run JSON.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows you can also run `run_agent_manager.bat` after installing dependencies.

## Main files

- `app.py` — Streamlit UI
- `agent_manager/schema.py` — project/run/return validation
- `agent_manager/packets.py` — deterministic prompt/metadata packet builders
- `agent_manager/storage.py` — local JSON persistence
- `data/projects/datapass-v4.json` — preconfigured Datapass scenario
- `data/runs/datapass-v4/DPV4-001.json` — sample run
- `tests/` — schema and prompt packet tests

## V1 boundaries

- No OpenAI API calls
- No paid Responses API
- No browser automation against chatgpt.com
- No fake automatic agent completion status
- No code execution/judge/runtime
- No GitHub API/authentication; Git state is imported/edited data

These boundaries are intentional. The app is a manager/router for agent discussions, not another Codex implementation environment.
