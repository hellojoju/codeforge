"""VerificationManager — 独立验收编排（用户路径、边界状态、多尺寸截图）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ralph.schema.brainstorm_record import UserPath


@dataclass
class VerificationChecklist:
    work_id: str
    user_paths: list = field(default_factory=list)
    boundary_states: list[str] = field(default_factory=lambda: [
        "empty", "loading", "error", "unauthorized",
    ])
    screenshot_sizes: list[tuple[int, int]] = field(default_factory=lambda: [
        (375, 812), (768, 1024), (1280, 800),
    ])
    checks: list[dict] = field(default_factory=list)
    # 每个 check: {check_name, passed, evidence, notes}


class VerificationManager:
    """独立验收编排器。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir

    def build_checklist(
        self, work_id: str, user_paths: list[UserPath] | None = None,
    ) -> VerificationChecklist:
        return VerificationChecklist(
            work_id=work_id, user_paths=list(user_paths or []),
        )

    def verify_user_paths(
        self, checklist: VerificationChecklist,
        base_url: str = "http://localhost:3000",
    ) -> VerificationChecklist:
        for path_item in checklist.user_paths:
            name = getattr(path_item, "name", str(path_item))
            steps = getattr(path_item, "steps", [])
            for step in steps:
                checklist.checks.append({
                    "check_name": f"user_path:{name}:{step}",
                    "passed": False,
                    "evidence": f"Playwright: navigate '{step}' at {base_url}",
                    "notes": "Requires Playwright runtime for verification",
                })
        return checklist

    def verify_boundary_states(
        self, checklist: VerificationChecklist,
    ) -> VerificationChecklist:
        for state in checklist.boundary_states:
            checklist.checks.append({
                "check_name": f"boundary:{state}",
                "passed": False,
                "evidence": f"Visual check: verify {state} state renders correctly",
                "notes": "Visual inspection or Playwright screenshot required",
            })
        return checklist

    def verify_multi_size_screenshots(
        self, checklist: VerificationChecklist,
    ) -> VerificationChecklist:
        for w, h in checklist.screenshot_sizes:
            checklist.checks.append({
                "check_name": f"screenshot:{w}x{h}",
                "passed": False,
                "evidence": f"Playwright screenshot at {w}x{h} viewport",
                "notes": f"Save screenshot at {w}x{h}",
            })
        return checklist

    def get_checklist(self, work_id: str) -> VerificationChecklist | None:
        path = self._dir / "evidence" / f"{work_id}_checklist.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return VerificationChecklist(**data)

    def save_checklist(self, checklist: VerificationChecklist) -> None:
        evidence_dir = self._dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path = evidence_dir / f"{checklist.work_id}_checklist.json"
        path.write_text(json.dumps(
            {k: v for k, v in checklist.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
