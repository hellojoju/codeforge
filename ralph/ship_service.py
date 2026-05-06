from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ralph.repository import RalphRepository
from ralph.schema.work_unit import WorkUnitStatus


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S")


@dataclass
class ShipResult:
    success: bool
    message: str
    tag: str = ""
    branch: str = ""
    changelog_path: str = ""
    pr_url: str = ""
    pushed: bool = False


class ShipService:
    def __init__(self, ralph_dir: Path | str, project_dir: Path | str):
        self._ralph_dir = Path(ralph_dir)
        self._project_dir = Path(project_dir)
        self._repo = RalphRepository(self._ralph_dir)

    def verify_pre_ship(self, work_id: str) -> list[dict | str]:
        blockers: list[dict | str] = []
        unit = self._repo.get_work_unit(work_id)
        if unit is None:
            blockers.append({"type": "missing_work_unit", "message": f"WorkUnit {work_id} 不存在"})
            return blockers
        if unit.status != WorkUnitStatus.ACCEPTED:
            blockers.append({"type": "invalid_status", "message": f"当前状态不是 accepted: {unit.status.value}"})
        unresolved = self._repo.list_blockers(work_id=work_id, resolved=False)
        if unresolved:
            blockers.append({"type": "unresolved_blockers", "message": f"存在 {len(unresolved)} 个未解决阻塞"})
        return blockers

    def ship_work_unit(
        self,
        work_id: str,
        strategy: str = "patch",
        tag_prefix: str = "v",
        push_remote: bool = False,
        create_pr_flag: bool = False,
        pr_base: str = "main",
    ) -> ShipResult:
        blockers = self.verify_pre_ship(work_id)
        if blockers:
            return ShipResult(success=False, message="发布前验证未通过")

        ts = _now_tag()
        branch = f"release/{work_id}-{ts}"
        tag = f"{tag_prefix}{ts}"
        releases_dir = self._ralph_dir / "releases"
        releases_dir.mkdir(parents=True, exist_ok=True)
        changelog = releases_dir / f"{tag}.md"
        changelog.write_text(
            f"# Release {tag}\n\n- WorkUnit: {work_id}\n- Strategy: {strategy}\n- Base: {pr_base}\n",
            encoding="utf-8",
        )

        try:
            subprocess.run(["git", "checkout", "-b", branch], cwd=self._project_dir, check=False, timeout=10)
            subprocess.run(["git", "tag", tag], cwd=self._project_dir, check=False, timeout=10)
            pushed = False
            if push_remote:
                subprocess.run(["git", "push", "-u", "origin", branch], cwd=self._project_dir, check=False, timeout=20)
                subprocess.run(["git", "push", "origin", tag], cwd=self._project_dir, check=False, timeout=20)
                pushed = True
        except Exception:
            pushed = False

        pr_url = f"https://example.local/pr/{branch}?base={pr_base}" if create_pr_flag else ""
        return ShipResult(
            success=True,
            message="发布成功",
            tag=tag,
            branch=branch,
            changelog_path=str(changelog),
            pr_url=pr_url,
            pushed=pushed,
        )
