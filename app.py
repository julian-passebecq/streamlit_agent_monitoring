from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import streamlit as st

from agent_manager.packets import (
    agent_return_schema_example,
    bootstrap_packet,
    build_director_consolidation_packet,
    build_liaison_request,
    build_pro_director_return,
    build_prompt_agent_request,
    build_startup_audit_prompt,
    combined_bootstrap_and_dispatch,
    companion_bootstrap,
    companion_run_schema_example,
    dispatch_packet,
    metadata_block,
    project_setup_json,
    prompt_agent_bootstrap,
    startup_audit_schema_example,
)
from agent_manager.schema import (
    ALLOWED_AGENT_STATUSES,
    APP_VERSION,
    CYCLE_PHASES,
    FEATURE_KINDS,
    FEATURE_PRIORITIES,
    FEATURE_STATUSES,
    SCHEMA_VERSION,
    new_blank_project,
    normalized_cycle,
    normalized_git_state,
    normalized_technical_stack,
    slugify,
    utc_now_iso,
    validate_agent_return,
    validate_bootstrap_audit,
    validate_project_config,
    validate_run_payload,
)
from agent_manager.storage import Store
from agent_manager.ui_helpers import agent_card, copy_open_controls, inject_css, json_download, org_node

ROOT = Path(__file__).resolve().parent
STORE = Store(ROOT)

