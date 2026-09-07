from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"
APP_VERSION = "1.2"

ALLOWED_AGENT_STATUSES = {
    "draft",
    "ready",
    "sent",
    "working",
    "returned",
    "reviewed",
    "closed",
    "waiting",
    "standby",
    "blocked",
}

CYCLE_PHASES = [
    "resume_audit",
    "director_plan",
    "pro_advisory",
    "prompt_packaging",
    "dispatch",
    "implementation",
    "qa",
    "audit_update",
    "director_consolidation",
    "lead_decision",
    "closed",
]

FEATURE_PRIORITIES = ["P0", "P1", "P2", "P3", "P4"]
FEATURE_STATUSES = [
    "idea",
    "planned",
    "ready",
    "in_progress",
    "standby",
    "blocked",
    "done",
    "deprecated",
]
FEATURE_KINDS = ["feature", "bug", "problem", "refactor", "research", "qa", "documentation"]

SETUP_STAGES = [
    "project_map",
    "selected_app_audit",
    "director_organization",
    "director_feature_plan",
    "agent_bootstrap",
    "ready",
]

APP_LIFECYCLE_STATUSES = ["active", "paused", "stopped", "unknown"]
APP_KINDS = ["application", "framework", "library", "consumer", "tool", "website", "service", "experiment", "other"]


DEFAULT_TECHNICAL_STACK: dict[str, Any] = {
    "languages": [],
    "frameworks": [],
    "sdks": [],
    "runtimes": [],
    "package_managers": [],
    "build_tools": [],
    "test_tools": [],
    "datastores": [],
    "cloud_platforms": [],
    "deployment_targets": [],
    "developer_tools": [],
    "notes": "",
}

