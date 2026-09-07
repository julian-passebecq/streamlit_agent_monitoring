from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import streamlit as st

from .packets import build_prompt_agent_request, companion_run_schema_example, dispatch_packet, prompt_agent_bootstrap
from .schema import (
    ALLOWED_AGENT_STATUSES,
    CYCLE_PHASES,
    FEATURE_KINDS,
    FEATURE_PRIORITIES,
    FEATURE_STATUSES,
    normalized_cycle,
    normalized_git_state,
    utc_now_iso,
    validate_run_payload,
)
from .ui_common import STORE, project_header, rerun
from .ui_helpers import agent_card, copy_open_controls, org_node

CONTROL_AGENT_IDS = {"startup_agent", "director", "prompt_agent", "companion", "pro_liaison", "pro_advisor"}

def control_room_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    if not run:
        st.info("No cycle exists yet. Start with Start / Resume or import a packaged run.")
        return
    run_obj = run.get("run", {})
    cycle = normalized_cycle(run)
    git = normalized_git_state(project.get("git_state"))
    st.markdown(f"## {run_obj.get('title', '')}")
    st.write(run_obj.get("objective", ""))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cycle", cycle.get("number", "—"))
    m2.metric("Phase", cycle.get("phase", "—"))
    m3.metric("Active agents", len(cycle.get("active_agents", [])))
    m4.metric("Returns", len(run.get("returns", {})))
    st.caption(
        f"Git {git.get('active_branch') or '—'} · {(git.get('head_sha') or '—')[:12]} · last push {git.get('last_push_at') or 'unknown'}"
    )

    dispatches = run.get("dispatches", {})
    if not dispatches:
        st.warning("This cycle is still in planning: no worker prompts are packaged yet. Go to Prompt Studio after Director has written the cycle brief.")
        return

    st.markdown("### Dispatch queue")
    for agent_id, dispatch in dispatches.items():
        agent = project.get("agents", {}).get(agent_id, {})
        status = dispatch.get("status", "ready")
        with st.container(border=True):
            top_a, top_b, top_c = st.columns([3, 2, 1])
            top_a.markdown(f"**{agent.get('name', agent_id)}**")
            top_a.caption(dispatch.get("title", ""))
            top_b.caption("MODEL")
            top_b.write(dispatch.get("model_label") or agent.get("model_label", ""))
            choices = sorted(ALLOWED_AGENT_STATUSES)
            selected = top_c.selectbox(
                "Status",
                choices,
                index=choices.index(status) if status in choices else 0,
                key=f"status_{run_obj.get('id')}_{agent_id}",
                label_visibility="collapsed",
            )
            if selected != status:
                run["dispatches"][agent_id]["status"] = selected
                STORE.save_run(project["project"]["id"], run)
                rerun()
            prompt = dispatch_packet(project, run, agent_id)
            copy_open_controls(prompt, agent.get("chat_url", ""))
            if agent.get("chat_url"):
                st.link_button("Open conversation ↗", agent["chat_url"])
            with st.expander("Prompt preview"):
                st.code(prompt, language=None, wrap_lines=True)


def current_active_agents(project: dict[str, Any], run: dict[str, Any] | None) -> list[str]:
    if run:
        cycle = normalized_cycle(run)
        if cycle.get("active_agents"):
            return [aid for aid in cycle["active_agents"] if aid in project.get("agents", {})]
    return [
        aid
        for aid, agent in project.get("agents", {}).items()
        if agent.get("receives_dispatch", True) and agent.get("active_default", True) and aid not in CONTROL_AGENT_IDS
    ]


