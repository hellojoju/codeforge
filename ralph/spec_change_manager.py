"""SpecChangeManager — OpenSpec-style 规格生命周期管理。"""

from __future__ import annotations

import json
from pathlib import Path

from ralph.schema.spec_document import SpecDocument, SpecChange, _now_iso


class SpecChangeManager:
    """管理 .ralph/specs/current/ + .ralph/specs/changes/ + .ralph/specs/archive/"""

    def __init__(self, ralph_dir: Path):
        self._current_dir = ralph_dir / "specs" / "current"
        self._changes_dir = ralph_dir / "specs" / "changes"
        self._archive_dir = ralph_dir / "specs" / "archive"
        for d in [self._current_dir, self._changes_dir, self._archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # --- Current Specs ---

    def save_spec(self, spec: SpecDocument) -> SpecDocument:
        spec.updated_at = _now_iso()
        target = self._current_dir if spec.status == "current" else self._archive_dir
        path = target / f"{spec.capability}.json"
        path.write_text(json.dumps(
            {k: v for k, v in spec.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
        return spec

    def get_spec(self, capability: str) -> SpecDocument | None:
        path = self._current_dir / f"{capability}.json"
        if not path.is_file():
            return None
        return SpecDocument(**json.loads(path.read_text()))

    def list_specs(self) -> list[dict]:
        specs = []
        for f in sorted(self._current_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                specs.append({
                    "spec_id": data.get("spec_id", ""),
                    "capability": data.get("capability", f.stem),
                    "title": data.get("title", ""),
                    "version": data.get("version", ""),
                    "status": data.get("status", ""),
                    "interfaces": len(data.get("interfaces", [])),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return specs

    # --- Changes ---

    def create_change(self, change: SpecChange) -> SpecChange:
        path = self._changes_dir / f"{change.change_id}.json"
        path.write_text(json.dumps(
            {k: v for k, v in change.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
        return change

    def approve_change(self, change_id: str) -> SpecChange | None:
        change = self._load_change(change_id)
        if not change:
            return None
        change.status = "approved"
        self.create_change(change)
        return change

    def reject_change(self, change_id: str) -> SpecChange | None:
        change = self._load_change(change_id)
        if not change:
            return None
        change.status = "rejected"
        self.create_change(change)
        return change

    def apply_change(self, change_id: str) -> SpecChange | None:
        change = self._load_change(change_id)
        if not change or change.status != "approved":
            return None
        for delta in change.spec_deltas:
            spec = self.get_spec(delta["spec_id"])
            if spec:
                setattr(spec, delta["field"], delta["new"])
                self.save_spec(spec)
        change.status = "applied"
        self.create_change(change)
        # 归档
        src = self._changes_dir / f"{change_id}.json"
        dst = self._archive_dir / f"{change_id}.json"
        if src.is_file():
            src.rename(dst)
        return change

    def list_changes(self) -> list[dict]:
        changes = []
        for f in sorted(self._changes_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                changes.append({
                    "change_id": data.get("change_id", f.stem),
                    "title": data.get("title", ""),
                    "status": data.get("status", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return changes

    # --- Internal ---

    def _load_change(self, change_id: str) -> SpecChange | None:
        path = self._changes_dir / f"{change_id}.json"
        if not path.is_file():
            return None
        return SpecChange(**json.loads(path.read_text()))
