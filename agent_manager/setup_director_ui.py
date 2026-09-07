from __future__ import annotations

import json
from typing import Any

import streamlit as st

from .organization_packets import (
    agent_bootstrap_pack_schema_example,
    build_agent_bootstrap_pack_prompt,
    build_director_feature_plan_prompt,
    build_director_organization_prompt,
    director_feature_plan_schema_example,
    director_organization_schema_example,
)
from .packets import bootstrap_packet, prompt_agent_bootstrap
from .schema import (
    validate_agent_bootstrap_pack,
    validate_director_feature_plan,
    validate_director_organization_plan,
)
from .ui_common import ROOT, STORE, project_header, rerun
from .ui_helpers import copy_open_controls, json_download
from .setup_map_ui import onboarding_stage, setup_progress

def director_organization_setup_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    setup_progress(project, 3)
    st.markdown("## 3 · Director designs the organization")
    onboarding = project.setdefault("onboarding", {})
    if not onboarding.get("selected_app_audit"):
        st.warning("Complete 2 · App Deep Audit first.")
        return

    current_director = project.get("agents", {}).get("director", {})
    with st.form("director_setup_link"):
        director_url = st.text_input("Director chat URL", value=current_director.get("chat_url") or onboarding.get("director_chat_url", ""))
        director_model = st.text_input("Actual Director model label", value=current_director.get("model_label") or onboarding.get("director_model_label", "GPT-5.6 Sol / High"))
        if st.form_submit_button("Save Director chat"):
            onboarding["director_chat_url"] = director_url
            onboarding["director_model_label"] = director_model
            if "director" in project.get("agents", {}):
                project["agents"]["director"]["chat_url"] = director_url
                project["agents"]["director"]["model_label"] = director_model
            STORE.save_project(project)
            rerun()

    prompt_tab, import_tab, graph_tab = st.tabs(["Prompt 3", "Import Director JSON", "Organization preview"])
    with prompt_tab:
        packet = build_director_organization_prompt(project)
        st.write("Create a new Director chat for this app if one does not already exist. This can be its first message.")
        copy_open_controls(packet, director_url or onboarding.get("director_chat_url", ""), "Copy + Open Director")
        st.code(packet, language=None, wrap_lines=True)

    with import_tab:
        raw = st.text_area("Paste director_organization_plan JSON", height=430, key="director_org_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_director_organization_plan(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            agents = parsed.get("organization", {}).get("agents", {})
            st.success(f"Valid organization plan with {len(agents)} agents.")
            st.caption(parsed.get("organization", {}).get("rationale", ""))
            if st.button("Apply Director organization", type="primary"):
                director_cfg = parsed.get("organization", {}).get("agents", {}).get("director")
                if isinstance(director_cfg, dict):
                    if director_url:
                        director_cfg["chat_url"] = director_url
                    if director_model:
                        director_cfg["model_label"] = director_model
                STORE.apply_director_organization_plan(project, parsed)
                st.session_state.nav_page = "4 · Features / Plan"
                rerun()
        with st.expander("Expected JSON contract"):
            st.code(json.dumps(director_organization_schema_example(project), indent=2, ensure_ascii=False), language="json")

    with graph_tab:
        plan = onboarding.get("director_organization_plan", {})
        org = plan.get("organization", {})
        agents = org.get("agents", {})
        if not agents:
            st.info("Import Prompt 3's Director answer first.")
        else:
            st.markdown("### Agents")
            for aid, agent in agents.items():
                st.write(f"- **{agent.get('name', aid)}** · {agent.get('role', '')} · `{agent.get('model_label', '')}`")
            st.markdown("### Handoffs")
            st.dataframe(org.get("relationships", []), use_container_width=True, hide_index=True)


def director_feature_plan_setup_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    setup_progress(project, 4)
    st.markdown("## 4 · Director creates feature board and plan")
    onboarding = project.setdefault("onboarding", {})
    if not onboarding.get("director_organization_plan"):
        st.warning("Complete 3 · Director / Organization first.")
        return
    director = project.get("agents", {}).get("director", {})

    prompt_tab, import_tab, preview_tab = st.tabs(["Prompt 4", "Import planning JSON", "Plan preview"])
    with prompt_tab:
        packet = build_director_feature_plan_prompt(project)
        st.write("Send this to the same Director chat. It creates the durable hierarchical feature ledger plus a concrete first cycle.")
        copy_open_controls(packet, director.get("chat_url", ""), "Copy + Open Director")
        st.code(packet, language=None, wrap_lines=True)

    with import_tab:
        raw = st.text_area("Paste director_feature_plan JSON", height=430, key="director_feature_plan_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_director_feature_plan(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            features = parsed.get("feature_board", {}).get("features", [])
            next_cycle = parsed.get("next_cycle", {})
            c1, c2, c3 = st.columns(3)
            c1.metric("Feature rows", len(features))
            c2.metric("Milestones", len(parsed.get("milestones", [])))
            c3.metric("Next cycle", next_cycle.get("number", "—"))
            st.success("Planning JSON is valid. Applying it initializes the feature/history ledger and next cycle shell.")
            if st.button("Apply feature board + plan", type="primary"):
                STORE.apply_director_feature_plan(project, parsed)
                if next_cycle.get("id"):
                    st.session_state.run_id = next_cycle["id"]
                st.session_state.nav_page = "5 · Agent Setup"
                rerun()
        with st.expander("Expected JSON contract"):
            st.code(json.dumps(director_feature_plan_schema_example(project), indent=2, ensure_ascii=False), language="json")

    with preview_tab:
        plan = onboarding.get("director_feature_plan", {})
        if not plan:
            st.info("Import Prompt 4's Director answer first.")
        else:
            st.markdown("### Next cycle")
            st.json(plan.get("next_cycle", {}))
            st.markdown("### Future-cycle outline")
            st.dataframe(plan.get("future_cycles", []), use_container_width=True, hide_index=True)


def agent_setup_wizard_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    setup_progress(project, 5)
    st.markdown("## 5 · Finalize agent instructions and link conversations")
    onboarding = project.setdefault("onboarding", {})
    if not onboarding.get("director_feature_plan"):
        st.warning("Complete 4 · Features / Plan first.")
        return
    prompt_agent = project.get("agents", {}).get("prompt_agent")
    if not prompt_agent:
        st.error("The Director organization does not contain a Prompt Agent. Return to step 3 and fix the organization before final bootstrap.")
        return

    st.markdown("### A · Create/link Prompt Agent first")
    with st.form("prompt_agent_link_setup"):
        prompt_url = st.text_input("Prompt Agent chat URL", value=prompt_agent.get("chat_url", ""))
        prompt_model = st.text_input("Actual Prompt Agent model label", value=prompt_agent.get("model_label", ""))
        if st.form_submit_button("Save Prompt Agent chat"):
            prompt_agent["chat_url"] = prompt_url
            prompt_agent["model_label"] = prompt_model
            STORE.save_project(project)
            rerun()
    initial_prompt_bootstrap = prompt_agent_bootstrap(project)
    copy_open_controls(initial_prompt_bootstrap, prompt_agent.get("chat_url", ""), "Copy bootstrap + Open Prompt Agent")

    st.markdown("### B · Ask Prompt Agent to finalize every stable role contract")
    packet = build_agent_bootstrap_pack_prompt(project)
    copy_open_controls(packet, prompt_agent.get("chat_url", ""), "Copy Prompt 5 + Open Prompt Agent")
    with st.expander("Prompt 5 preview"):
        st.code(packet, language=None, wrap_lines=True)

    raw = st.text_area("Paste agent_bootstrap_pack JSON", height=400, key="bootstrap_pack_import")
    parsed = None
    errors: list[str] = []
    if raw.strip():
        try:
            parsed = json.loads(raw)
            errors = validate_agent_bootstrap_pack(parsed, project)
        except json.JSONDecodeError as exc:
            errors = [f"Invalid JSON: {exc}"]
    if errors:
        for error in errors:
            st.error(error)
    elif parsed:
        st.success(f"Valid bootstrap pack for {len(parsed.get('agents', {}))} agents.")
        if st.button("Apply final role instructions", type="primary"):
            STORE.apply_agent_bootstrap_pack(project, parsed)
            rerun()

    with st.expander("Expected JSON contract"):
        st.code(json.dumps(agent_bootstrap_pack_schema_example(project), indent=2, ensure_ascii=False), language="json")

    st.markdown("### C · Create/link the actual agent conversations")
    st.caption("Chat links are human-entered. Agent Manager never invents them. After saving, every agent gets its own page in the left sidebar.")
    agents = project.get("agents", {})
    if not agents:
        st.info("No agents are configured yet.")
        return
    with st.form("all_agent_links"):
        updates: dict[str, tuple[str, str]] = {}
        for aid, agent in agents.items():
            st.markdown(f"**{agent.get('name', aid)}** · {agent.get('role', '')}")
            c1, c2 = st.columns([3, 2])
            url = c1.text_input("Conversation URL", value=agent.get("chat_url", ""), key=f"setup_link_{aid}", label_visibility="collapsed", placeholder="https://chatgpt.com/c/...")
            model = c2.text_input("Model", value=agent.get("model_label", ""), key=f"setup_model_{aid}", label_visibility="collapsed")
            updates[aid] = (url, model)
        if st.form_submit_button("Save all conversation links / model labels", type="primary"):
            for aid, (url, model) in updates.items():
                project["agents"][aid]["chat_url"] = url
                project["agents"][aid]["model_label"] = model
            STORE.save_project(project)
            rerun()

    linked = sum(1 for agent in agents.values() if agent.get("chat_url"))
    st.metric("Linked conversations", f"{linked} / {len(agents)}")
    if onboarding_stage(project) == "ready":
        st.success("Five-step setup is structurally complete. Use the agent pages on the left to send bootstraps, then move to Control Room / Prompt Studio for operating cycles.")


def archive_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    st.markdown("## Archive / evidence bundle")
    st.write(
        "Do not pollute the implementation repo with every audit dump. Agent Manager keeps setup artifacts separately and can export one archive ZIP containing setup outputs, feature history and cycle JSON."
    )
    archive = project.setdefault("archive", {})
    with st.form("archive_settings"):
        repo_url = st.text_input("Optional archive repository URL", value=archive.get("repository_url", ""), help="If you want Git history, prefer one central private archive repo rather than a new dump repo per app.")
        notes = st.text_area("Archive notes", value=archive.get("notes", ""), height=90)
        if st.form_submit_button("Save archive settings"):
            archive.update({"repository_url": repo_url, "notes": notes})
            STORE.save_project(project)
            rerun()
    include_urls = st.checkbox("Include ChatGPT conversation URLs in export", value=False, help="Off by default because chat URLs may be sensitive, especially if your archive repo is public.")
    bundle = STORE.build_archive_zip(project, include_chat_urls=include_urls)
    st.download_button(
        "Download project archive ZIP",
        data=bundle,
        file_name=f"{project['project']['id']}_agent_manager_archive.zip",
        mime="application/zip",
        use_container_width=True,
    )
    artifacts = STORE.list_setup_artifacts(project["project"]["id"])
    st.caption(f"Stored setup artifacts: {len(artifacts)}")
    for path in artifacts[:20]:
        st.code(str(path.relative_to(ROOT)), language=None)
