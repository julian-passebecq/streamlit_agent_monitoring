from __future__ import annotations

import streamlit as st

from agent_manager.control_ui import control_room_page, organization_page, prompt_studio_page
from agent_manager.planning_ui import cycles_page, features_page
from agent_manager.agent_return_ui import agents_page, import_returns_page
from agent_manager.pro_git_ui import git_stack_page, pro_desk_page
from agent_manager.project_ui import project_setup_page, settings_page
from agent_manager.setup_map_ui import app_deep_audit_page, project_map_page
from agent_manager.setup_director_ui import (
    agent_setup_wizard_page,
    archive_page,
    director_feature_plan_setup_page,
    director_organization_setup_page,
)
from agent_manager.ui_common import select_project, select_run, sidebar_navigation
from agent_manager.ui_helpers import inject_css

st.set_page_config(
    page_title="Agent Manager",
    page_icon="◎",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

project = select_project()
run = select_run(project)
page = sidebar_navigation(project, run)

if page == "1 · Project Map":
    project_map_page(project, run)
elif page == "2 · App Deep Audit":
    app_deep_audit_page(project, run)
elif page == "3 · Director / Organization":
    director_organization_setup_page(project, run)
elif page == "4 · Features / Plan":
    director_feature_plan_setup_page(project, run)
elif page == "5 · Agent Setup":
    agent_setup_wizard_page(project, run)
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
elif page == "Import / Returns":
    import_returns_page(project, run)
elif page == "Pro Desk":
    pro_desk_page(project, run)
elif page == "Git & Stack":
    git_stack_page(project, run)
elif page == "Archive":
    archive_page(project, run)
elif page == "Project Setup":
    project_setup_page(project, run)
elif page == "Settings":
    settings_page(project, run)
elif page.startswith("Agent::"):
    agents_page(project, run, page.split("::", 1)[1])
else:
    project_map_page(project, run)
