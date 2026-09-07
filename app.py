from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import streamlit as st

from agent_manager.packets import (
    agent_return_schema_example,
    bootstrap_packet,
    build_director_consolidation_packet,
    build_liaison_request,
    build_pro_director_return,
    companion_bootstrap,
    dispatch_packet,
    project_setup_json,
)
from agent_manager.schema import (
    ALLOWED_AGENT_STATUSES,
    new_blank_project,
    normalized_git_state,
    slugify,
    utc_now_iso,
    validate_agent_return,
    validate_project_config,
    validate_run_payload,
)
from agent_manager.storage import Store
from agent_manager.ui_helpers import copy_open_controls, inject_css, json_download

ROOT = Path(__file__).resolve().parent
STORE = Store(ROOT)

st.set_page_config(page_title="Agent Manager", page_icon="◎", layout="wide")
inject_css()


def load_current_project():
    projects = STORE.list_projects()
    if not projects:
        p = new_blank_project("project-1", "Project 1")
        STORE.save_project(p)
        projects = [p]
    by_id = {p["project"]["id"]: p for p in projects}
    current = st.session_state.get("project_id")
    if current not in by_id:
        current = next(iter(by_id))
        st.session_state.project_id = current
    return STORE.load_project(current), by_id


def current_run(project):
    runs = STORE.list_runs(project["project"]["id"])
    if not runs:
        return None
    ids = [r["run"]["id"] for r in runs]
    rid = st.session_state.get("run_id")
    if rid not in ids:
        rid = ids[0]
        st.session_state.run_id = rid
    return STORE.load_run(project["project"]["id"], rid)


def header(project, run):
    st.caption("PROJECT")
    st.title(project["project"]["name"])
    st.caption(project["project"].get("description", ""))
    if run:
        st.caption(f"Current run: {run['run']['id']} · {run['run']['title']}")


def dispatch_board(project, run):
    header(project, run)
    if not run:
        st.info("No run yet. Import a Director/Companion run JSON first.")
        return
    st.write(run["run"].get("objective", ""))
    git = normalized_git_state(project.get("git_state"))
    st.caption(f"Git {git.get('active_branch') or '—'} · {(git.get('head_sha') or '—')[:12]}")
    for agent_id, dispatch in run.get("dispatches", {}).items():
        agent = project.get("agents", {}).get(agent_id, {})
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{agent.get('name', agent_id)}**")
            c1.caption(dispatch.get("title", ""))
            c2.write(dispatch.get("model_label") or agent.get("model_label", ""))
            status = dispatch.get("status", "ready")
            choices = sorted(ALLOWED_AGENT_STATUSES)
            new_status = c3.selectbox("Status", choices, index=choices.index(status) if status in choices else 0, key=f"status_{run['run']['id']}_{agent_id}", label_visibility="collapsed")
            if new_status != status:
                run["dispatches"][agent_id]["status"] = new_status
                STORE.save_run(project["project"]["id"], run)
                st.rerun()
            packet = dispatch_packet(project, run, agent_id)
            copy_open_controls(packet, agent.get("chat_url", ""))
            if agent.get("chat_url"):
                st.link_button("Open conversation ↗", agent["chat_url"])
            with st.expander("Prompt preview"):
                st.code(packet, language=None, wrap_lines=True)


def agents_page(project, run):
    header(project, run)
    st.subheader("Agents")
    ids = list(project.get("agents", {}))
    if not ids:
        st.info("No agents configured.")
        return
    tabs = st.tabs([project["agents"][i].get("name", i) for i in ids])
    for tab, aid in zip(tabs, ids):
        with tab:
            agent = project["agents"][aid]
            with st.form(f"agent_{aid}"):
                agent["name"] = st.text_input("Name", value=agent.get("name", ""))
                agent["role"] = st.text_input("Role", value=agent.get("role", ""))
                agent["model_label"] = st.text_input("Model label", value=agent.get("model_label", ""))
                agent["surface"] = st.text_input("Surface", value=agent.get("surface", "ChatGPT"))
                agent["chat_url"] = st.text_input("Conversation URL", value=agent.get("chat_url", ""))
                agent["custom_instructions"] = st.text_area("Custom instructions", value=agent.get("custom_instructions", ""), height=180)
                agent["reporting_contract"] = st.text_area("Reporting contract", value=agent.get("reporting_contract", ""), height=120)
                agent["bootstrap_installed"] = st.checkbox("Bootstrap installed", value=bool(agent.get("bootstrap_installed")))
                if st.form_submit_button("Save agent"):
                    STORE.save_project(project)
                    st.rerun()
            boot = companion_bootstrap(project) if aid == "companion" else bootstrap_packet(project, agent)
            copy_open_controls(boot, agent.get("chat_url", ""), "Copy + Open")
            with st.expander("Bootstrap prompt"):
                st.code(boot, language=None, wrap_lines=True)


