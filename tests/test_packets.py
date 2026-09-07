from pathlib import Path
import json

from agent_manager.packets import (
    bootstrap_packet,
    build_liaison_request,
    build_pro_director_return,
    build_prompt_agent_request,
    build_startup_audit_prompt,
    companion_run_schema_example,
    dispatch_packet,
    prompt_agent_bootstrap,
    startup_audit_schema_example,
)

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_dispatch_contains_model_git_stack_and_cycle_metadata():
    project = load("data/projects/datapass-v4.json")
    run = load("data/runs/datapass-v4/DPV4-001.json")
    packet = dispatch_packet(project, run, "code_agent_a")
    assert 'model_label: "Codex"' in packet
    assert 'head_sha: "ce8353ee0878ca74b2fe24a1af7de657a6ba61f2"' in packet
    assert 'languages: ["TypeScript", "JavaScript"]' in packet
    assert 'cycle_number: "1"' in packet
    assert "Example bounded implementation task" in packet


def test_bootstrap_contains_shared_and_agent_instructions():
    project = load("data/projects/datapass-v4.json")
    packet = bootstrap_packet(project, project["agents"]["qa"])
    assert "Shared project instructions" in packet
    assert "Verify Director-defined acceptance criteria independently" in packet
    assert "Project technical baseline" in packet


def test_companion_schema_uses_known_selected_agents_only():
    project = load("data/projects/datapass-v4.json")
    example = companion_run_schema_example(project, ["code_agent_a", "audit"])
    assert set(example["dispatches"]) == {"code_agent_a", "audit"}
    assert set(example["dispatches"]).issubset(project["agents"])
    assert example["cycle"]["active_agents"] == ["code_agent_a", "audit"]


def test_startup_audit_prompt_requests_stack_git_org_and_feature_history():
    project = load("data/projects/datapass-v4.json")
    prompt = build_startup_audit_prompt(project)
    schema = startup_audit_schema_example(project)
    assert "programming languages, frameworks, SDKs/libraries" in prompt
    assert "hierarchical feature/problem/bug/refactor/QA backlog" in prompt
    assert "optimized agent organization" in prompt
    assert schema["type"] == "project_bootstrap_audit"
    assert "technical_stack" in schema
    assert "feature_board" in schema


def test_prompt_agent_request_respects_selected_workers_and_authority():
    project = load("data/projects/datapass-v4.json")
    run = load("data/runs/datapass-v4/DPV4-001.json")
    packet = build_prompt_agent_request(project, "Code A implements X. Audit records the result.", ["code_agent_a", "audit"], run)
    assert '"code_agent_a"' in packet
    assert '"audit"' in packet
    assert '"code_agent_b"' not in packet.split("## Required run JSON shape", 1)[1]
    assert "Director owns the decisions" in packet
    assert "Do not request hidden chain-of-thought" in packet


def test_prompt_agent_bootstrap_contains_prompt_method():
    project = load("data/projects/datapass-v4.json")
    packet = prompt_agent_bootstrap(project)
    assert "State the concrete outcome first" in packet
    assert "Do not add technical decisions" in packet


def test_pro_workflow_packets_are_advisory():
    project = load("data/projects/datapass-v4.json")
    run = load("data/runs/datapass-v4/DPV4-001.json")
    request = build_liaison_request(project, run)
    returned = build_pro_director_return(project, run, "Use option B.")
    assert "Do not solve the implementation problem yourself" in request
    assert "external advisory input" in returned
    assert "Use option B." in returned