st.set_page_config(
    page_title="Agent Manager",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

CONTROL_AGENT_IDS = {"startup_agent", "director", "prompt_agent", "companion", "pro_liaison", "pro_advisor"}


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
    with st.sidebar:
        show_new_project_dialog()
        st.divider()
        st.caption("ACTIVE NOW")
        if run:
            cycle = normalized_cycle(run)
            st.caption(f"Cycle {cycle.get('number')} · {cycle.get('phase')}")
            active = cycle.get("active_agents", [])
            for agent_id in active[:6]:
                agent = project.get("agents", {}).get(agent_id, {})
                dispatch = run.get("dispatches", {}).get(agent_id, {})
                status = dispatch.get("status", "ready") if dispatch else "selected"
                st.caption(f"● {agent.get('name', agent_id)} · {status}")
            if not active:
                st.caption("No selected workers")
        else:
            st.caption("No cycle yet — use Start / Resume")

        st.divider()
        page = st.radio(
            "Navigation",
            [
                "Start / Resume",
                "Control Room",
                "Organization",
                "Prompt Studio",
                "Features / Pilot",
                "Cycles",
                "Agents",
                "Import / Returns",
                "Pro Desk",
                "Git & Stack",
                "Project Setup",
                "Settings",
            ],
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("Manual ChatGPT/Codex execution")
        st.caption("No paid OpenAI API calls · no fake completion polling")
        return page


def project_header(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    p = project["project"]
    st.markdown('<div class="am-kicker">Project</div>', unsafe_allow_html=True)
    left, right = st.columns([4, 1])
    with left:
        st.title(p.get("name", ""))
        if p.get("description"):
            st.caption(p["description"])
    with right:
        if run:
            cycle = normalized_cycle(run)
            st.metric("Cycle", f"{cycle.get('number')} · {cycle.get('phase')}")
        else:
            st.metric("Cycle", "—")


def start_resume_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## Start / Resume project")
    st.write(
        "Use this when returning to an existing ChatGPT Project or when Agent Manager does not yet know the real repository/agent state. "
        "The audit chat reconstructs the control plane before a new implementation cycle starts."
    )
    startup = project.get("agents", {}).get("startup_agent", {})
    target_url = startup.get("chat_url") or project.get("project", {}).get("chatgpt_project_url", "")

    prompt_tab, import_tab, contract_tab = st.tabs(["1 · Audit prompt", "2 · Import audit JSON", "3 · Expected contract"])
    with prompt_tab:
        prompt = build_startup_audit_prompt(project)
        st.info("Send this to a knowledgeable chat inside the existing ChatGPT Project. If a dedicated Startup Agent conversation already exists, use it; otherwise use the project/chat that has the best history.")
        copy_open_controls(prompt, target_url, "Copy + Open project/chat")
        st.code(prompt, language=None, wrap_lines=True)

    with import_tab:
        raw = st.text_area("Paste project_bootstrap_audit JSON", height=420, key="bootstrap_audit_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_bootstrap_audit(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            proposed_agents = parsed.get("agent_organization", {}).get("agents", {})
            existing = project.get("agents", {})
            added = sorted(set(proposed_agents) - set(existing))
            retained = sorted(set(proposed_agents) & set(existing))
            features = parsed.get("feature_board", {}).get("features", [])
            next_cycle = parsed.get("next_cycle", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Proposed agents", len(proposed_agents))
            c2.metric("New agent IDs", len(added))
            c3.metric("Feature rows", len(features))
            c4.metric("Next cycle", next_cycle.get("number", "—"))
            st.success("Audit JSON is valid for this project.")
            st.caption(f"Preserved IDs: {', '.join(retained) or 'none'}")
            st.caption(f"New IDs: {', '.join(added) or 'none'}")
            st.markdown("### Audit summary")
            st.write(parsed.get("audit_summary", ""))
            st.markdown("### Technical stack")
            st.json(parsed.get("technical_stack", {}))
            st.markdown("### Next cycle")
            st.json(next_cycle)
            if st.button("Apply startup/resume audit", type="primary"):
                STORE.apply_bootstrap_audit(project, parsed)
                if next_cycle.get("id"):
                    st.session_state.run_id = next_cycle["id"]
                st.success("Project organization, stack, Git state, feature ledger and cycle shell updated.")
                rerun()

    with contract_tab:
        example = startup_audit_schema_example(project)
        st.code(json.dumps(example, indent=2, ensure_ascii=False), language="json")
        json_download("Download startup audit schema", example, f"{project['project']['id']}_startup_audit_schema.json")


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


def features_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    project_id = project["project"]["id"]
    board = STORE.load_feature_board(project_id)
    features = board.get("features", [])
    history = board.get("history", [])
    st.markdown("## Features / Pilot board")
    st.write("Audit owns this durable ledger. Every change can be tied to a cycle/pass so priority, status, bugs, problems and completed work remain traceable instead of being overwritten by the latest conversation.")

    table_tab, history_tab, manual_tab = st.tabs(["Current board", "History", "Manual update"])
    with table_tab:
        priorities = st.multiselect("Priority", FEATURE_PRIORITIES, default=FEATURE_PRIORITIES)
        statuses = st.multiselect("Status", FEATURE_STATUSES, default=FEATURE_STATUSES)
        kinds = st.multiselect("Kind", FEATURE_KINDS, default=FEATURE_KINDS)
        parent_titles = {item.get("id"): item.get("title", item.get("id")) for item in features}
        rows = []
        for item in features:
            if item.get("priority", "P3") not in priorities or item.get("status", "planned") not in statuses or item.get("kind", "feature") not in kinds:
                continue
            parent = parent_titles.get(item.get("parent_id"), "")
            rows.append({
                "ID": item.get("id", ""),
                "Hierarchy": f"{parent} / {item.get('title', '')}" if parent else item.get("title", ""),
                "Area": item.get("area", ""),
                "Kind": item.get("kind", "feature"),
                "Priority": item.get("priority", "P3"),
                "Status": item.get("status", "planned"),
                "Owner": item.get("owner_agent", ""),
                "Last cycle": item.get("cycle_last_changed", ""),
                "Problem / goal": item.get("summary", item.get("problem", "")),
            })
        priority_rank = {p: i for i, p in enumerate(FEATURE_PRIORITIES)}
        rows.sort(key=lambda row: (priority_rank.get(row["Priority"], 99), row["Area"], row["Hierarchy"]))
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No feature rows match the filters. The Startup/Audit agent can seed the board.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Items", len(features))
        c2.metric("Open bugs", sum(1 for f in features if f.get("kind") == "bug" and f.get("status") != "done"))
        c3.metric("Blocked", sum(1 for f in features if f.get("status") == "blocked"))
        c4.metric("Standby", sum(1 for f in features if f.get("status") == "standby"))
        json_download("Download feature board JSON", board, f"{project_id}_feature_board.json")

    with history_tab:
        feature_ids = ["All"] + sorted({h.get("feature_id", "") for h in history if h.get("feature_id")})
        selected_id = st.selectbox("Feature history", feature_ids)
        filtered = [h for h in history if selected_id == "All" or h.get("feature_id") == selected_id]
        filtered = list(reversed(filtered))
        if filtered:
            for event in filtered:
                with st.expander(f"{event.get('cycle_id', '')} · {event.get('feature_id', '')} · {event.get('action', '')} · {event.get('at', '')}"):
                    st.caption(f"Source: {event.get('source_agent', '')}")
                    if event.get("note"):
                        st.write(event["note"])
                    st.json(event.get("changes", {}))
        else:
            st.info("No history yet.")

    with manual_tab:
        st.caption("Manual edits use the same history mechanism as Audit agent updates.")
        existing_ids = [f.get("id", "") for f in features if f.get("id")]
        selected_existing = st.selectbox("Existing item to edit", ["New item"] + existing_ids)
        current = next((f for f in features if f.get("id") == selected_existing), {}) if selected_existing != "New item" else {}
        with st.form("feature_manual"):
            feature_id = st.text_input("Stable ID", value=current.get("id", ""))
            parent_id = st.text_input("Parent ID", value=current.get("parent_id", ""))
            area = st.text_input("Area", value=current.get("area", ""))
            title = st.text_input("Title", value=current.get("title", ""))
            kind = st.selectbox("Kind", FEATURE_KINDS, index=FEATURE_KINDS.index(current.get("kind", "feature")) if current.get("kind", "feature") in FEATURE_KINDS else 0)
            priority = st.selectbox("Priority", FEATURE_PRIORITIES, index=FEATURE_PRIORITIES.index(current.get("priority", "P2")) if current.get("priority", "P2") in FEATURE_PRIORITIES else 2)
            status = st.selectbox("Status", FEATURE_STATUSES, index=FEATURE_STATUSES.index(current.get("status", "planned")) if current.get("status", "planned") in FEATURE_STATUSES else 1)
            owner = st.text_input("Owner agent", value=current.get("owner_agent", ""))
            summary = st.text_area("Problem / goal", value=current.get("summary", current.get("problem", "")), height=100)
            evidence = st.text_area("Evidence / references", value="\n".join(current.get("evidence", [])) if isinstance(current.get("evidence"), list) else str(current.get("evidence", "")), height=80)
            note = st.text_input("History note")
            if st.form_submit_button("Save feature update", type="primary"):
                if not feature_id or not title:
                    st.error("Stable ID and title are required.")
                else:
                    cycle_id = (run or {}).get("run", {}).get("id", "MANUAL")
                    STORE.apply_feature_updates(project_id, [{
                        "feature_id": feature_id,
                        "action": "upsert",
                        "fields": {
                            "parent_id": parent_id,
                            "area": area,
                            "title": title,
                            "kind": kind,
                            "priority": priority,
                            "status": status,
                            "owner_agent": owner,
                            "summary": summary,
                            "evidence": [line.strip() for line in evidence.splitlines() if line.strip()],
                        },
                        "note": note,
                    }], cycle_id, "manual")
                    rerun()


def record_cycle_phase(project: dict[str, Any], run: dict[str, Any], new_phase: str, note: str = "") -> None:
    old = normalized_cycle(run).get("phase", "director_plan")
    run.setdefault("cycle", {})["phase"] = new_phase
    if new_phase == "closed":
        run["cycle"]["status"] = "closed"
        run["cycle"]["completed_at"] = utc_now_iso()
        run.setdefault("run", {})["status"] = "closed"
    run.setdefault("cycle_history", []).append({
        "at": utc_now_iso(),
        "event": "phase_changed",
        "from": old,
        "to": new_phase,
        "note": note,
    })
    STORE.save_run(project["project"]["id"], run)


def cycles_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## Operating cycles")
    st.write("A cycle is the durable unit of work: resume/audit → Director plan → optional Pro advice → Prompt Agent packaging → dispatch/implementation → QA → Audit ledger update → Director consolidation → Lead decision/close.")

    if run:
        cycle = normalized_cycle(run)
        st.markdown("### Current cycle")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Number", cycle.get("number"))
        c2.metric("Phase", cycle.get("phase"))
        c3.metric("Status", cycle.get("status"))
        c4.metric("Workers", len(cycle.get("active_agents", [])))
        st.caption(" → ".join(CYCLE_PHASES))
        phase = cycle.get("phase", "director_plan")
        phase_index = CYCLE_PHASES.index(phase) if phase in CYCLE_PHASES else 0
        b1, b2, b3 = st.columns(3)
        if b1.button("Advance one phase", disabled=phase_index >= len(CYCLE_PHASES) - 1, use_container_width=True):
            record_cycle_phase(project, run, CYCLE_PHASES[min(phase_index + 1, len(CYCLE_PHASES) - 1)])
            rerun()
        if b2.button("Skip optional Pro → Prompt packaging", disabled=phase != "director_plan", use_container_width=True):
            record_cycle_phase(project, run, "prompt_packaging", "Optional Pro advisory skipped.")
            rerun()
        if b3.button("Close cycle", disabled=phase == "closed", use_container_width=True):
            record_cycle_phase(project, run, "closed", "Closed manually from cycle page.")
            rerun()
        with st.expander("Cycle event history"):
            for event in reversed(run.get("cycle_history", [])):
                st.json(event)

    st.markdown("### All cycles")
    runs = STORE.list_runs(project["project"]["id"])
    for item in runs:
        obj = item.get("run", {})
        cycle = normalized_cycle(item)
        with st.expander(f"Cycle {cycle.get('number')} · {obj.get('id')} — {obj.get('title', '')}"):
            st.write(obj.get("objective", ""))
            st.caption(f"Phase {cycle.get('phase')} · status {cycle.get('status')} · dispatches {len(item.get('dispatches', {}))} · returns {len(item.get('returns', {}))}")
            if st.button("Make current", key=f"current_{obj.get('id')}"):
                st.session_state.run_id = obj.get("id")
                rerun()
            json_download("Download cycle JSON", item, f"{obj.get('id')}.json")


def agents_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    agents = project.get("agents", {})
    if not agents:
        st.info("No agents configured. Start with Start / Resume.")
        return
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


def pro_desk_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    desk = project.get("pro_desk", {})
    liaison = project.get("agents", {}).get(desk.get("liaison_agent_id", "pro_liaison"), {})
    pro = project.get("agents", {}).get(desk.get("pro_agent_id", "pro_advisor"), {})
    director = project.get("agents", {}).get(desk.get("director_agent_id", "director"), {})
    st.markdown("## Pro advisory side-channel")
    st.caption("Optional. Pro advice is isolated, then returned to Director for acceptance/rejection/verification before implementation prompts are packaged.")
    a, b, c = st.tabs(["1 · Ask Liaison", "2 · Send to Pro", "3 · Return to Director"])
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


def git_stack_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    git_tab, stack_tab, repos_tab = st.tabs(["Git snapshot", "Technical stack", "Repository inventory"])
    with git_tab:
        git = normalized_git_state(project.get("git_state"))
        st.caption("The Startup/Audit chat can populate verified Git metadata. Manual editing remains available. No GitHub API is required by Agent Manager itself.")
        with st.form("git_snapshot"):
            repo = st.text_input("Primary repository URL", value=git.get("repository_url", ""))
            repo_name = st.text_input("Repository name", value=git.get("repository_name", ""))
            default_branch = st.text_input("Default branch", value=git.get("default_branch", "main"))
            branch = st.text_input("Active branch", value=git.get("active_branch", ""))
            head = st.text_input("HEAD SHA", value=git.get("head_sha", ""))
            last_sha = st.text_input("Last commit SHA", value=git.get("last_commit", {}).get("sha", ""))
            last_msg = st.text_input("Last commit message", value=git.get("last_commit", {}).get("message", ""))
            last_author = st.text_input("Last commit author", value=git.get("last_commit", {}).get("author", ""))
            last_commit_at = st.text_input("Last commit at", value=git.get("last_commit", {}).get("committed_at", ""))
            last_push = st.text_input("Last push at", value=git.get("last_push_at", ""))
            deployment = st.text_input("Deployment URL", value=git.get("deployment_url", ""))
            working_state = st.text_input("Working state", value=git.get("working_state", "unknown"))
            source = st.text_input("Snapshot source", value=git.get("snapshot_source", "manual"))
            recent_json = st.text_area("Recent commits JSON", value=json.dumps(git.get("recent_commits", []), indent=2, ensure_ascii=False), height=130)
            notes = st.text_area("Notes", value=git.get("notes", ""), height=90)
            if st.form_submit_button("Save Git snapshot", type="primary"):
                try:
                    recent_commits = json.loads(recent_json) if recent_json.strip() else []
                    if not isinstance(recent_commits, list):
                        raise ValueError("Recent commits must be a JSON list.")
                except Exception as exc:
                    st.error(str(exc))
                else:
                    project["git_state"] = {
                        **git,
                        "repository_url": repo,
                        "repository_name": repo_name,
                        "default_branch": default_branch,
                        "active_branch": branch,
                        "head_sha": head,
                        "last_commit": {"sha": last_sha, "message": last_msg, "author": last_author, "committed_at": last_commit_at},
                        "last_push_at": last_push,
                        "deployment_url": deployment,
                        "working_state": working_state,
                        "snapshot_source": source,
                        "snapshot_at": utc_now_iso(),
                        "recent_commits": recent_commits,
                        "notes": notes,
                    }
                    STORE.save_project(project)
                    rerun()
        st.markdown("#### Prompt metadata preview")
        preview_agent = next(iter(project.get("agents", {}).values()), {})
        st.code(metadata_block(project, preview_agent, run), language=None)

    with stack_tab:
        stack = normalized_technical_stack(project.get("technical_stack"))
        with st.form("technical_stack"):
            languages = st.text_input("Languages", value=", ".join(stack.get("languages", [])))
            frameworks = st.text_input("Frameworks", value=", ".join(stack.get("frameworks", [])))
            sdks = st.text_input("SDKs / libraries", value=", ".join(stack.get("sdks", [])))
            runtimes = st.text_input("Runtimes", value=", ".join(stack.get("runtimes", [])))
            package_managers = st.text_input("Package managers", value=", ".join(stack.get("package_managers", [])))
            build_tools = st.text_input("Build tools", value=", ".join(stack.get("build_tools", [])))
            test_tools = st.text_input("Test tools", value=", ".join(stack.get("test_tools", [])))
            datastores = st.text_input("Datastores", value=", ".join(stack.get("datastores", [])))
            cloud_platforms = st.text_input("Cloud platforms", value=", ".join(stack.get("cloud_platforms", [])))
            deployment_targets = st.text_input("Deployment targets", value=", ".join(stack.get("deployment_targets", [])))
            developer_tools = st.text_input("Developer tools", value=", ".join(stack.get("developer_tools", [])))
            stack_notes = st.text_area("Stack notes", value=stack.get("notes", ""), height=90)
            if st.form_submit_button("Save technical stack", type="primary"):
                project["technical_stack"] = {
                    "languages": csv_list(languages),
                    "frameworks": csv_list(frameworks),
                    "sdks": csv_list(sdks),
                    "runtimes": csv_list(runtimes),
                    "package_managers": csv_list(package_managers),
                    "build_tools": csv_list(build_tools),
                    "test_tools": csv_list(test_tools),
                    "datastores": csv_list(datastores),
                    "cloud_platforms": csv_list(cloud_platforms),
                    "deployment_targets": csv_list(deployment_targets),
                    "developer_tools": csv_list(developer_tools),
                    "notes": stack_notes,
                }
                STORE.save_project(project)
                rerun()

    with repos_tab:
        repos = project.get("repositories", [])
        if repos:
            st.dataframe(repos, use_container_width=True, hide_index=True)
        else:
            st.info("No repository inventory yet. Startup/Resume Audit can populate it.")
        st.caption("Primary-repo metadata lives in Git snapshot and is prepended to prompts. This inventory records additional consumer/library/tool repositories without pretending the app can query them automatically.")


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


project = select_project()
run = select_run(project)
page = sidebar_navigation(project, run)

if page == "Start / Resume":
    start_resume_page(project, run)
elif page == "Control Room":
    control_room_page(project, run)
elif page == "Organization":
    organization_page(project, run)
elif page == "Prompt Studio":
    prompt_studio_page(project, run)
elif page == "Features / Pilot":
    features_page(project, run)
elif page == "Cycles":
    cycles_page(project, run)
elif page == "Agents":
    agents_page(project, run)
elif page == "Import / Returns":
    import_returns_page(project, run)
elif page == "Pro Desk":
    pro_desk_page(project, run)
elif page == "Git & Stack":
    git_stack_page(project, run)
elif page == "Project Setup":
    project_setup_page(project, run)
elif page == "Settings":
    settings_page(project, run)
