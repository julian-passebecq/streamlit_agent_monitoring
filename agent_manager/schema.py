from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"
ALLOWED_AGENT_STATUSES = {
    "draft",
    "ready",
    "sent",
    "working",
    "returned",
    "reviewed",
    "closed",
    "waiting",
    "blocked",
}

DEFAULT_GIT_STATE: dict[str, Any] = {
    "repository_url": "",
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
    "notes": "",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "project"


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
        errors.append(
            f"project_id must match the selected project ({project_id!r})."
        )
    run = data.get("run")
    if not isinstance(run, dict):
        errors.append("run must be an object.")
    else:
        for key in ("id", "title", "objective"):
            if not run.get(key):
                errors.append(f"run.{key} is required.")
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
                errors.append(
                    f"dispatches.{agent_id}.status {status!r} is not supported."
                )
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
    return errors


def normalized_git_state(value: Any) -> dict[str, Any]:
    state = deepcopy(DEFAULT_GIT_STATE)
    if isinstance(value, dict):
        for key, val in value.items():
            if key == "last_commit" and isinstance(val, dict):
                state["last_commit"].update(val)
            else:
                state[key] = val
    return state


def new_blank_project(project_id: str, name: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
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
        "workflow": {
            "entry_agent": "",
            "coordinator": "",
            "final_recipient": "",
            "description": "",
        },
        "agents": {},
        "git_state": normalized_git_state({}),
        "pro_desk": {
            "liaison_agent_id": "",
            "pro_agent_id": "",
            "director_agent_id": "",
            "default_questions": [],
        },
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }
