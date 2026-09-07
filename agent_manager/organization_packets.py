from __future__ import annotations

import json
from typing import Any

from .schema import empty_feature_board
def director_organization_schema_example(project: dict[str, Any]) -> dict[str, Any]:
    existing = project.get("agents", {})
    agent_examples: dict[str, Any] = {}
    for aid, agent in list(existing.items())[:3]:
        agent_examples[aid] = {
            "id": aid,
            "name": agent.get("name", aid),
            "role": agent.get("role", ""),
            "surface": agent.get("surface", "ChatGPT"),
            "model_label": agent.get("model_label", ""),
            "receives_dispatch": bool(agent.get("receives_dispatch", True)),
            "active_default": bool(agent.get("active_default", agent.get("receives_dispatch", True))),
            "custom_instructions": "Precise authority/scope contract.",
            "reporting_contract": "Precise evidence/output contract.",
        }
    if not agent_examples:
        agent_examples = {
            "director": {
                "id": "director",
                "name": "Director",
                "role": "coordinator",
                "surface": "ChatGPT",
                "model_label": "",
                "receives_dispatch": False,
                "active_default": True,
                "custom_instructions": "",
                "reporting_contract": "",
            },
            "prompt_agent": {
                "id": "prompt_agent",
                "name": "Prompt Agent",
                "role": "prompt packaging",
                "surface": "ChatGPT",
                "model_label": "",
                "receives_dispatch": False,
                "active_default": True,
                "custom_instructions": "",
                "reporting_contract": "",
            },
        }
    return {
        "schema_version": "1.0",
        "type": "director_organization_plan",
        "project_id": project.get("project", {}).get("id", ""),
        "selected_app_id": project.get("onboarding", {}).get("selected_app_id", ""),
        "director_summary": "",
        "shared_project_instructions_draft": "",
        "organization": {
            "rationale": "",
            "replace_agents": False,
            "agents": agent_examples,
            "relationships": [{"from": "director", "to": "prompt_agent", "kind": "directs"}],
            "governance": {
                "decision_authority": "",
                "implementation_authority": "",
                "qa_authority": "",
                "audit_authority": "",
                "prompt_agent_boundary": "",
                "pro_advisory_boundary": "",
            },
        },
        "pro_desk": {
            "enabled": False,
            "liaison_agent_id": "pro_liaison",
            "pro_agent_id": "pro_advisor",
            "director_agent_id": "director",
            "default_questions": [],
        },
        "questions": [],
    }


def build_director_organization_prompt(project: dict[str, Any]) -> str:
    onboarding = project.get("onboarding", {})
    audit = onboarding.get("selected_app_audit", {})
    schema = director_organization_schema_example(project)
    return f"""# Director setup request — design the operating organization

You are the Director for **{audit.get('identity', {}).get('name') or project.get('project', {}).get('name', '')}**. We have finished the project-map and deep selected-app audit. Now design the smallest effective agent organization for this app.

Do not implement code in this answer. Do not create the feature roadmap yet. This step is only organization, authority, model/surface labels, shared project instructions and precise role contracts.

## What you must decide

- Which agent roles are actually needed now and which should be standby/omitted.
- Clear authority boundaries and handoffs.
- Whether a Technical Lead is necessary or whether Director can own the current technical coordination.
- A dedicated Prompt Agent below Director. Prompt Agent may improve prompt precision but must not reinterpret or expand Director decisions.
- Implementation agents only where parallelism is useful.
- Independent QA and Audit/Backlog roles where the project warrants them.
- Optional Pro Liaison/Pro Advisor only if it adds value; Pro is advisory and cannot directly command workers.
- Recommended model label and ChatGPT/Codex surface for every role. If model choice is uncertain, state a neutral label rather than inventing entitlement/capability.
- Precise custom instructions and reporting contracts for every role.
- A concise shared ChatGPT Project instruction draft that captures stable project constraints without duplicating every agent's private role contract.

Preserve stable agent IDs from prior work when useful so existing conversation links can survive. Prefer standby over deleting a useful historical role.

## Deep selected-app audit

{json.dumps(audit, indent=2, ensure_ascii=False)}

## Required output

Return valid JSON only, no markdown fence and no commentary, matching this shape:

{json.dumps(schema, indent=2, ensure_ascii=False)}
""".strip()


