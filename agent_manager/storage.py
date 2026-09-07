from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import utc_now_iso


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.data_dir = root / "data"
        self.projects_dir = self.data_dir / "projects"
        self.runs_dir = self.data_dir / "runs"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

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

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for path in sorted(self.projects_dir.glob("*.json")):
            try:
                project = self._read_json(path)
                project["_path"] = str(path)
                projects.append(project)
            except (OSError, json.JSONDecodeError):
                continue
        return projects

    def load_project(self, project_id: str) -> dict[str, Any]:
        return self._read_json(self.projects_dir / f"{project_id}.json")

    def save_project(self, project: dict[str, Any]) -> None:
        project.setdefault("project", {})
        project["updated_at"] = utc_now_iso()
        project_id = project["project"]["id"]
        self._write_json(self.projects_dir / f"{project_id}.json", project)

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
        runs.sort(
            key=lambda item: item.get("run", {}).get("created_at", ""), reverse=True
        )
        return runs

    def load_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self._read_json(self.runs_dir / project_id / f"{run_id}.json")

    def save_run(self, project_id: str, run: dict[str, Any]) -> None:
        run.setdefault("run", {})
        run["run"].setdefault("created_at", utc_now_iso())
        run["run"]["updated_at"] = utc_now_iso()
        run_id = run["run"]["id"]
        self._write_json(self.runs_dir / project_id / f"{run_id}.json", run)

    def apply_run_payload(
        self, project: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        project_id = project["project"]["id"]
        self.save_run(project_id, payload)
        if isinstance(payload.get("git_state"), dict):
            project["git_state"] = payload["git_state"]
            self.save_project(project)
        return payload
