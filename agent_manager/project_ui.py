from __future__ import annotations

from typing import Any

import streamlit as st

from .packets import (
    bootstrap_packet,
    build_startup_audit_prompt,
    companion_bootstrap,
    companion_run_schema_example,
    project_setup_json,
    prompt_agent_bootstrap,
    startup_audit_schema_example,
)
from .schema import SCHEMA_VERSION, slugify, validate_project_config
from .ui_common import STORE, project_header, rerun
from .ui_helpers import copy_open_controls, json_download
from .control_ui import current_active_agents

def project_setup_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## ChatGPT Project setup pack")
    setup = project_setup_json(project)
    left, right = st.columns([2, 1])
    with left:
        st.markdown("### Shared Project instructions")
        st.code(project.get("shared_project_instructions", ""), language=None, wrap_lines=True)
        st.markdown("### Conversation roster")
        for item in setup["conversations"]:
            state = "active default" if item.get("active_default") else "standby default"
            st.write(f"- **{item['conversation_name']}** — {item['role']} · `{item['model_label']}` · {state}")
    with right:
        json_download("Download complete Project setup JSON", setup, f"{project['project']['id']}_chatgpt_project_setup.json")
        json_download("Download startup audit schema", startup_audit_schema_example(project), f"{project['project']['id']}_startup_audit_schema.json")
        json_download("Download run schema", companion_run_schema_example(project, current_active_agents(project, run)), f"{project['project']['id']}_run_schema.json")

    st.markdown("### Start / Resume audit prompt")
    with st.expander("View reusable startup prompt"):
        st.code(build_startup_audit_prompt(project), language=None, wrap_lines=True)
    st.markdown("### Agent bootstraps")
    for agent_id, agent in project.get("agents", {}).items():
        with st.expander(f"{agent.get('name', agent_id)} · {agent.get('model_label', '')}"):
            if agent_id == "companion":
                boot = companion_bootstrap(project)
            elif agent_id == "prompt_agent":
                boot = prompt_agent_bootstrap(project)
            else:
                boot = bootstrap_packet(project, agent)
            copy_open_controls(boot, agent.get("chat_url", ""))
            st.code(boot, language=None, wrap_lines=True)


def settings_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    p = project.get("project", {})
    with st.form("project_settings"):
        name = st.text_input("Name", value=p.get("name", ""))
        description = st.text_area("Description", value=p.get("description", ""), height=90)
        chatgpt_project_url = st.text_input("ChatGPT Project URL", value=p.get("chatgpt_project_url", ""))
        repo_url = st.text_input("Primary repository URL", value=p.get("repository_url", ""))
        shared = st.text_area("Shared ChatGPT Project instructions", value=project.get("shared_project_instructions", ""), height=260)
        workflow = st.text_area("Workflow description", value=project.get("workflow", {}).get("description", ""), height=120)
        if st.form_submit_button("Save project", type="primary"):
            p.update({"name": name, "description": description, "chatgpt_project_url": chatgpt_project_url, "repository_url": repo_url})
            project["shared_project_instructions"] = shared
            project.setdefault("workflow", {})["description"] = workflow
            STORE.save_project(project)
            rerun()

    st.markdown("### Add agent")
    with st.form("add_agent"):
        agent_name = st.text_input("Agent name")
        agent_id = st.text_input("Agent ID")
        role = st.text_input("Role")
        model = st.text_input("Model label")
        surface = st.text_input("Surface", value="ChatGPT")
        if st.form_submit_button("Add agent"):
            new_id = slugify(agent_id or agent_name).replace("-", "_")
            if not agent_name or not role or not model:
                st.error("Name, role and model label are required.")
            elif new_id in project.get("agents", {}):
                st.error("Agent ID already exists.")
            else:
                project.setdefault("agents", {})[new_id] = {
                    "id": new_id,
                    "name": agent_name,
                    "role": role,
                    "surface": surface,
                    "model_label": model,
                    "chat_url": "",
                    "bootstrap_installed": False,
                    "receives_dispatch": True,
                    "active_default": True,
                    "custom_instructions": "",
                    "reporting_contract": "",
                }
                STORE.save_project(project)
                rerun()

    st.markdown("### JSON configuration")
    errors = validate_project_config(project)
    if errors:
        for error in errors:
            st.error(error)
    else:
        st.success(f"Project configuration conforms to schema {SCHEMA_VERSION}.")
    json_download("Download project config", project, f"{p.get('id')}_project.json")