def director_feature_plan_schema_example(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "type": "director_feature_plan",
        "project_id": project.get("project", {}).get("id", ""),
        "selected_app_id": project.get("onboarding", {}).get("selected_app_id", ""),
        "planning_summary": "",
        "feature_board": empty_feature_board(project.get("project", {}).get("id", "")),
        "milestones": [
            {"id": "M1", "title": "", "objective": "", "status": "planned", "feature_ids": [], "evidence_required": []}
        ],
        "next_cycle": {
            "id": "CYCLE-001",
            "number": 1,
            "title": "First operating cycle",
            "objective": "Resume the selected app safely.",
            "phase": "director_plan",
            "active_agents": [],
            "standby_agents": [],
            "selected_feature_ids": [],
            "acceptance_summary": [],
            "risks": [],
            "questions": [],
        },
        "future_cycles": [
            {"number": 2, "title": "", "objective": "", "candidate_feature_ids": [], "notes": ""}
        ],
        "planning_rules": [],
    }


def build_director_feature_plan_prompt(project: dict[str, Any]) -> str:
    onboarding = project.get("onboarding", {})
    audit = onboarding.get("selected_app_audit", {})
    org = onboarding.get("director_organization_plan", {})
    schema = director_feature_plan_schema_example(project)
    return f"""# Director setup request — feature board and first operating plan

The agent organization is now defined. Build the durable product/work ledger and the first operating cycle for **{audit.get('identity', {}).get('name') or project.get('project', {}).get('name', '')}**.

## Planning rules

- Create a hierarchical feature/problem/bug/refactor/research/QA/documentation board with stable IDs.
- Use priorities P0–P4 and statuses idea/planned/ready/in_progress/standby/blocked/done/deprecated.
- Preserve completed historical work when it matters to project understanding; do not turn every old detail into an active feature.
- Separate product capability, defects, technical debt, research and QA work.
- Include evidence and parent/area relationships where known.
- Define milestones only when they improve clarity.
- Plan the **next cycle concretely**: selected feature IDs, objective, active agents, standby agents, acceptance summary, risks and questions.
- Future cycles should stay high-level; do not over-plan uncertain work.
- The Director may later reprioritize the board. Audit Agent will record every state transition in append-only history.

## Deep audit

{json.dumps(audit, indent=2, ensure_ascii=False)}

## Approved organization

{json.dumps(org, indent=2, ensure_ascii=False)}

## Required output

Return valid JSON only, no markdown fence and no commentary, matching this shape:

{json.dumps(schema, indent=2, ensure_ascii=False)}
""".strip()


def agent_bootstrap_pack_schema_example(project: dict[str, Any]) -> dict[str, Any]:
    agents = {}
    for aid, agent in project.get("agents", {}).items():
        agents[aid] = {
            "conversation_name": agent.get("name", aid),
            "surface": agent.get("surface", "ChatGPT"),
            "model_label": agent.get("model_label", ""),
            "custom_instructions": agent.get("custom_instructions", ""),
            "reporting_contract": agent.get("reporting_contract", ""),
            "startup_behavior": "Acknowledge role briefly and wait for bounded work unless setup work is explicitly assigned.",
        }
    return {
        "schema_version": "1.0",
        "type": "agent_bootstrap_pack",
        "project_id": project.get("project", {}).get("id", ""),
        "selected_app_id": project.get("onboarding", {}).get("selected_app_id", ""),
        "shared_project_instructions": project.get("shared_project_instructions", ""),
        "agents": agents,
    }


def build_agent_bootstrap_pack_prompt(project: dict[str, Any]) -> str:
    onboarding = project.get("onboarding", {})
    org = onboarding.get("director_organization_plan", {})
    feature_plan = onboarding.get("director_feature_plan", {})
    schema = agent_bootstrap_pack_schema_example(project)
    return f"""# Prompt Agent setup task — finalize role instructions for conversation creation

The Director has already decided the organization and planning policy. Your job is to turn those approved role definitions into clean, durable ChatGPT/Codex conversation bootstraps **without changing Director decisions, authority, scope or agent assignments**.

## Prompt-writing method

For each agent:
- state role, authority, scope and explicit non-goals first;
- separate stable role instructions from dynamic cycle context;
- define evidence requirements and missing-evidence behavior;
- define tool/repository boundaries and what must never be invented;
- make success/return criteria explicit;
- use model/surface labels as metadata only; do not claim undocumented capabilities;
- keep instructions concise enough to remain useful across many cycles;
- do not request private chain-of-thought; request concise rationale, decisions and evidence;
- preserve exact stable agent IDs.

Also refine the shared ChatGPT Project instructions so they contain only stable project-wide constraints, not private role instructions or transient cycle tasks.

## Director-approved organization

{json.dumps(org, indent=2, ensure_ascii=False)}

## Director-approved feature / planning context

{json.dumps(feature_plan, indent=2, ensure_ascii=False)}

## Required output

Return valid JSON only, no markdown fence and no commentary, matching this shape. Do not include or invent conversation URLs; the human will create/link those manually in Streamlit.

{json.dumps(schema, indent=2, ensure_ascii=False)}
""".strip()
