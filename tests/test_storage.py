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