DEFAULT_GIT_STATE: dict[str, Any] = {
    "repository_url": "",
    "repository_name": "",
    "default_branch": "main",
    "active_branch": "main",
    "head_sha": "",
    "last_commit": {
        "sha": "",
        "message": "",
        "author": "",
        "committed_at": "",
    },
    "last_push_at": "",
    "deployment_url": "",
    "snapshot_source": "manual",
    "snapshot_at": "",
    "recent_commits": [],
    "working_state": "unknown",
    "notes": "",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "project"


def normalized_technical_stack(value: Any) -> dict[str, Any]:
    stack = deepcopy(DEFAULT_TECHNICAL_STACK)
    if isinstance(value, dict):
        for key, val in value.items():
            stack[key] = val
    for key, default in DEFAULT_TECHNICAL_STACK.items():
        if isinstance(default, list) and not isinstance(stack.get(key), list):
            stack[key] = []
    return stack


def normalized_git_state(value: Any) -> dict[str, Any]:
    state = deepcopy(DEFAULT_GIT_STATE)
    if isinstance(value, dict):
        for key, val in value.items():
            if key == "last_commit" and isinstance(val, dict):
                state["last_commit"].update(val)
            else:
                state[key] = val
    if not isinstance(state.get("recent_commits"), list):
        state["recent_commits"] = []
    return state


def normalized_cycle(run: dict[str, Any] | None = None) -> dict[str, Any]:
    cycle = deepcopy((run or {}).get("cycle") or {})
    cycle.setdefault("number", 1)
    cycle.setdefault("phase", "director_plan")
    cycle.setdefault("status", "active")
    cycle.setdefault("active_agents", [])
    cycle.setdefault("standby_agents", [])
    cycle.setdefault("started_at", "")
    cycle.setdefault("completed_at", "")
    cycle.setdefault("notes", "")
    return cycle


def empty_feature_board(project_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "feature_board",
        "project_id": project_id,
        "features": [],
        "history": [],
        "updated_at": utc_now_iso(),
    }


def validate_project_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Project configuration must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    project = data.get("project")
    if not isinstance(project, dict):
        errors.append("project must be an object.")
    else:
        for key in ("id", "name"):
            if not project.get(key):
                errors.append(f"project.{key} is required.")
    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        errors.append("agents must be a non-empty object keyed by agent id.")
    else:
        for agent_id, agent in agents.items():
            if not isinstance(agent, dict):
                errors.append(f"agents.{agent_id} must be an object.")
                continue
            if agent.get("id") and agent.get("id") != agent_id:
                errors.append(f"agents.{agent_id}.id must match its object key.")
            for key in ("name", "role", "model_label"):
                if not agent.get(key):
                    errors.append(f"agents.{agent_id}.{key} is required.")
    return errors


def validate_run_payload(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Run payload must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "agent_manager_run":
        errors.append("type must be 'agent_manager_run'.")
    project_id = project.get("project", {}).get("id")
    if data.get("project_id") != project_id:
        errors.append(f"project_id must match the selected project ({project_id!r}).")
    run = data.get("run")
    if not isinstance(run, dict):
        errors.append("run must be an object.")
    else:
        for key in ("id", "title", "objective"):
            if not run.get(key):
                errors.append(f"run.{key} is required.")
    cycle = data.get("cycle")
    if cycle is not None:
        if not isinstance(cycle, dict):
            errors.append("cycle must be an object when provided.")
        elif cycle.get("phase") and cycle.get("phase") not in CYCLE_PHASES:
            errors.append(f"cycle.phase {cycle.get('phase')!r} is not supported.")
    dispatches = data.get("dispatches")
    if not isinstance(dispatches, dict):
        errors.append("dispatches must be an object.")
    else:
        known_agents = set(project.get("agents", {}))
        for agent_id, dispatch in dispatches.items():
            if agent_id not in known_agents:
                errors.append(f"Unknown dispatch agent id: {agent_id!r}.")
            if not isinstance(dispatch, dict):
                errors.append(f"dispatches.{agent_id} must be an object.")
                continue
            if not dispatch.get("prompt"):
                errors.append(f"dispatches.{agent_id}.prompt is required.")
            status = dispatch.get("status", "ready")
            if status not in ALLOWED_AGENT_STATUSES:
                errors.append(f"dispatches.{agent_id}.status {status!r} is not supported.")
    return errors


def validate_agent_return(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Agent return must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "agent_return":
        errors.append("type must be 'agent_return'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected project.")
    agent_id = data.get("agent_id")
    if agent_id not in project.get("agents", {}):
        errors.append(f"Unknown agent_id: {agent_id!r}.")
    if not data.get("run_id"):
        errors.append("run_id is required.")
    if not data.get("status"):
        errors.append("status is required.")
    updates = data.get("feature_updates", [])
    if updates is not None and not isinstance(updates, list):
        errors.append("feature_updates must be a list when provided.")
    return errors


def validate_bootstrap_audit(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Bootstrap audit must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "project_bootstrap_audit":
        errors.append("type must be 'project_bootstrap_audit'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected project.")
    org = data.get("agent_organization")
    if not isinstance(org, dict):
        errors.append("agent_organization must be an object.")
    elif not isinstance(org.get("agents"), dict) or not org.get("agents"):
        errors.append("agent_organization.agents must be a non-empty object.")
    else:
        for agent_id, agent in org["agents"].items():
            if not isinstance(agent, dict):
                errors.append(f"agent_organization.agents.{agent_id} must be an object.")
                continue
            for field in ("name", "role", "model_label", "custom_instructions", "reporting_contract"):
                if not agent.get(field):
                    errors.append(f"agent_organization.agents.{agent_id}.{field} is required.")
    if not isinstance(data.get("technical_stack"), dict):
        errors.append("technical_stack must be an object.")
    if not isinstance(data.get("git_state"), dict):
        errors.append("git_state must be an object.")
    board = data.get("feature_board")
    if board is not None and not isinstance(board, dict):
        errors.append("feature_board must be an object when provided.")
    next_cycle = data.get("next_cycle")
    if not isinstance(next_cycle, dict):
        errors.append("next_cycle must be an object.")
    else:
        for field in ("id", "number", "title", "objective"):
            if next_cycle.get(field) in (None, ""):
                errors.append(f"next_cycle.{field} is required.")
        phase = next_cycle.get("phase", "director_plan")
        if phase not in CYCLE_PHASES:
            errors.append(f"next_cycle.phase {phase!r} is not supported.")
    return errors

def validate_project_map(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Project map must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "chatgpt_project_map":
        errors.append("type must be 'chatgpt_project_map'.")
    if data.get("manager_project_id") != project.get("project", {}).get("id"):
        errors.append("manager_project_id does not match the selected Agent Manager project.")
    chatgpt_project = data.get("chatgpt_project")
    if not isinstance(chatgpt_project, dict) or not chatgpt_project.get("name"):
        errors.append("chatgpt_project.name is required.")
    apps = data.get("apps")
    if not isinstance(apps, list) or not apps:
        errors.append("apps must be a non-empty list.")
    else:
        seen: set[str] = set()
        for idx, app in enumerate(apps):
            if not isinstance(app, dict):
                errors.append(f"apps[{idx}] must be an object.")
                continue
            app_id = app.get("id")
            if not app_id:
                errors.append(f"apps[{idx}].id is required.")
            elif app_id in seen:
                errors.append(f"Duplicate app id: {app_id!r}.")
            else:
                seen.add(app_id)
            if not app.get("name"):
                errors.append(f"apps[{idx}].name is required.")
            status = app.get("status", "unknown")
            if status not in APP_LIFECYCLE_STATUSES:
                errors.append(f"apps[{idx}].status {status!r} is not supported.")
    return errors


def validate_selected_app_audit(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Selected-app audit must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "selected_app_audit":
        errors.append("type must be 'selected_app_audit'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected Agent Manager project.")
    selected = project.get("onboarding", {}).get("selected_app_id", "")
    if selected and data.get("selected_app_id") != selected:
        errors.append(f"selected_app_id must match the selected app ({selected!r}).")
    if not isinstance(data.get("technical_stack"), dict):
        errors.append("technical_stack must be an object.")
    if not isinstance(data.get("git_state"), dict):
        errors.append("git_state must be an object.")
    repos = data.get("repositories")
    if repos is not None and not isinstance(repos, list):
        errors.append("repositories must be a list when provided.")
    chats = data.get("chat_inventory")
    if chats is not None and not isinstance(chats, list):
        errors.append("chat_inventory must be a list when provided.")
    return errors


def validate_director_organization_plan(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Director organization plan must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "director_organization_plan":
        errors.append("type must be 'director_organization_plan'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected Agent Manager project.")
    org = data.get("organization")
    if not isinstance(org, dict):
        errors.append("organization must be an object.")
    else:
        agents = org.get("agents")
        if not isinstance(agents, dict) or not agents:
            errors.append("organization.agents must be a non-empty object.")
        else:
            for aid, agent in agents.items():
                if not isinstance(agent, dict):
                    errors.append(f"organization.agents.{aid} must be an object.")
                    continue
                for field in ("name", "role", "model_label", "custom_instructions", "reporting_contract"):
                    if not agent.get(field):
                        errors.append(f"organization.agents.{aid}.{field} is required.")
    return errors


def validate_director_feature_plan(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Director feature plan must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "director_feature_plan":
        errors.append("type must be 'director_feature_plan'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected Agent Manager project.")
    board = data.get("feature_board")
    if not isinstance(board, dict) or not isinstance(board.get("features"), list):
        errors.append("feature_board.features must be a list.")
    cycle = data.get("next_cycle")
    if not isinstance(cycle, dict):
        errors.append("next_cycle must be an object.")
    else:
        for field in ("id", "number", "title", "objective"):
            if cycle.get(field) in (None, ""):
                errors.append(f"next_cycle.{field} is required.")
        phase = cycle.get("phase", "director_plan")
        if phase not in CYCLE_PHASES:
            errors.append(f"next_cycle.phase {phase!r} is not supported.")
    return errors


def validate_agent_bootstrap_pack(data: dict[str, Any], project: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Agent bootstrap pack must be a JSON object."]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}.")
    if data.get("type") != "agent_bootstrap_pack":
        errors.append("type must be 'agent_bootstrap_pack'.")
    if data.get("project_id") != project.get("project", {}).get("id"):
        errors.append("project_id does not match the selected Agent Manager project.")
    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        errors.append("agents must be a non-empty object.")
    else:
        known = set(project.get("agents", {}))
        for aid, agent in agents.items():
            if aid not in known:
                errors.append(f"Unknown bootstrap agent id: {aid!r}.")
            if not isinstance(agent, dict):
                errors.append(f"agents.{aid} must be an object.")
                continue
            for field in ("custom_instructions", "reporting_contract"):
                if not agent.get(field):
                    errors.append(f"agents.{aid}.{field} is required.")
    return errors


def new_blank_project(project_id: str, name: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "type": "agent_manager_project",
        "project": {
            "id": project_id,
            "name": name,
            "description": "",
            "status": "active",
            "chatgpt_project_url": "",
            "repository_url": "",
        },
        "shared_project_instructions": "",
        "technical_stack": normalized_technical_stack({}),
        "workflow": {
            "entry_agent": "startup_agent",
            "coordinator": "director",
            "prompt_agent": "prompt_agent",
            "final_recipient": "technical_lead",
            "description": "Startup audit -> Director -> Prompt Agent -> selected workers -> QA/Audit -> Director consolidation.",
            "relationships": [],
        },
        "agents": {},
        "git_state": normalized_git_state({}),
        "cycle_plan": {},
        "pro_desk": {
            "liaison_agent_id": "",
            "pro_agent_id": "",
            "director_agent_id": "",
            "default_questions": [],
        },
        "onboarding": {
            "stage": "project_map",
            "chatgpt_project_name": "",
            "chatgpt_project_url": "",
            "setup_chat_url": "",
            "setup_model_label": "GPT-5.6 Sol / High",
            "project_map": {},
            "selected_app_id": "",
            "selected_app_audit": {},
            "director_organization_plan": {},
            "director_feature_plan": {},
            "agent_bootstrap_pack": {},
        },
        "archive": {
            "repository_url": "",
            "notes": "",
        },
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
