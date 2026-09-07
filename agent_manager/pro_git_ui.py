from __future__ import annotations

import json
from typing import Any

import streamlit as st

from .packets import build_liaison_request, build_pro_director_return, metadata_block
from .schema import normalized_git_state, normalized_technical_stack, utc_now_iso
from .ui_common import STORE, csv_list, project_header, rerun
from .ui_helpers import copy_open_controls, json_download

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


