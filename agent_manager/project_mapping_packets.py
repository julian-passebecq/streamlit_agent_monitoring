from __future__ import annotations

import json
from typing import Any

from .schema import APP_KINDS, APP_LIFECYCLE_STATUSES, empty_feature_board, normalized_git_state, normalized_technical_stack
def project_map_schema_example(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = project.get("onboarding", {})
    return {
        "schema_version": "1.0",
        "type": "chatgpt_project_map",
        "manager_project_id": project.get("project", {}).get("id", ""),
        "chatgpt_project": {
            "name": onboarding.get("chatgpt_project_name") or project.get("project", {}).get("name", ""),
            "url": onboarding.get("chatgpt_project_url") or project.get("project", {}).get("chatgpt_project_url", ""),
            "audited_at": "",
            "summary": "",
        },
        "apps": [
            {
                "id": "app-stable-id",
                "name": "Application / framework / consumer name",
                "kind": "application",
                "status": "unknown",
                "purpose": "",
                "current_work": {
                    "summary": "",
                    "status": "",
                    "next_action": "",
                },
                "repositories": [
                    {
                        "name": "",
                        "url": "",
                        "role": "primary|library|consumer|infra|docs|other",
                        "default_branch": "",
                        "active_branch": "",
                        "last_known_commit": "",
                        "last_known_push": "",
                    }
                ],
                "deployments": [{"name": "", "url": "", "status": ""}],
                "conversations": [
                    {
                        "title": "",
                        "url": "",
                        "role_or_agent": "",
                        "model_label": "",
                        "status": "active|standby|historical|unknown",
                        "last_known_work": "",
                    }
                ],
                "related_app_ids": [],
                "evidence": [],
                "confidence": "high|medium|low",
            }
        ],
        "relationships": [
            {"from_app_id": "", "to_app_id": "", "kind": "depends_on|consumes|tests|deploys|forks|other", "notes": ""}
        ],
        "recommended_focus": [],
        "unknowns": [],
    }


def build_project_map_prompt(project: dict[str, Any]) -> str:
    onboarding = project.get("onboarding", {})
    project_name = onboarding.get("chatgpt_project_name") or project.get("project", {}).get("name", "this ChatGPT Project")
    schema = project_map_schema_example(project)
    return f"""# Project map request for Agent Manager

I am back in the ChatGPT Project **{project_name}**. Before we resume any one app, I need you to map the whole project so I can see clearly what is active, paused, stopped, shared, or only historical.

Act as the **Streamlit Setup / Project Mapper** for this first answer. Use only information you can actually recover from this ChatGPT Project, its files, prior project context, and any connected repository tools you truly have. Do not guess URLs, commits, branches, models, deployments, or conversation links that you cannot verify.

## Goal

Identify every distinct application, framework, library, consumer site, tool, experiment, or service that belongs to this ChatGPT Project. The point is to separate them before we choose which one to manage.

For each app/subproject, recover where possible:
- stable short ID and clear name;
- kind and lifecycle status: active, paused, stopped, or unknown;
- purpose and current work;
- GitHub repositories and their roles;
- known active/default branches and latest known commit/push only when evidenced;
- deployments/sites;
- related ChatGPT conversations or agent roles, with URLs/model labels only if actually observable;
- relationships to other apps in the project;
- evidence/confidence and important unknowns.

Do not design the future agent organization yet. Do not make a feature roadmap yet. This first answer is only the **project map / ramification view** so I can select one app to resume.

## Required output

Return valid JSON only, no markdown fence and no commentary, matching this shape:

{json.dumps(schema, indent=2, ensure_ascii=False)}
""".strip()


def selected_app_audit_schema_example(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = project.get("onboarding", {})
    selected_id = onboarding.get("selected_app_id", "")
    return {
        "schema_version": "1.0",
        "type": "selected_app_audit",
        "project_id": project.get("project", {}).get("id", ""),
        "selected_app_id": selected_id,
        "audited_at": "",
        "identity": {
            "name": "",
            "purpose": "",
            "status": "unknown",
            "scope": [],
            "out_of_scope": [],
        },
        "technical_stack": normalized_technical_stack(project.get("technical_stack")),
        "repositories": [
            {
                "name": "",
                "url": "",
                "purpose": "",
                "default_branch": "",
                "active_branch": "",
                "head_sha": "",
                "last_commit_sha": "",
                "last_commit_message": "",
                "last_push_at": "",
                "recent_commits": [],
                "open_branches_or_prs": [],
                "deployment_url": "",
                "working_state": "unknown",
                "evidence": [],
            }
        ],
        "git_state": normalized_git_state(project.get("git_state")),
        "chat_inventory": [
            {
                "title": "",
                "url": "",
                "agent_or_role": "",
                "model_label": "",
                "status": "active|standby|historical|unknown",
                "worked_on": [],
                "latest_known_action": "",
                "evidence": [],
            }
        ],
        "current_state": {
            "completed": [],
            "in_progress": [],
            "blocked": [],
            "standby": [],
            "risks": [],
            "open_questions": [],
        },
        "important_decisions": [],
        "artifacts": [],
        "mermaid": {
            "repository_topology": "graph TD",
            "work_history": "graph LR",
            "agent_activity": "graph TD",
        },
        "evidence": [],
        "unknowns": [],
    }


def _selected_app_from_map(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = project.get("onboarding", {})
    selected_id = onboarding.get("selected_app_id", "")
    for app in onboarding.get("project_map", {}).get("apps", []):
        if app.get("id") == selected_id:
            return app
    return {}


def build_selected_app_audit_prompt(project: dict[str, Any]) -> str:
    onboarding = project.get("onboarding", {})
    selected = _selected_app_from_map(project)
    schema = selected_app_audit_schema_example(project)
    return f"""# Deep resume audit for the selected app

We have now selected **{selected.get('name', onboarding.get('selected_app_id', 'the selected app'))}** (`{onboarding.get('selected_app_id', '')}`) from the project map.

Continue as the **Streamlit Setup / Resume Auditor**. This second answer must go deep only on this selected app. I need enough verified metadata to initialize Agent Manager before I ask a Director to design the operating organization.

## Audit in detail

1. Reconstruct the app's purpose, exact scope, current lifecycle state and what is explicitly out of scope.
2. Audit every relevant Git/GitHub repository: URL, purpose, default/active branch, HEAD, latest verified commit, latest verified push where visible, recent important commits, open branches/PRs when visible, working state and deployment URL.
3. Reconstruct the technical stack precisely: languages, frameworks, SDKs/libraries, runtimes, package managers, build/test tools, datastores, cloud platforms, deployment targets and developer tooling.
4. Reconstruct the conversation/agent history for this app: chat title, URL if observable, role/agent, model label if known, what it worked on, latest known action and whether it is active, standby or historical. Never invent chat URLs or model labels.
5. Summarize completed work, in-progress work, blockers, standby work, risks, unresolved questions and important decisions.
6. List important handoff/audit/spec/report artifacts that exist or are referenced.
7. Produce Mermaid source strings for repository topology, work/history flow and agent activity. Keep them semantic and based on known relationships; do not fabricate missing nodes.

Do **not** decide the future agent organization yet and do **not** create the feature roadmap yet. Those belong to the Director in later setup steps.

## Project-map selection

{json.dumps(selected, indent=2, ensure_ascii=False)}

## Required output

Return valid JSON only, no markdown fence and no commentary, matching this shape:

{json.dumps(schema, indent=2, ensure_ascii=False)}
""".strip()

