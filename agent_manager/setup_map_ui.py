from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import streamlit as st

from .project_mapping_packets import (
    build_project_map_prompt,
    build_selected_app_audit_prompt,
    project_map_schema_example,
    selected_app_audit_schema_example,
)
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
    normalized_git_state,
    normalized_technical_stack,
    new_blank_project,
    slugify,
    validate_agent_bootstrap_pack,
    validate_director_feature_plan,
    validate_director_organization_plan,
    validate_project_map,
    validate_selected_app_audit,
)
from .ui_common import ROOT, STORE, project_header, projects_index, rerun
from .ui_helpers import copy_open_controls, json_download

def onboarding_stage(project: dict[str, Any]) -> str:
    return project.get("onboarding", {}).get("stage", "project_map")


def setup_progress(project: dict[str, Any], current: int) -> None:
    labels = ["Project map", "Deep audit", "Organization", "Features / plan", "Agent setup"]
    cols = st.columns(5)
    for idx, (col, label) in enumerate(zip(cols, labels), start=1):
        with col:
            marker = "✓" if idx < current else ("●" if idx == current else "○")
            st.caption(f"{marker} {idx}. {label}")


def selected_map_app(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = project.get("onboarding", {})
    selected_id = onboarding.get("selected_app_id", "")
    for app in onboarding.get("project_map", {}).get("apps", []):
        if app.get("id") == selected_id:
            return app
    return onboarding.get("selected_app", {}) or {}


def create_project_from_mapped_app(project: dict[str, Any], app: dict[str, Any]) -> str:
    requested = slugify(app.get("id") or app.get("name") or "managed-app")
    existing = projects_index()
    project_id = requested
    counter = 2
    while project_id in existing:
        project_id = f"{requested}-{counter}"
        counter += 1
    new_project = new_blank_project(project_id, app.get("name") or project_id)
    parent = project.get("onboarding", {})
    new_project["onboarding"].update({
        "chatgpt_project_name": parent.get("chatgpt_project_name", ""),
        "chatgpt_project_url": parent.get("chatgpt_project_url", ""),
        "setup_chat_url": parent.get("setup_chat_url", ""),
        "setup_model_label": parent.get("setup_model_label", "GPT-5.6 Sol / High"),
        "project_map": deepcopy(parent.get("project_map", {})),
        "selected_app_id": app.get("id", ""),
        "selected_app": deepcopy(app),
        "stage": "selected_app_audit",
    })
    new_project["project"]["description"] = app.get("purpose", "")
    repos = app.get("repositories", [])
    if repos and isinstance(repos[0], dict):
        url = repos[0].get("url", "")
        new_project["project"]["repository_url"] = url
        new_project["git_state"]["repository_url"] = url
    STORE.save_project(new_project)
    return project_id


def project_map_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    setup_progress(project, 1)
    st.markdown("## 1 · Map the whole ChatGPT Project")
    st.write(
        "Start one dedicated **Streamlit Setup / Project Mapper** chat inside the ChatGPT Project. "
        "Its first job is not to resume implementation: it maps every distinct app, framework, consumer, tool and repo so you can choose what you are actually working on."
    )

    onboarding = project.setdefault("onboarding", {})
    with st.form("project_map_context"):
        project_name = st.text_input(
            "ChatGPT Project name",
            value=onboarding.get("chatgpt_project_name") or project.get("project", {}).get("name", ""),
        )
        project_url = st.text_input(
            "ChatGPT Project URL",
            value=onboarding.get("chatgpt_project_url") or project.get("project", {}).get("chatgpt_project_url", ""),
            help="Optional. Store the Project link so you can get back to it quickly.",
        )
        setup_chat_url = st.text_input(
            "Streamlit Setup Agent chat URL",
            value=onboarding.get("setup_chat_url", ""),
            help="Create one new chat in the ChatGPT Project and paste its chatgpt.com/c/... link here.",
        )
        setup_model = st.text_input(
            "Setup Agent model label",
            value=onboarding.get("setup_model_label", "GPT-5.6 Sol / High"),
            help="Metadata only: record the model/mode you actually selected.",
        )
        if st.form_submit_button("Save setup chat", type="primary"):
            onboarding.update({
                "chatgpt_project_name": project_name,
                "chatgpt_project_url": project_url,
                "setup_chat_url": setup_chat_url,
                "setup_model_label": setup_model,
            })
            project["project"]["chatgpt_project_url"] = project_url
            STORE.save_project(project)
            rerun()

    prompt, import_tab, map_tab = st.tabs(["Prompt 1", "Import structured answer", "Project ramifications"])
    with prompt:
        packet = build_project_map_prompt(project)
        st.info("Paste this as the first message in the dedicated Setup Agent chat. Its first answer should be JSON only.")
        copy_open_controls(packet, onboarding.get("setup_chat_url") or onboarding.get("chatgpt_project_url", ""), "Copy + Open Setup Agent")
        st.code(packet, language=None, wrap_lines=True)

    with import_tab:
        raw = st.text_area("Paste chatgpt_project_map JSON", height=430, key="project_map_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_project_map(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            apps = parsed.get("apps", [])
            active = sum(1 for app in apps if app.get("status") == "active")
            paused = sum(1 for app in apps if app.get("status") == "paused")
            c1, c2, c3 = st.columns(3)
            c1.metric("Apps / subprojects", len(apps))
            c2.metric("Active", active)
            c3.metric("Paused", paused)
            st.success("Project map is valid. Apply it, then select the exact app you want to resume.")
            if st.button("Apply project map", type="primary"):
                STORE.apply_project_map(project, parsed)
                rerun()
        with st.expander("Expected JSON contract"):
            st.code(json.dumps(project_map_schema_example(project), indent=2, ensure_ascii=False), language="json")

    with map_tab:
        project_map = project.get("onboarding", {}).get("project_map", {})
        apps = project_map.get("apps", [])
        if not apps:
            st.info("Import Prompt 1's structured answer first.")
        else:
            selected_id = project.get("onboarding", {}).get("selected_app_id", "")
            for app in apps:
                with st.container(border=True):
                    top1, top2, top3 = st.columns([4, 1, 1])
                    top1.markdown(f"### {app.get('name', app.get('id', ''))}")
                    top1.caption(f"{app.get('kind', 'app')} · {app.get('status', 'unknown')} · confidence {app.get('confidence', 'unknown')}")
                    top2.metric("Repos", len(app.get("repositories", [])))
                    top3.metric("Chats", len(app.get("conversations", [])))
                    if app.get("purpose"):
                        st.write(app["purpose"])
                    current = app.get("current_work", {})
                    if current.get("summary"):
                        st.caption(f"Current: {current.get('summary')} · {current.get('status', '')}")
                    repo_urls = [repo.get("url", "") for repo in app.get("repositories", []) if isinstance(repo, dict) and repo.get("url")]
                    if repo_urls:
                        st.code("\n".join(repo_urls), language=None)
                    b1, b2 = st.columns(2)
                    label = "Selected ✓" if app.get("id") == selected_id else "Select this app"
                    if b1.button(label, key=f"select_map_{app.get('id')}", disabled=app.get("id") == selected_id, use_container_width=True):
                        STORE.select_mapped_app(project, app.get("id", ""))
                        st.session_state.nav_page = "2 · App Deep Audit"
                        rerun()
                    if b2.button("Create separate managed project", key=f"create_map_{app.get('id')}", use_container_width=True):
                        new_id = create_project_from_mapped_app(project, app)
                        st.session_state.project_id = new_id
                        st.session_state.nav_page = "2 · App Deep Audit"
                        st.session_state.pop("run_id", None)
                        rerun()


def app_deep_audit_page(project: dict[str, Any], run: dict[str, Any] | None) -> None:
    project_header(project, run)
    setup_progress(project, 2)
    st.markdown("## 2 · Deep audit the selected app")
    selected = selected_map_app(project)
    if not selected:
        st.warning("No app selected. Go back to 1 · Project Map and choose one app/subproject first.")
        return
    st.info(f"Selected: **{selected.get('name', selected.get('id', ''))}** · {selected.get('status', 'unknown')}")
    onboarding = project.setdefault("onboarding", {})

    prompt_tab, import_tab, evidence_tab = st.tabs(["Prompt 2", "Import structured answer", "Audit evidence"])
    with prompt_tab:
        packet = build_selected_app_audit_prompt(project)
        st.write("Send this as the **second message to the same Setup Agent chat**. It now audits only the selected app in depth.")
        copy_open_controls(packet, onboarding.get("setup_chat_url", ""), "Copy + Open Setup Agent")
        st.code(packet, language=None, wrap_lines=True)

    with import_tab:
        raw = st.text_area("Paste selected_app_audit JSON", height=430, key="selected_app_audit_import")
        parsed = None
        errors: list[str] = []
        if raw.strip():
            try:
                parsed = json.loads(raw)
                errors = validate_selected_app_audit(parsed, project)
            except json.JSONDecodeError as exc:
                errors = [f"Invalid JSON: {exc}"]
        if errors:
            for error in errors:
                st.error(error)
        elif parsed:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Repositories", len(parsed.get("repositories", [])))
            c2.metric("Known chats", len(parsed.get("chat_inventory", [])))
            c3.metric("Languages", len(parsed.get("technical_stack", {}).get("languages", [])))
            c4.metric("Open questions", len(parsed.get("current_state", {}).get("open_questions", [])))
            st.success("Deep audit JSON is valid. This initializes Git/stack/chat history, but does not yet decide the future agent organization.")
            if st.button("Apply deep audit", type="primary"):
                STORE.apply_selected_app_audit(project, parsed)
                st.session_state.nav_page = "3 · Director / Organization"
                rerun()
        with st.expander("Expected JSON contract"):
            st.code(json.dumps(selected_app_audit_schema_example(project), indent=2, ensure_ascii=False), language="json")

    with evidence_tab:
        audit = onboarding.get("selected_app_audit", {})
        if not audit:
            st.info("Import Prompt 2's structured answer first.")
        else:
            st.markdown("### Repositories")
            st.dataframe(audit.get("repositories", []), use_container_width=True, hide_index=True)
            st.markdown("### Chat / agent history")
            st.dataframe(audit.get("chat_inventory", []), use_container_width=True, hide_index=True)
            st.markdown("### Mermaid sources")
            for name, mermaid in audit.get("mermaid", {}).items():
                with st.expander(name.replace("_", " ").title()):
                    st.code(mermaid, language="mermaid")


