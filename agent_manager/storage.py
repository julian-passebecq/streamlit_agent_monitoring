from __future__ import annotations

import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .schema import empty_feature_board, normalized_git_state, normalized_technical_stack, utc_now_iso


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "data"
        self.projects_dir = self.data_dir / "projects"
        self.runs_dir = self.data_dir / "runs"
        self.features_dir = self.data_dir / "features"
        self.artifacts_dir = self.data_dir / "artifacts"
        self.private_dir = self.data_dir / "private"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.private_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        tmp.replace(path)

    def _private_links_path(self, project_id: str) -> Path:
        return self.private_dir / f"{project_id}.json"

    @staticmethod
    def _private_link_payload(project: dict[str, Any]) -> dict[str, Any]:
        onboarding = project.get("onboarding", {})
        return {
            "project_id": project.get("project", {}).get("id", ""),
            "chatgpt_project_url": project.get("project", {}).get("chatgpt_project_url", ""),
            "onboarding": {
                "chatgpt_project_url": onboarding.get("chatgpt_project_url", ""),
                "setup_chat_url": onboarding.get("setup_chat_url", ""),
                "director_chat_url": onboarding.get("director_chat_url", ""),
            },
            "agent_chat_urls": {
                aid: agent.get("chat_url", "")
                for aid, agent in project.get("agents", {}).items()
                if agent.get("chat_url")
            },
        }

    @staticmethod
    def _strip_private_links(project: dict[str, Any]) -> dict[str, Any]:
        clean = deepcopy(project)
        clean.get("project", {})["chatgpt_project_url"] = ""
        onboarding = clean.get("onboarding", {})
        onboarding["chatgpt_project_url"] = ""
        onboarding["setup_chat_url"] = ""
        onboarding["director_chat_url"] = ""
        for agent in clean.get("agents", {}).values():
            agent["chat_url"] = ""
        clean.pop("_path", None)
        return clean

    def _merge_private_links(self, project: dict[str, Any]) -> dict[str, Any]:
        project_id = project.get("project", {}).get("id", "")
        path = self._private_links_path(project_id)
        if not path.exists():
            return project
        try:
            private = self._read_json(path)
        except (OSError, json.JSONDecodeError):
            return project
        if private.get("chatgpt_project_url"):
            project.setdefault("project", {})["chatgpt_project_url"] = private["chatgpt_project_url"]
        onboarding_private = private.get("onboarding", {})
        onboarding = project.setdefault("onboarding", {})
        for key in ("chatgpt_project_url", "setup_chat_url", "director_chat_url"):
            if onboarding_private.get(key):
                onboarding[key] = onboarding_private[key]
        for aid, url in private.get("agent_chat_urls", {}).items():
            if aid in project.get("agents", {}) and url:
                project["agents"][aid]["chat_url"] = url
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for path in sorted(self.projects_dir.glob("*.json")):
            try:
                project = self._merge_private_links(self._read_json(path))
                project["_path"] = str(path)
                projects.append(project)
            except (OSError, json.JSONDecodeError):
                continue
        return projects

    def load_project(self, project_id: str) -> dict[str, Any]:
        project = self._read_json(self.projects_dir / f"{project_id}.json")
        return self._merge_private_links(project)

    def save_project(self, project: dict[str, Any]) -> None:
        project.setdefault("project", {})
        project["updated_at"] = utc_now_iso()
        project_id = project["project"]["id"]
        project["technical_stack"] = normalized_technical_stack(project.get("technical_stack"))
        project["git_state"] = normalized_git_state(project.get("git_state"))
        private = self._private_link_payload(project)
        self._write_json(self._private_links_path(project_id), private)
        clean = self._strip_private_links(project)
        self._write_json(self.projects_dir / f"{project_id}.json", clean)

    def delete_project(self, project_id: str) -> None:
        path = self.projects_dir / f"{project_id}.json"
        if path.exists():
            path.unlink()

    def list_runs(self, project_id: str) -> list[dict[str, Any]]:
        folder = self.runs_dir / project_id
        if not folder.exists():
            return []
        runs = []
        for path in folder.glob("*.json"):
            try:
                runs.append(self._read_json(path))
            except (OSError, json.JSONDecodeError):
                continue
        runs.sort(key=lambda item: (item.get("cycle", {}).get("number", 0), item.get("run", {}).get("created_at", "")), reverse=True)
        return runs

    def load_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self._read_json(self.runs_dir / project_id / f"{run_id}.json")

    def save_run(self, project_id: str, run: dict[str, Any]) -> None:
        run.setdefault("run", {})
        run["run"].setdefault("created_at", utc_now_iso())
        run["run"]["updated_at"] = utc_now_iso()
        run_id = run["run"]["id"]
        self._write_json(self.runs_dir / project_id / f"{run_id}.json", run)

    def load_feature_board(self, project_id: str) -> dict[str, Any]:
        path = self.features_dir / f"{project_id}.json"
        if not path.exists():
            board = empty_feature_board(project_id)
            self.save_feature_board(project_id, board)
            return board
        return self._read_json(path)

    def save_feature_board(self, project_id: str, board: dict[str, Any]) -> None:
        board["project_id"] = project_id
        board["updated_at"] = utc_now_iso()
        self._write_json(self.features_dir / f"{project_id}.json", board)

    def apply_feature_updates(self, project_id: str, updates: list[dict[str, Any]], cycle_id: str, source_agent: str) -> dict[str, Any]:
        board = self.load_feature_board(project_id)
        features = {item.get("id"): deepcopy(item) for item in board.get("features", []) if item.get("id")}
        history = list(board.get("history", []))
        now = utc_now_iso()
        for update in updates or []:
            feature_id = update.get("feature_id") or update.get("id")
            if not feature_id:
                continue
            action = update.get("action", "upsert")
            before = deepcopy(features.get(feature_id, {}))
            if action == "delete":
                if feature_id in features:
                    del features[feature_id]
                    history.append({"at": now, "cycle_id": cycle_id, "feature_id": feature_id, "source_agent": source_agent, "action": "delete", "changes": {"deleted": before}, "note": update.get("note", "")})
                continue
            fields = deepcopy(update.get("fields") or {})
            if not before:
                fields.setdefault("id", feature_id)
                fields.setdefault("created_at", now)
            item = deepcopy(before)
            item.update(fields)
            item["id"] = feature_id
            item["updated_at"] = now
            item["cycle_last_changed"] = cycle_id
            features[feature_id] = item
            changes: dict[str, Any] = {}
            for key, value in item.items():
                old = before.get(key)
                if old != value and key not in {"updated_at"}:
                    changes[key] = {"from": old, "to": value}
            if changes:
                history.append({"at": now, "cycle_id": cycle_id, "feature_id": feature_id, "source_agent": source_agent, "action": "create" if not before else "update", "changes": changes, "note": update.get("note", "")})
        board["features"] = list(features.values())
        board["history"] = history
        self.save_feature_board(project_id, board)
        return board

    def store_agent_return(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        target_run = self.load_run(project_id, payload["run_id"])
        target_run.setdefault("returns", {})[payload["agent_id"]] = payload
        if payload["agent_id"] in target_run.get("dispatches", {}):
            target_run["dispatches"][payload["agent_id"]]["status"] = "returned"
        self.save_run(project_id, target_run)
        updates = payload.get("feature_updates") or []
        if updates:
            self.apply_feature_updates(project_id, updates, payload["run_id"], payload["agent_id"])
        return target_run

    def apply_run_payload(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        self.save_run(project_id, payload)
        if isinstance(payload.get("git_state"), dict):
            project["git_state"] = payload["git_state"]
            self.save_project(project)
        return payload

    def save_setup_artifact(self, project_id: str, stage: str, payload: dict[str, Any]) -> Path:
        stamp = utc_now_iso().replace(":", "-")
        folder = self.artifacts_dir / project_id / "setup" / stage
        path = folder / f"{stamp}.json"
        self._write_json(path, payload)
        return path

    def list_setup_artifacts(self, project_id: str) -> list[Path]:
        folder = self.artifacts_dir / project_id / "setup"
        if not folder.exists():
            return []
        return sorted(folder.rglob("*.json"), reverse=True)

    def apply_project_map(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        onboarding = project.setdefault("onboarding", {})
        onboarding["project_map"] = deepcopy(payload)
        onboarding["stage"] = "selected_app_audit"
        chatgpt_project = payload.get("chatgpt_project", {})
        if chatgpt_project.get("name"):
            onboarding["chatgpt_project_name"] = chatgpt_project["name"]
        if chatgpt_project.get("url"):
            onboarding["chatgpt_project_url"] = chatgpt_project["url"]
            project.setdefault("project", {})["chatgpt_project_url"] = chatgpt_project["url"]
        self.save_project(project)
        self.save_setup_artifact(project_id, "01_project_map", payload)
        return project

    def select_mapped_app(self, project: dict[str, Any], app_id: str) -> dict[str, Any]:
        onboarding = project.setdefault("onboarding", {})
        onboarding["selected_app_id"] = app_id
        onboarding["stage"] = "selected_app_audit"
        selected = {}
        for app in onboarding.get("project_map", {}).get("apps", []):
            if app.get("id") == app_id:
                selected = deepcopy(app)
                break
        onboarding["selected_app"] = selected
        self.save_project(project)
        return project

    def apply_selected_app_audit(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        onboarding = project.setdefault("onboarding", {})
        onboarding["selected_app_audit"] = deepcopy(payload)
        onboarding["stage"] = "director_organization"
        project["technical_stack"] = normalized_technical_stack(payload.get("technical_stack"))
        project["git_state"] = normalized_git_state(payload.get("git_state"))
        project["repositories"] = deepcopy(payload.get("repositories", []))
        project["chat_inventory"] = deepcopy(payload.get("chat_inventory", []))
        identity = payload.get("identity", {})
        if identity.get("name"):
            project["project"]["name"] = identity["name"]
        if identity.get("purpose"):
            project["project"]["description"] = identity["purpose"]
        primary = payload.get("git_state", {}).get("repository_url")
        if primary:
            project["project"]["repository_url"] = primary
        self.save_project(project)
        self.save_setup_artifact(project_id, "02_selected_app_audit", payload)
        return project

    def apply_director_organization_plan(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        onboarding = project.setdefault("onboarding", {})
        onboarding["director_organization_plan"] = deepcopy(payload)
        onboarding["stage"] = "director_feature_plan"
        if payload.get("shared_project_instructions_draft"):
            project["shared_project_instructions"] = payload["shared_project_instructions_draft"]
        org = payload.get("organization", {})
        existing_agents = project.get("agents", {})
        proposed_agents = deepcopy(org.get("agents", {}))
        merged: dict[str, Any] = {} if org.get("replace_agents") else deepcopy(existing_agents)
        for aid, proposed in proposed_agents.items():
            prior = existing_agents.get(aid, {})
            proposed.setdefault("id", aid)
            proposed.setdefault("surface", prior.get("surface", "ChatGPT"))
            proposed.setdefault("receives_dispatch", True)
            proposed.setdefault("active_default", proposed.get("receives_dispatch", True))
            proposed["chat_url"] = prior.get("chat_url", proposed.get("chat_url", ""))
            proposed["bootstrap_installed"] = prior.get("bootstrap_installed", False)
            merged[aid] = proposed
        project["agents"] = merged
        workflow = project.setdefault("workflow", {})
        workflow["relationships"] = deepcopy(org.get("relationships", []))
        workflow["organization_rationale"] = org.get("rationale", "")
        workflow["governance"] = deepcopy(org.get("governance", {}))
        if isinstance(payload.get("pro_desk"), dict):
            project["pro_desk"] = deepcopy(payload["pro_desk"])
        self.save_project(project)
        self.save_setup_artifact(project_id, "03_director_organization", payload)
        return project

    def apply_director_feature_plan(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        onboarding = project.setdefault("onboarding", {})
        onboarding["director_feature_plan"] = deepcopy(payload)
        onboarding["stage"] = "agent_bootstrap"
        project["cycle_plan"] = deepcopy(payload.get("next_cycle", {}))
        project["milestones"] = deepcopy(payload.get("milestones", []))
        board = deepcopy(payload.get("feature_board", {}))
        if isinstance(board, dict):
            board["project_id"] = project_id
            board.setdefault("features", [])
            board.setdefault("history", [])
            self.save_feature_board(project_id, board)
        cycle = payload.get("next_cycle", {})
        if cycle.get("id"):
            shell = {
                "schema_version": "1.0",
                "type": "agent_manager_run",
                "project_id": project_id,
                "run": {"id": cycle["id"], "title": cycle.get("title", "Next cycle"), "objective": cycle.get("objective", ""), "status": "planning", "created_at": utc_now_iso()},
                "cycle": {"number": cycle.get("number", 1), "phase": cycle.get("phase", "director_plan"), "status": "active", "active_agents": cycle.get("active_agents", []), "standby_agents": cycle.get("standby_agents", []), "selected_feature_ids": cycle.get("selected_feature_ids", []), "started_at": utc_now_iso(), "completed_at": "", "notes": "Created from Director feature/plan setup."},
                "git_state": normalized_git_state(project.get("git_state")),
                "director_context": {"summary": payload.get("planning_summary", ""), "decisions": [], "constraints": payload.get("planning_rules", []), "open_questions": cycle.get("questions", [])},
                "dispatches": {}, "returns": {}, "pro_context": {"needs_pro_review": False, "topics": [], "questions": []},
            }
            self.save_run(project_id, shell)
        self.save_project(project)
        self.save_setup_artifact(project_id, "04_director_feature_plan", payload)
        return project

    def apply_agent_bootstrap_pack(self, project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        onboarding = project.setdefault("onboarding", {})
        onboarding["agent_bootstrap_pack"] = deepcopy(payload)
        onboarding["stage"] = "ready"
        if payload.get("shared_project_instructions"):
            project["shared_project_instructions"] = payload["shared_project_instructions"]
        for aid, packed in payload.get("agents", {}).items():
            if aid not in project.get("agents", {}):
                continue
            agent = project["agents"][aid]
            for field in ("conversation_name", "surface", "model_label", "custom_instructions", "reporting_contract", "startup_behavior"):
                if packed.get(field) not in (None, ""):
                    target = "name" if field == "conversation_name" else field
                    agent[target] = packed[field]
        self.save_project(project)
        self.save_setup_artifact(project_id, "05_agent_bootstrap", payload)
        return project

    def build_archive_zip(self, project: dict[str, Any], include_chat_urls: bool = False) -> bytes:
        project_id = project["project"]["id"]
        snapshot = deepcopy(project)
        if not include_chat_urls:
            snapshot.get("project", {})["chatgpt_project_url"] = ""
            onboarding = snapshot.get("onboarding", {})
            onboarding["chatgpt_project_url"] = ""
            onboarding["setup_chat_url"] = ""
            for agent in snapshot.get("agents", {}).values():
                agent["chat_url"] = ""
            for chat in snapshot.get("chat_inventory", []):
                if isinstance(chat, dict):
                    chat["url"] = ""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{project_id}/project.json", json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")
            board = self.load_feature_board(project_id)
            zf.writestr(f"{project_id}/feature_board.json", json.dumps(board, indent=2, ensure_ascii=False) + "\n")
            for run in self.list_runs(project_id):
                run_id = run.get("run", {}).get("id", "run")
                zf.writestr(f"{project_id}/cycles/{run_id}.json", json.dumps(run, indent=2, ensure_ascii=False) + "\n")
            for artifact in self.list_setup_artifacts(project_id):
                rel = artifact.relative_to(self.artifacts_dir / project_id)
                zf.writestr(f"{project_id}/artifacts/{rel.as_posix()}", artifact.read_text(encoding="utf-8"))
            manifest = {"project_id": project_id, "exported_at": utc_now_iso(), "chat_urls_included": include_chat_urls, "note": "Agent Manager archive bundle. Keep this outside the implementation repository if you want clean product Git history."}
            zf.writestr(f"{project_id}/MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        return buffer.getvalue()

    def apply_bootstrap_audit(self, project: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
        project_id = project["project"]["id"]
        project["technical_stack"] = normalized_technical_stack(audit.get("technical_stack"))
        project["git_state"] = normalized_git_state(audit.get("git_state"))
        project["repositories"] = deepcopy(audit.get("repositories", []))
        project["startup_audit"] = {"audited_at": audit.get("audited_at", ""), "audit_summary": audit.get("audit_summary", ""), "current_state": deepcopy(audit.get("current_state", {}))}
        org = audit.get("agent_organization", {})
        existing_agents = project.get("agents", {})
        proposed_agents = deepcopy(org.get("agents", {}))
        merged_agents: dict[str, Any] = {} if org.get("replace_agents") else deepcopy(existing_agents)
        for aid, proposed in proposed_agents.items():
            prior = existing_agents.get(aid, {})
            proposed.setdefault("id", aid)
            proposed.setdefault("surface", prior.get("surface", "ChatGPT"))
            proposed.setdefault("receives_dispatch", True)
            proposed.setdefault("active_default", proposed.get("receives_dispatch", True))
            proposed["chat_url"] = prior.get("chat_url", proposed.get("chat_url", ""))
            proposed["bootstrap_installed"] = prior.get("bootstrap_installed", False)
            merged_agents[aid] = proposed
        project["agents"] = merged_agents
        project.setdefault("workflow", {})["relationships"] = deepcopy(org.get("relationships", []))
        project["workflow"]["organization_rationale"] = org.get("rationale", "")
        project["cycle_plan"] = deepcopy(audit.get("next_cycle", {}))
        self.save_project(project)
        board = audit.get("feature_board")
        if isinstance(board, dict):
            board = deepcopy(board)
            board["project_id"] = project_id
            board.setdefault("features", [])
            board.setdefault("history", [])
            self.save_feature_board(project_id, board)
        cycle = audit.get("next_cycle", {})
        if cycle.get("id"):
            shell = {
                "schema_version": "1.0", "type": "agent_manager_run", "project_id": project_id,
                "run": {"id": cycle["id"], "title": cycle.get("title", "Next cycle"), "objective": cycle.get("objective", ""), "status": "planning", "created_at": utc_now_iso()},
                "cycle": {"number": cycle.get("number", 1), "phase": cycle.get("phase", "director_plan"), "status": "active", "active_agents": cycle.get("active_agents", []), "standby_agents": cycle.get("standby_agents", []), "started_at": utc_now_iso(), "completed_at": "", "notes": "Created from startup/resume audit."},
                "git_state": normalized_git_state(audit.get("git_state")),
                "director_context": {"summary": audit.get("audit_summary", ""), "decisions": [], "constraints": [], "open_questions": cycle.get("questions", [])},
                "dispatches": {}, "returns": {}, "pro_context": {"needs_pro_review": False, "topics": [], "questions": []},
            }
            self.save_run(project_id, shell)
        return project
