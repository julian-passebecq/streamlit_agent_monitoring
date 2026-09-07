from __future__ import annotations

from copy import deepcopy
from typing import Any

import streamlit as st

from .schema import CYCLE_PHASES, FEATURE_KINDS, FEATURE_PRIORITIES, FEATURE_STATUSES, normalized_cycle, utc_now_iso
from .ui_common import STORE, project_header, rerun
from .ui_helpers import json_download

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
