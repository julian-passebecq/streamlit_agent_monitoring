from pathlib import Path
import json

from agent_manager.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def seed_project():
    return json.loads((ROOT / "data/projects/datapass-v4.json").read_text(encoding="utf-8"))


def test_feature_updates_append_history(tmp_path):
    store = Store(tmp_path)
    board = store.apply_feature_updates(
        "demo",
        [{
            "feature_id": "F-1",
            "action": "upsert",
            "fields": {"title": "Feature", "kind": "feature", "priority": "P1", "status": "planned"},
            "note": "seed",
        }],
        "CYCLE-1",
        "audit",
    )
    assert board["features"][0]["id"] == "F-1"
    assert board["history"][0]["cycle_id"] == "CYCLE-1"
    assert board["history"][0]["source_agent"] == "audit"


def test_bootstrap_audit_preserves_existing_chat_url(tmp_path):
    store = Store(tmp_path)
    project = seed_project()
    project["agents"]["director"]["chat_url"] = "https://chatgpt.com/c/existing"
    store.save_project(project)
    audit = {
        "schema_version": "1.0",
        "type": "project_bootstrap_audit",
        "project_id": "datapass-v4",
        "audited_at": "2026-09-07T00:00:00Z",
        "audit_summary": "resume",
        "technical_stack": project["technical_stack"],
        "repositories": project.get("repositories", []),
        "git_state": project["git_state"],
        "current_state": {},
        "agent_organization": {
            "rationale": "keep IDs",
            "replace_agents": False,
            "agents": {
                "director": {
                    **project["agents"]["director"],
                    "custom_instructions": "updated role",
                }
            },
            "relationships": [],
        },
        "feature_board": {"schema_version": "1.0", "type": "feature_board", "project_id": "datapass-v4", "features": [], "history": []},
        "next_cycle": {
            "id": "CYCLE-2",
            "number": 2,
            "title": "Next",
            "objective": "Resume",
            "phase": "director_plan",
            "active_agents": [],
            "standby_agents": [],
        },
    }
    store.apply_bootstrap_audit(project, audit)
    saved = store.load_project("datapass-v4")
    assert saved["agents"]["director"]["chat_url"] == "https://chatgpt.com/c/existing"
    assert saved["agents"]["director"]["custom_instructions"] == "updated role"
    shell = store.load_run("datapass-v4", "CYCLE-2")
    assert shell["cycle"]["number"] == 2


def test_five_step_setup_artifacts_and_archive(tmp_path):
    from agent_manager.project_mapping_packets import (
        project_map_schema_example,
        selected_app_audit_schema_example,
    )
    from agent_manager.organization_packets import (
        agent_bootstrap_pack_schema_example,
        director_feature_plan_schema_example,
        director_organization_schema_example,
    )

    store = Store(tmp_path)
    p = seed_project()
    p["project"]["id"] = "demo"
    p["project"]["name"] = "Demo manager"
    p.setdefault("onboarding", {})["chatgpt_project_name"] = "Umbrella Project"
    store.save_project(p)

    mapped = project_map_schema_example(p)
    mapped["manager_project_id"] = "demo"
    mapped["apps"][0]["id"] = "app-a"
    mapped["apps"][0]["name"] = "App A"
    store.apply_project_map(p, mapped)
    store.select_mapped_app(p, "app-a")
    p = store.load_project("demo")
    assert p["onboarding"]["selected_app_id"] == "app-a"

    audit = selected_app_audit_schema_example(p)
    audit["project_id"] = "demo"
    audit["selected_app_id"] = "app-a"
    audit["identity"]["name"] = "App A"
    store.apply_selected_app_audit(p, audit)
    p = store.load_project("demo")
    assert p["onboarding"]["stage"] == "director_organization"

    org = director_organization_schema_example(p)
    org["project_id"] = "demo"
    org["selected_app_id"] = "app-a"
    store.apply_director_organization_plan(p, org)
    p = store.load_project("demo")

    plan = director_feature_plan_schema_example(p)
    plan["project_id"] = "demo"
    plan["selected_app_id"] = "app-a"
    plan["next_cycle"]["id"] = "DEMO-C1"
    plan["next_cycle"]["title"] = "First cycle"
    plan["next_cycle"]["objective"] = "Resume safely"
    store.apply_director_feature_plan(p, plan)
    p = store.load_project("demo")

    pack = agent_bootstrap_pack_schema_example(p)
    pack["project_id"] = "demo"
    pack["selected_app_id"] = "app-a"
    store.apply_agent_bootstrap_pack(p, pack)
    p = store.load_project("demo")
    assert p["onboarding"]["stage"] == "ready"
    assert len(store.list_setup_artifacts("demo")) == 5

    archive = store.build_archive_zip(p, include_chat_urls=False)
    assert archive[:2] == b"PK"