def organization_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## Agent organization")
    st.caption("The organigram is project-specific. Startup/Resume Audit may propose a different structure; stable agent IDs preserve saved conversation links when possible.")
    agents = project.get("agents", {})
    active = set(current_active_agents(project, run))

    st.markdown("### Control chain")
    chain_ids = [aid for aid in ["startup_agent", "technical_lead", "director", "prompt_agent"] if aid in agents]
    cols = st.columns(max(1, len(chain_ids)))
    for col, aid in zip(cols, chain_ids):
        with col:
            status = "idle"
            if run and aid in run.get("dispatches", {}):
                status = run["dispatches"][aid].get("status", "ready")
            org_node(agents[aid], True, status)
    if chain_ids:
        st.markdown('<div class="am-arrow">↓ selected worker pool ↓</div>', unsafe_allow_html=True)

    workers = [aid for aid, a in agents.items() if a.get("receives_dispatch", True) and aid not in CONTROL_AGENT_IDS]
    if workers:
        cols = st.columns(min(4, len(workers)))
        for index, aid in enumerate(workers):
            with cols[index % len(cols)]:
                dispatch = (run or {}).get("dispatches", {}).get(aid, {})
                status = dispatch.get("status", "standby" if aid not in active else "ready")
                org_node(agents[aid], aid in active, status)

    pro_ids = [aid for aid in ["pro_liaison", "pro_advisor"] if aid in agents]
    if pro_ids:
        st.markdown("### Optional advisory branch")
        cols = st.columns(len(pro_ids))
        for col, aid in zip(cols, pro_ids):
            with col:
                org_node(agents[aid], False, "standby")

    st.markdown("### Active worker selection")
    st.write("These toggles define which worker conversations the **Prompt Agent is allowed to package in the current cycle**. Standby agents keep their role/chat history but receive no prompt this cycle.")
    changed = False
    new_active: list[str] = []
    toggle_cols = st.columns(3)
    for idx, aid in enumerate(workers):
        agent = agents[aid]
        with toggle_cols[idx % 3]:
            is_active = st.toggle(
                f"{agent.get('name', aid)} · {agent.get('model_label', '')}",
                value=aid in active,
                key=f"active_{(run or {}).get('run', {}).get('id', 'project')}_{aid}",
            )
            if is_active:
                new_active.append(aid)
            if is_active != (aid in active):
                changed = True
    if changed:
        if run:
            run.setdefault("cycle", {})["active_agents"] = new_active
            run["cycle"]["standby_agents"] = [aid for aid in workers if aid not in new_active]
            run.setdefault("cycle_history", []).append({
                "at": utc_now_iso(),
                "event": "agent_selection_changed",
                "active_agents": new_active,
            })
            STORE.save_run(project["project"]["id"], run)
        else:
            for aid in workers:
                project["agents"][aid]["active_default"] = aid in new_active
            STORE.save_project(project)
        rerun()

    if run:
        st.markdown("### Current prompts")
        for aid in workers:
            agent = agents[aid]
            dispatch = run.get("dispatches", {}).get(aid)
            label = f"{'●' if aid in active else '–'} {agent.get('name', aid)}"
            with st.expander(label):
                if dispatch:
                    st.code(dispatch_packet(project, run, aid), language=None, wrap_lines=True)
                else:
                    st.caption("No packaged prompt in this cycle.")


def prompt_studio_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## Prompt Studio")
    st.write("Director decides **what** each selected agent should accomplish. Prompt Agent decides **how to express those assignments clearly** for the target model/surface without changing scope or technical decisions.")
    prompt_agent = project.get("agents", {}).get("prompt_agent", {})
    selected = current_active_agents(project, run)
    st.caption(f"Selected worker IDs: {', '.join(selected) or 'none'}")

    brief_tab, result_tab, method_tab = st.tabs(["1 · Director brief → Prompt Agent", "2 · Import packaged run", "3 · Prompt method"])
    with brief_tab:
        director_brief = st.text_area(
            "Paste Director's cycle brief / orchestration instructions",
            height=300,
            placeholder="Director describes decisions, assignments, priorities, dependencies, QA/audit requirements and expected outcome. Prompt Agent will not add decisions.",
            key="director_brief",
        )
        if not selected:
            st.warning("No active workers selected. Use Organization first.")
        elif director_brief.strip():
            packet = build_prompt_agent_request(project, director_brief, selected, run)
            copy_open_controls(packet, prompt_agent.get("chat_url", ""), "Copy + Open Prompt Agent")
            with st.expander("Prompt Agent request", expanded=True):
                st.code(packet, language=None, wrap_lines=True)
        else:
            st.info("Paste the Director brief to build the Prompt Agent request.")

    with result_tab:
        raw = st.text_area("Paste Prompt Agent agent_manager_run JSON", height=390, key="prompt_agent_run")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_run_payload(parsed, project)
                unexpected = set(parsed.get("dispatches", {})) - set(selected)
                if unexpected:
                    errors.append(f"Prompt Agent packaged unselected agents: {', '.join(sorted(unexpected))}.")
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            st.success("Packaged run is valid and respects the active-agent selection.")
            st.write(f"Run **{parsed['run']['id']}** · {len(parsed.get('dispatches', {}))} dispatches")
            if st.button("Apply packaged run", type="primary"):
                STORE.apply_run_payload(project, parsed)
                st.session_state.run_id = parsed["run"]["id"]
                rerun()

    with method_tab:
        st.markdown("### Prompt Agent bootstrap")
        method = prompt_agent_bootstrap(project)
        copy_open_controls(method, prompt_agent.get("chat_url", ""), "Copy + Open Prompt Agent")
        st.code(method, language=None, wrap_lines=True)
        st.caption("The embedded method follows current OpenAI guidance: clear/specific instructions, instructions before context, explicit output formats when needed, bounded requests, and iterative refinement. It also adds project-control rules: evidence, role authority, model labels and no invented context.")


