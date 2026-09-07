from pathlib import Path
import json

from agent_manager.schema import (
    validate_bootstrap_audit,
    validate_project_config,
    validate_run_payload,
)

ROOT = Path(__file__).resolve().parents[1]


def project():
    return json.loads((ROOT / "data/projects/datapass-v4.json").read_text(encoding="utf-8"))


def run():
    return json.loads((ROOT / "data/runs/datapass-v4/DPV4-001.json").read_text(encoding="utf-8"))


def bootstrap_audit():
    p = project()
    return {
        "schema_version": "1.0",
        "type": "project_bootstrap_audit",
        "project_id": "datapass-v4",
        "technical_stack": p["technical_stack"],
        "git_state": p["git_state"],
        "agent_organization": {
            "rationale": "test",
            "replace_agents": False,
            "agents": {
                "director": p["agents"]["director"],
                "prompt_agent": p["agents"]["prompt_agent"],
            },
            "relationships": [],
        },
        "feature_board": {"features": [], "history": []},
        "next_cycle": {
            "id": "DPV4-002",
            "number": 2,
            "title": "Next",
            "objective": "Resume",
            "phase": "director_plan",
            "active_agents": [],
            "standby_agents": [],
        },
    }


def test_default_project_valid():
    assert validate_project_config(project()) == []


def test_default_run_valid():
    assert validate_run_payload(run(), project()) == []


def test_run_rejects_unknown_agent():
    payload = run()
    payload["dispatches"]["ghost"] = {"prompt": "x", "status": "ready"}
    errors = validate_run_payload(payload, project())
    assert any("Unknown dispatch agent" in e for e in errors)


def test_bootstrap_audit_valid():
    assert validate_bootstrap_audit(bootstrap_audit(), project()) == []


def test_bootstrap_audit_requires_agent_role_contracts():
    payload = bootstrap_audit()
    payload["agent_organization"]["agents"]["director"]["custom_instructions"] = ""
    errors = validate_bootstrap_audit(payload, project())
    assert any("custom_instructions" in e for e in errors)