def import_returns(project, run):
    header(project, run)
    run_tab, return_tab, director_tab = st.tabs(["Import Director run", "Import agent return", "Director consolidation"])
    with run_tab:
        raw = st.text_area("Paste agent_manager_run JSON", height=360)
        if raw.strip():
            try:
                payload = json.loads(raw)
                errors = validate_run_payload(payload, project)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.success(f"Valid run: {payload['run']['id']}")
                    st.json(payload)
                    if st.button("Apply run", type="primary"):
                        STORE.apply_run_payload(project, payload)
                        st.session_state.run_id = payload["run"]["id"]
                        st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
    with return_tab:
        raw = st.text_area("Paste agent_return JSON", height=320, key="agent_return")
        if raw.strip():
            try:
                payload = json.loads(raw)
                errors = validate_agent_return(payload, project)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    target = STORE.load_run(project["project"]["id"], payload["run_id"])
                    target.setdefault("returns", {})[payload["agent_id"]] = payload
                    if payload["agent_id"] in target.get("dispatches", {}):
                        target["dispatches"][payload["agent_id"]]["status"] = "returned"
                    if st.button("Store return", type="primary"):
                        STORE.save_run(project["project"]["id"], target)
                        st.session_state.run_id = payload["run_id"]
                        st.rerun()
            except Exception as e:
                st.error(str(e))
        with st.expander("Return JSON example"):
            st.json(agent_return_schema_example(project))
    with director_tab:
        if not run:
            st.info("Select a run first.")
        elif not run.get("returns"):
            st.info("No stored returns yet.")
        else:
            packet = build_director_consolidation_packet(project, run, run.get("returns", {}))
            director = project.get("agents", {}).get("director", {})
            copy_open_controls(packet, director.get("chat_url", ""), "Copy + Open Director")
            st.code(packet, language=None, wrap_lines=True)


def pro_page(project, run):
    header(project, run)
    desk = project.get("pro_desk", {})
    liaison = project.get("agents", {}).get(desk.get("liaison_agent_id", "pro_liaison"), {})
    pro = project.get("agents", {}).get(desk.get("pro_agent_id", "pro_advisor"), {})
    director = project.get("agents", {}).get(desk.get("director_agent_id", "director"), {})
    a, b, c = st.tabs(["Ask Liaison", "Send to Pro", "Return to Director"])
    with a:
        packet = build_liaison_request(project, run)
        copy_open_controls(packet, liaison.get("chat_url", ""), "Copy + Open Liaison")
        st.code(packet, language=None, wrap_lines=True)
    with b:
        brief = st.text_area("Paste Liaison's final Pro prompt", height=320)
        if brief.strip():
            copy_open_controls(brief, pro.get("chat_url", ""), "Copy + Open Pro")
    with c:
        answer = st.text_area("Paste Pro Advisor answer", height=320)
        if answer.strip():
            packet = build_pro_director_return(project, run, answer)
            copy_open_controls(packet, director.get("chat_url", ""), "Copy + Open Director")
            st.code(packet, language=None, wrap_lines=True)


