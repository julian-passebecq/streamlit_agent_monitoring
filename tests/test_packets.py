from pathlib import Path
import json

from agent_manager.packets import (
    bootstrap_packet,
    build_liaison_request,
    build_pro_director_return,
    companion_run_schema_example,
    dispatch_packet,
)

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_dispatch_contains_model_and_git_metadata():
    project = load("data/projects/datapass-v4.json")
    run = load("data/runs/datapass-v4/DPV4-001.json")
    packet = dispatch_packet(project, run, "code_agent_a")
    assert 'model_label: "Codex"' in packet
    assert 'head_sha: "ce8353ee0878ca74b2fe24a1af7de657a6ba61f2"' in packet
    assert "Example bounded implementation task" in packet


def test_bootstrap_contains_shared_and_agent_instructions():
    project = load("data/projects/datapass-v4.json")
    packet = bootstrap_packet(project, project["agents"]["qa"])
    assert "Shared project instructions" in packet
    assert "Verify the Director-defined acceptance criteria" in packet


def test_companion_schema_uses_known_agents_only():
    project = load("data/projects/datapass-v4.json")
    example = companion_run_schema_example(project)
    assert set(example["dispatches"]).issubset(project["agents"])
    assert "companion" not in example["dispatches"]


def test_pro_workflow_packets_are_advisory():
    project = load("data/projects/datapass-v4.json")
    run = load("data/runs/datapass-v4/DPV4-001.json")
    request = build_liaison_request(project, run)
    returned = build_pro_director_return(project, run, "Use option B.")
    assert "Do not solve the implementation problem yourself" in request
    assert "external advisory input" in returned
    assert "Use option B." in returned
