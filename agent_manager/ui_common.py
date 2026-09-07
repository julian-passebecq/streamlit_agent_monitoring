from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import streamlit as st

from .schema import APP_VERSION, normalized_cycle, normalized_git_state, normalized_technical_stack, new_blank_project, slugify, utc_now_iso
from .storage import Store

ROOT = Path(__file__).resolve().parents[1]
STORE = Store(ROOT)

def rerun() -> None:
    st.rerun()


def csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def projects_index() -> dict[str, dict[str, Any]]:
    return {p["project"]["id"]: p for p in STORE.list_projects()}


def select_project() -> dict[str, Any]:
    projects = projects_index()
    if not projects:
        blank = new_blank_project("project-1", "Project 1")
        STORE.save_project(blank)
        projects = projects_index()

    ids = list(projects)
    current = st.session_state.get("project_id")
    if current not in projects:
        current = ids[0]
        st.session_state.project_id = current

    label_to_id = {projects[pid]["project"]["name"]: pid for pid in ids}
    names = list(label_to_id)
    current_name = projects[current]["project"]["name"]
    with st.sidebar:
        st.markdown('<div class="am-kicker">Control plane</div>', unsafe_allow_html=True)
        st.markdown("## Agent Manager")
        st.caption(f"v{APP_VERSION}")
        picked = st.selectbox("Project", names, index=names.index(current_name), label_visibility="collapsed")
        picked_id = label_to_id[picked]
        if picked_id != current:
            st.session_state.project_id = picked_id
            st.session_state.pop("run_id", None)
            rerun()
        if st.button("＋ New project", use_container_width=True):
            st.session_state.show_new_project = True
    return STORE.load_project(st.session_state.project_id)


def select_run(project: dict[str, Any]) -> dict[str, Any] | None:
    project_id = project["project"]["id"]
    runs = STORE.list_runs(project_id)
    if not runs:
        return None
    ids = [r["run"]["id"] for r in runs]
    current = st.session_state.get("run_id")
    if current not in ids:
        current = ids[0]
        st.session_state.run_id = current
    return STORE.load_run(project_id, current)


def show_new_project_dialog() -> None:
    if not st.session_state.get("show_new_project"):
        return
    with st.sidebar.expander("Create project", expanded=True):
        name = st.text_input("Project name", key="new_project_name")
        requested_id = st.text_input("Project ID", value=slugify(name), key="new_project_id")
        template = st.selectbox("Template", ["Blank", "Copy current agent structure"])
        if st.button("Create", type="primary", use_container_width=True):
            project_id = slugify(requested_id or name)
            if not name:
                st.error("Project name is required.")
            elif (ROOT / "data" / "projects" / f"{project_id}.json").exists():
                st.error("That project ID already exists.")
            else:
                if template == "Copy current agent structure":
                    source = STORE.load_project(st.session_state.project_id)
                    new_project = deepcopy(source)
                    new_project["project"] = {
                        "id": project_id,
                        "name": name,
                        "description": "",
                        "status": "active",
                        "chatgpt_project_url": "",
                        "repository_url": "",
                    }
                    for agent in new_project.get("agents", {}).values():
                        agent["chat_url"] = ""
                        agent["bootstrap_installed"] = False
                    new_project["git_state"] = normalized_git_state({})
                    new_project["technical_stack"] = normalized_technical_stack({})
                    new_project["repositories"] = []
                    new_project["cycle_plan"] = {}
                    new_project["created_at"] = utc_now_iso()
                else:
                    new_project = new_blank_project(project_id, name)
                STORE.save_project(new_project)
                st.session_state.project_id = project_id
                st.session_state.show_new_project = False
                st.session_state.pop("run_id", None)
                rerun()


def sidebar_navigation(project: dict[str, Any], run: dict[str, Any] | None) -> str:
    def nav_button(label: str, page_id: str, key: str) -> None:
        active = st.session_state.get("nav_page", "1 · Project Map") == page_id
        button_label = f"{'● ' if active else ''}{label}"
        if st.button(button_label, key=key, use_container_width=True, type="primary" if active else "secondary"):
            st.session_state.nav_page = page_id
            rerun()

    with st.sidebar:
        show_new_project_dialog()
        st.divider()
        if run:
            cycle = normalized_cycle(run)
            st.caption(f"CURRENT · Cycle {cycle.get('number')} · {cycle.get('phase')}")
        else:
            st.caption("CURRENT · setup / no active cycle")

        st.caption("SETUP WIZARD")
        setup_pages = [
            ("1 · Project Map", "1 · Project Map"),
            ("2 · App Deep Audit", "2 · App Deep Audit"),
            ("3 · Director / Organization", "3 · Director / Organization"),
            ("4 · Features / Plan", "4 · Features / Plan"),
            ("5 · Agent Setup", "5 · Agent Setup"),
        ]
        for idx, (label, page_id) in enumerate(setup_pages):
            nav_button(label, page_id, f"nav_setup_{idx}")

        st.caption("OPERATE")
        operate_pages = [
            ("Control Room", "Control Room"),
            ("Organization", "Organization"),
            ("Prompt Studio", "Prompt Studio"),
            ("Features / Pilot", "Features / Pilot"),
            ("Cycles", "Cycles"),
            ("Import / Returns", "Import / Returns"),
            ("Pro Desk", "Pro Desk"),
            ("Git & Stack", "Git & Stack"),
            ("Archive", "Archive"),
        ]
        for idx, (label, page_id) in enumerate(operate_pages):
            nav_button(label, page_id, f"nav_operate_{idx}")

        agents = project.get("agents", {})
        if agents:
            st.caption("AGENT CHATS")
            for idx, (agent_id, agent) in enumerate(agents.items()):
                name = agent.get("name", agent_id)
                model = agent.get("model_label", "")
                suffix = f" · {model}" if model else ""
                nav_button(f"{name}{suffix}", f"Agent::{agent_id}", f"nav_agent_{idx}_{agent_id}")

        st.caption("PROJECT")
        nav_button("Project Setup / Export", "Project Setup", "nav_project_setup")
        nav_button("Settings", "Settings", "nav_settings")
        st.divider()
        st.caption("Manual ChatGPT/Codex execution")
        st.caption("No paid OpenAI API calls · no fake completion polling")

    return st.session_state.get("nav_page", "1 · Project Map")

def project_header(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    p = project["project"]
    st.markdown('<div class="am-kicker">Project</div>', unsafe_allow_html=True)
    left, right = st.columns([4, 1])
    with left:
        st.title(p.get("name", ""))
        onboarding = project.get("onboarding", {})
        parent_name = onboarding.get("chatgpt_project_name", "")
        selected_id = onboarding.get("selected_app_id", "")
        if parent_name:
            suffix = f" · selected app `{selected_id}`" if selected_id else " · no app selected yet"
            st.caption(f"ChatGPT Project: {parent_name}{suffix}")
        if p.get("description"):
            st.caption(p["description"])
    with right:
        if run:
            cycle = normalized_cycle(run)
            st.metric("Cycle", f"{cycle.get('number')} · {cycle.get('phase')}")
        else:
            st.metric("Cycle", "—")