def git_page(project, run):
    header(project, run)
    git = normalized_git_state(project.get("git_state"))
    with st.form("git"):
        repo = st.text_input("Repository URL", value=git.get("repository_url", ""))
        branch = st.text_input("Active branch", value=git.get("active_branch", ""))
        head = st.text_input("HEAD SHA", value=git.get("head_sha", ""))
        last_sha = st.text_input("Last commit SHA", value=git.get("last_commit", {}).get("sha", ""))
        last_msg = st.text_input("Last commit message", value=git.get("last_commit", {}).get("message", ""))
        last_push = st.text_input("Last push at", value=git.get("last_push_at", ""))
        notes = st.text_area("Notes", value=git.get("notes", ""))
        if st.form_submit_button("Save Git snapshot"):
            git.update({"repository_url": repo, "active_branch": branch, "head_sha": head, "last_push_at": last_push, "snapshot_at": utc_now_iso(), "notes": notes})
            git["last_commit"].update({"sha": last_sha, "message": last_msg})
            project["git_state"] = git
            STORE.save_project(project)
            st.rerun()
    json_download("Download Git snapshot", git, f"{project['project']['id']}_git.json")


def setup_page(project, run):
    header(project, run)
    st.subheader("ChatGPT Project setup")
    st.code(project.get("shared_project_instructions", ""), language=None, wrap_lines=True)
    setup = project_setup_json(project)
    json_download("Download Project setup JSON", setup, f"{project['project']['id']}_setup.json")
    st.subheader("Required conversations")
    for item in setup["conversations"]:
        st.write(f"- **{item['conversation_name']}** — {item['role']} · `{item['model_label']}`")


def settings_page(project, run):
    header(project, run)
    p = project["project"]
    with st.form("project_settings"):
        p["name"] = st.text_input("Name", value=p.get("name", ""))
        p["description"] = st.text_area("Description", value=p.get("description", ""))
        p["chatgpt_project_url"] = st.text_input("ChatGPT Project URL", value=p.get("chatgpt_project_url", ""))
        project["shared_project_instructions"] = st.text_area("Shared Project instructions", value=project.get("shared_project_instructions", ""), height=260)
        if st.form_submit_button("Save project"):
            STORE.save_project(project)
            st.rerun()
    st.subheader("Add agent")
    with st.form("add_agent"):
        name = st.text_input("Agent name")
        aid = st.text_input("Agent ID")
        role = st.text_input("Role")
        model = st.text_input("Model label")
        if st.form_submit_button("Add agent"):
            new_id = slugify(aid or name).replace("-", "_")
            project.setdefault("agents", {})[new_id] = {"id": new_id, "name": name, "role": role, "surface": "ChatGPT", "model_label": model, "chat_url": "", "bootstrap_installed": False, "receives_dispatch": True, "custom_instructions": "", "reporting_contract": ""}
            STORE.save_project(project)
            st.rerun()
    errors = validate_project_config(project)
    if errors:
        for e in errors:
            st.error(e)
    else:
        st.success("Project configuration valid.")
    json_download("Download project JSON", project, f"{p['id']}_project.json")


project, projects = load_current_project()
run = current_run(project)

with st.sidebar:
    st.caption("CONTROL PLANE")
    st.markdown("## Agent Manager")
    names = {p["project"]["name"]: pid for pid, p in projects.items()}
    selected = st.selectbox("Project", list(names), index=list(names).index(project["project"]["name"]), label_visibility="collapsed")
    if names[selected] != project["project"]["id"]:
        st.session_state.project_id = names[selected]
        st.session_state.pop("run_id", None)
        st.rerun()
    page = st.radio("Navigation", ["Dispatch Board", "Agents", "Import / Returns", "Pro Desk", "Git Snapshot", "Project Setup", "Settings"], label_visibility="collapsed")
    st.divider()
    st.caption("Manual ChatGPT/Codex execution · no paid OpenAI API calls")

if page == "Dispatch Board":
    dispatch_board(project, run)
elif page == "Agents":
    agents_page(project, run)
elif page == "Import / Returns":
    import_returns(project, run)
elif page == "Pro Desk":
    pro_page(project, run)
elif page == "Git Snapshot":
    git_page(project, run)
elif page == "Project Setup":
    setup_page(project, run)
elif page == "Settings":
    settings_page(project, run)
