from __future__ import annotations

import json
from typing import Any

import streamlit as st

from .packets import (
    agent_return_schema_example,
    bootstrap_packet,
    build_director_consolidation_packet,
    build_liaison_request,
    build_pro_director_return,
    combined_bootstrap_and_dispatch,
    companion_bootstrap,
    companion_run_schema_example,
    dispatch_packet,
    prompt_agent_bootstrap,
)
from .schema import (
    normalized_git_state,
    normalized_technical_stack,
    utc_now_iso,
    validate_agent_return,
    validate_run_payload,
)
from .ui_common import STORE, project_header, rerun
from .ui_helpers import agent_card, copy_open_controls, json_download
from .control_ui import current_active_agents

def agents_page(project: dict[str, Any], run: dict[str, Any] | None, selected_agent_id: str | None = None) -> None:
    project_header(project, run)
    agents = project.get("agents", {})
    if not agents:
        st.info("No agents configured. Start with Start / Resume.")
        return
    if selected_agent_id and selected_agent_id in agents:
        agent_id = selected_agent_id
    else:
        labels = {f"{a.get('name', aid)} · {a.get('model_label', '')}": aid for aid, a in agents.items()}
        selected_label = st.selectbox("Agent", list(labels))
        agent_id = labels[selected_label]
    agent = agents[agent_id]

    status = "idle"
    dispatch = None
    if run and agent_id in run.get("dispatches", {}):
        dispatch = run["dispatches"][agent_id]
        status = dispatch.get("status", "ready")
    elif agent_id not in current_active_agents(project, run) and agent.get("receives_dispatch", False):
        status = "standby"
    agent_card(agent, status, "Persistent role contract + current cycle context")

    overview, bootstrap_tab, current_tab, edit_tab = st.tabs(["Overview", "Bootstrap", "Current dispatch", "Edit agent"])
    with overview:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Model", agent.get("model_label", ""))
        col2.metric("Surface", agent.get("surface", ""))
        col3.metric("Bootstrap", "installed" if agent.get("bootstrap_installed") else "not marked")
        col4.metric("Default", "active" if agent.get("active_default", agent.get("receives_dispatch", True)) else "standby")
        if agent.get("chat_url"):
            st.link_button("Open stored conversation ↗", agent["chat_url"])
        st.markdown("#### Role contract")
        st.write(agent.get("custom_instructions", ""))
        st.markdown("#### Reporting contract")
        st.write(agent.get("reporting_contract", ""))

    with bootstrap_tab:
        if agent_id == "companion":
            boot = companion_bootstrap(project)
        elif agent_id == "prompt_agent":
            boot = prompt_agent_bootstrap(project)
        else:
            boot = bootstrap_packet(project, agent)
        copy_open_controls(boot, agent.get("chat_url", ""), "Copy + Open")
        st.code(boot, language=None, wrap_lines=True)
        installed = st.checkbox("Bootstrap has been sent to this conversation", value=bool(agent.get("bootstrap_installed")), key=f"boot_{agent_id}")
        if installed != bool(agent.get("bootstrap_installed")):
            project["agents"][agent_id]["bootstrap_installed"] = installed
            STORE.save_project(project)
            rerun()

    with current_tab:
        if dispatch and run:
            prompt = dispatch_packet(project, run, agent_id)
            combined = combined_bootstrap_and_dispatch(project, run, agent_id)
            mode = st.radio("Packet", ["Current dispatch", "Bootstrap + current dispatch"], horizontal=True)
            shown = prompt if mode == "Current dispatch" else combined
            copy_open_controls(shown, agent.get("chat_url", ""))
            st.code(shown, language=None, wrap_lines=True)
        else:
            st.info("This agent has no packaged dispatch in the selected cycle.")

    with edit_tab:
        with st.form(f"agent_edit_{agent_id}"):
            name = st.text_input("Name", value=agent.get("name", ""))
            role = st.text_input("Role", value=agent.get("role", ""))
            surface = st.text_input("Surface label", value=agent.get("surface", "ChatGPT"))
            model = st.text_input("Model label", value=agent.get("model_label", ""))
            chat_url = st.text_input("Conversation URL", value=agent.get("chat_url", ""))
            instructions = st.text_area("Custom instructions", value=agent.get("custom_instructions", ""), height=260)
            reporting = st.text_area("Reporting contract", value=agent.get("reporting_contract", ""), height=150)
            receives = st.checkbox("May receive normal Director work", value=bool(agent.get("receives_dispatch", True)))
            active_default = st.checkbox("Active by default", value=bool(agent.get("active_default", receives)))
            if st.form_submit_button("Save agent", type="primary"):
                agent.update({
                    "name": name,
                    "role": role,
                    "surface": surface,
                    "model_label": model,
                    "chat_url": chat_url,
                    "custom_instructions": instructions,
                    "reporting_contract": reporting,
                    "receives_dispatch": receives,
                    "active_default": active_default,
                })
                STORE.save_project(project)
                rerun()


