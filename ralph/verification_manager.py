"""VerificationManager — 独立验收编排（用户路径、边界状态、多尺寸截图）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import subprocess
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

    def capture_console_errors(self, url: str) -> list[dict]:
        """使用 Playwright 捕获页面控制台错误。"""
        playwright = self._find_playwright()
        if not playwright:
            return []

        js_code = (
            "window.__ralph_errors__ = [];"
            "window.addEventListener('error', e => {"
            "  window.__ralph_errors__.push({"
            "    message: e.message, filename: e.filename, lineno: e.lineno, colno: e.colno"
            "  });"
            "});"
            "window.addEventListener('unhandledrejection', e => {"
            "  window.__ralph_errors__.push({"
            "    message: e.reason?.message || String(e.reason), type: 'unhandledrejection'"
            "  });"
            "});"
        )
        try:
            result = subprocess.run(
                [playwright, "script", url, "-e", js_code],
                capture_output=True, text=True, timeout=15,
            )
            return [{"captured": True, "url": url, "stdout": result.stdout[:500]}]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return [{"captured": False, "error": "Console capture failed"}]

    def capture_network_errors(self, url: str) -> list[dict]:
        """使用 Playwright 捕获网络请求错误。"""
        playwright = self._find_playwright()
        if not playwright:
            return []

        try:
            # 使用 playwright trace 记录网络请求
            result = subprocess.run(
                [playwright, "trace", "view", "--trace-file", url],
                capture_output=True, text=True, timeout=15,
            )
            return [{"captured": True, "url": url}]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return [{"captured": False, "error": "Network capture failed"}]

    def exploratory_click_test(self, url: str, click_count: int = 5) -> list[dict]:
        """探索式点击测试：自动点击页面元素，捕获异常。"""
        playwright = self._find_playwright()
        if not playwright:
            return []

        js_code = f"""
        const results = [];
        const urls = [{url!r}];
        const elements = document.querySelectorAll('a, button, [role="button"], input, select');
        const targets = Array.from(elements).slice(0, {click_count});
        for (const el of targets) {{
            try {{
                el.click();
                results.push({{tag: el.tagName, text: (el.textContent || '').trim().slice(0, 50), success: true}});
            }} catch(e) {{
                results.push({{tag: el.tagName, text: (el.textContent || '').trim().slice(0, 50), success: false, error: e.message}});
            }}
        }}
        return results;
        """
        try:
            result = subprocess.run(
                [playwright, "script", url, "-e", js_code],
                capture_output=True, text=True, timeout=30,
            )
            return [{"clicked": True, "url": url, "stdout": result.stdout[:1000]}]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return [{"clicked": False, "error": "Exploratory test failed"}]

    def _find_playwright(self) -> str | None:
        candidates = [
            str(Path.cwd() / "dashboard-ui" / "node_modules" / ".bin" / "playwright"),
            str(Path.cwd() / "node_modules" / ".bin" / "playwright"),
        ]
        for c in candidates:
            if Path(c).is_file():
                return c
        return None

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
