"""Evidence Collector — 证据收集

文档依据：
- AI 协议 §8.2 执行结果格式 — evidence_files 字段
- MVP 清单 §9 开发执行验收清单 — 必须提交证据文件
- PRD §9.10 真实可用性验收 — diff、测试输出、Playwright 截图
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from ralph.schema.evidence import Evidence

logger = logging.getLogger(__name__)


class EvidenceCollector:
    """收集执行证据并保存到 .ralph/evidence/<work_id>/。"""

    # Playwright 优先从 dashboard-ui 的 node_modules 找
    _PLAYWRIGHT_BIN: str | None = None

    @classmethod
    def _find_playwright(cls) -> str | None:
        if cls._PLAYWRIGHT_BIN is not None:
            return cls._PLAYWRIGHT_BIN if cls._PLAYWRIGHT_BIN else None
        import os
        project_root = os.environ.get("PROJECT_DIR", "")
        candidates = [
            str(Path.cwd() / "dashboard-ui" / "node_modules" / ".bin" / "playwright"),
            str(Path.cwd() / "node_modules" / ".bin" / "playwright"),
        ]
        if project_root:
            candidates.insert(0, str(Path(project_root) / "dashboard-ui" / "node_modules" / ".bin" / "playwright"))
        # 硬编码的备用路径
        candidates.append("/Users/jieson/auto-coding/dashboard-ui/node_modules/.bin/playwright")
        for c in candidates:
            if Path(c).is_file():
                cls._PLAYWRIGHT_BIN = c
                return c
        cls._PLAYWRIGHT_BIN = ""  # 标记已搜索过
        return None

    def __init__(self, ralph_dir: Path) -> None:
        self._evidence_base = ralph_dir / "evidence"
        self._evidence_base.mkdir(parents=True, exist_ok=True)

    def collect(
        self,
        work_id: str,
        workspace_dir: Path,
        *,
        include_diff: bool = True,
        include_files_changed: bool = True,
        include_test_output: str = "",
    ) -> list[Evidence]:
        """收集证据。

        Args:
            work_id: 工作单元 ID
            workspace_dir: 工作目录
            include_diff: 是否收集 git diff
            include_files_changed: 是否收集文件变更清单
            include_test_output: 测试输出（如果提供则保存）

        Returns:
            收集到的 Evidence 列表
        """
        evidence_dir = self._evidence_base / work_id
        evidence_dir.mkdir(parents=True, exist_ok=True)

        items: list[Evidence] = []

        if include_diff:
            e = self._collect_diff(work_id, workspace_dir, evidence_dir)
            if e:
                items.append(e)

        if include_files_changed:
            e = self._collect_files_changed(work_id, workspace_dir, evidence_dir)
            if e:
                items.append(e)

        if include_test_output:
            e = self._save_test_output(work_id, include_test_output, evidence_dir)
            if e:
                items.append(e)

        logger.info("为 %s 收集了 %d 个证据", work_id, len(items))
        return items

    def collect_playwright_screenshots(
        self, work_id: str, url: str = "http://localhost:3000",
    ) -> list[Evidence]:
        """尝试用 Playwright 采集浏览器截图证据。

        如果 Playwright 不可用则静默跳过，不阻塞管道。
        """
        evidence_dir = self._evidence_base / work_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        items: list[Evidence] = []

        playwright_bin = self._find_playwright()
        if not playwright_bin:
            logger.debug("Playwright 不可用（未安装）: %s", work_id)
            return items

        try:
            result = subprocess.run(
                [playwright_bin, "screenshot", url,
                 str(evidence_dir / "screenshot.png")],
                capture_output=True, text=True, timeout=30,
                env=self._playwright_env(),
            )
            if result.returncode == 0:
                screenshot_path = evidence_dir / "screenshot.png"
                items.append(Evidence(
                    evidence_id=f"ev-{work_id}-playwright",
                    work_id=work_id,
                    evidence_type="screenshot",
                    file_path=str(screenshot_path),
                    description=f"Playwright screenshot of {url}",
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            logger.debug("Playwright 截图跳过（不可用）: %s", work_id)

        return items

    def collect_multi_size_screenshots(
        self, work_id: str, url: str = "http://localhost:3000",
    ) -> list[Evidence]:
        """多尺寸 Playwright 截图（移动端/平板/桌面）。"""
        sizes = [("mobile", 375, 812), ("tablet", 768, 1024), ("desktop", 1280, 800)]
        items: list[Evidence] = []
        evidence_dir = self._evidence_base / work_id
        evidence_dir.mkdir(parents=True, exist_ok=True)

        playwright_bin = self._find_playwright()
        if not playwright_bin:
            logger.debug("Playwright 不可用（未安装）: %s", work_id)
            return items

        for label, w, h in sizes:
            try:
                result = subprocess.run(
                    [playwright_bin, "screenshot", url,
                     f"--viewport-size={w},{h}",
                     str(evidence_dir / f"screenshot-{label}.png")],
                    capture_output=True, text=True, timeout=30,
                    env=self._playwright_env(),
                )
                if result.returncode == 0:
                    items.append(Evidence(
                        evidence_id=f"ev-{work_id}-screenshot-{label}",
                        work_id=work_id,
                        evidence_type="screenshot",
                        file_path=str(evidence_dir / f"screenshot-{label}.png"),
                        description=f"Screenshot {label} ({w}x{h})",
                    ))
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                logger.debug("Playwright %s screenshot skipped: %s", label, work_id)

        return items

    @staticmethod
    def _playwright_env() -> dict:
        import os
        env = {k: v for k, v in os.environ.items()}
        cached = str(Path.home() / "Library" / "Caches" / "ms-playwright")
        if cached:
            env["PLAYWRIGHT_BROWSERS_PATH"] = cached
        return env

    def _collect_diff(
        self, work_id: str, workspace_dir: Path, evidence_dir: Path
    ) -> Evidence | None:
        """收集 git diff --stat。"""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            content = result.stdout.strip()
            if not content:
                return None

            file_path = evidence_dir / "diff.txt"
            file_path.write_text(content, encoding="utf-8")

            return Evidence(
                evidence_id=f"{work_id}-diff",
                work_id=work_id,
                evidence_type="diff",
                file_path=str(file_path),
                description="git diff --stat HEAD",
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _collect_files_changed(
        self, work_id: str, workspace_dir: Path, evidence_dir: Path
    ) -> Evidence | None:
        """收集变更文件列表。"""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            content = result.stdout.strip()
            if not content:
                return None

            file_path = evidence_dir / "files_changed.txt"
            file_path.write_text(content, encoding="utf-8")

            return Evidence(
                evidence_id=f"{work_id}-files",
                work_id=work_id,
                evidence_type="files_changed",
                file_path=str(file_path),
                description="变更文件列表",
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _save_test_output(
        self, work_id: str, output: str, evidence_dir: Path
    ) -> Evidence:
        """保存测试输出。"""
        file_path = evidence_dir / "test_output.txt"
        file_path.write_text(output, encoding="utf-8")

        return Evidence(
            evidence_id=f"{work_id}-test",
            work_id=work_id,
            evidence_type="test_output",
            file_path=str(file_path),
            description="测试输出",
        )