def import_returns_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    import_tab, return_tab, consolidate_tab = st.tabs(["Import packaged run", "Import agent return", "Director consolidation"])
    with import_tab:
        st.caption("Normally Prompt Studio imports the Prompt Agent output. Use this generic importer for Companion repairs or external JSON.")
        raw = st.text_area("agent_manager_run JSON", height=360, key="run_json_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_run_payload(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            st.success("Schema valid for selected project.")
            st.write(f"Run: **{parsed.get('run', {}).get('id')}** — {parsed.get('run', {}).get('title')}")
            st.write(f"Dispatches: {', '.join(sorted(parsed.get('dispatches', {}))) or 'none'}")
            if st.button("Apply imported run", type="primary"):
                STORE.apply_run_payload(project, parsed)
                st.session_state.run_id = parsed["run"]["id"]
                rerun()
        with st.expander("Run schema example"):
            example = companion_run_schema_example(project, current_active_agents(project, run))
            st.code(json.dumps(example, indent=2, ensure_ascii=False), language="json")

    with return_tab:
        st.caption("Audit returns may include `feature_updates`; Agent Manager applies them to the feature ledger and records history against this cycle.")
        raw_return = st.text_area("Agent return JSON", height=340, key="agent_return_import")
        parsed_return = None
        return_errors: list[str] = []
        if raw_return.strip():
            try:
                parsed_return = json.loads(raw_return)
                return_errors = validate_agent_return(parsed_return, project)
            except json.JSONDecodeError as exc:
                return_errors = [f"Invalid JSON: {exc}"]
        if return_errors:
            for error in return_errors:
                st.error(error)
        elif parsed_return:
            try:
                STORE.load_run(project["project"]["id"], parsed_return["run_id"])
            except FileNotFoundError:
                st.error(f"Run {parsed_return['run_id']!r} does not exist locally.")
            else:
                st.success(f"Valid return for {parsed_return['agent_id']} / {parsed_return['run_id']}.")
                if parsed_return.get("feature_updates"):
                    st.info(f"This return contains {len(parsed_return['feature_updates'])} feature-ledger updates.")
                if st.button("Store return", type="primary"):
                    STORE.store_agent_return(project, parsed_return)
                    st.session_state.run_id = parsed_return["run_id"]
                    rerun()
        with st.expander("Return schema example"):
            st.code(json.dumps(agent_return_schema_example(project), indent=2, ensure_ascii=False), language="json")

    with consolidate_tab:
        if not run:
            st.info("Select/import a cycle first.")
        else:
            returns = run.get("returns", {})
            st.write(f"Stored returns: **{len(returns)}**")
            for agent_id, payload in returns.items():
                st.caption(f"✓ {project.get('agents', {}).get(agent_id, {}).get('name', agent_id)} · {payload.get('status', '')}")
            if returns:
                packet = build_director_consolidation_packet(project, run, returns)
                director = project.get("agents", {}).get("director", {})
                copy_open_controls(packet, director.get("chat_url", ""), "Copy + Open Director")
                st.code(packet, language=None, wrap_lines=True)
            else:
                st.info("No returns stored for this cycle yet.")


