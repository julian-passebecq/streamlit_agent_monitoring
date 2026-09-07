from pathlib import Path
import json

from agent_manager.schema import validate_project_config, validate_run_payload

ROOT = Path(__file__).resolve().parents[1]


def project():
    return json.loads((ROOT / "data/projects/datapass-v4.json").read_text(encoding="utf-8"))


def run():
    return json.loads((ROOT / "data/runs/datapass-v4/DPV4-001.json").read_text(encoding="utf-8"))


def test_default_project_valid():
    assert validate_project_config(project()) == []


def test_default_run_valid():
    assert validate_run_payload(run(), project()) == []


def test_run_rejects_unknown_agent():
    payload = run()
    payload["dispatches"]["ghost"] = {"prompt": "x", "status": "ready"}
    errors = validate_run_payload(payload, project())
    assert any("Unknown dispatch agent" in e for e in errors)
