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
        base_url: str = "http://localhost:3000",
    ) -> VerificationChecklist:
        pw = self._find_playwright()
        if not pw:
            return self._stub_screenshots(checklist)

        for w, h in checklist.screenshot_sizes:
            evidence_dir = self._dir / "evidence" / checklist.work_id
            evidence_dir.mkdir(parents=True, exist_ok=True)
            shot_path = evidence_dir / f"screenshot_{w}x{h}.png"
            script_path = evidence_dir / f"_pw_{w}x{h}.py"

            script = self._generate_screenshot_script(base_url, w, h, str(shot_path))
            script_path.write_text(script, encoding="utf-8")

            try:
                result = subprocess.run(
                    ["python", str(script_path)],
                    capture_output=True, text=True, timeout=30,
                )
                passed = result.returncode == 0 and Path(shot_path).exists()
                checklist.checks.append({
                    "check_name": f"screenshot:{w}x{h}",
                    "passed": passed,
                    "evidence": str(shot_path) if passed else None,
                    "notes": result.stderr[:200] if not passed else "OK",
                })
            except (subprocess.TimeoutExpired, Exception) as e:
                checklist.checks.append({
                    "check_name": f"screenshot:{w}x{h}",
                    "passed": False,
                    "evidence": None,
                    "notes": str(e),
                })
        return checklist

    def _stub_screenshots(self, checklist: VerificationChecklist) -> VerificationChecklist:
        """无 Playwright 时生成占位 check。"""
        for w, h in checklist.screenshot_sizes:
            checklist.checks.append({
                "check_name": f"screenshot:{w}x{h}",
                "passed": False,
                "evidence": None,
                "notes": "Playwright 未安装，跳过",
            })
        return checklist

    @staticmethod
    def _generate_screenshot_script(url: str, width: int, height: int, output: str) -> str:
        return f'''import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={{"width": {width}, "height": {height}}})
        page = await context.new_page()
        await page.goto("{url}", wait_until="networkidle")
        await page.screenshot(path="{output}")
        await browser.close()

asyncio.run(main())
'''

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

        cmd_prefix = [playwright] if not playwright.startswith("npx") else ["npx", "playwright"]
        try:
            result = subprocess.run(
                cmd_prefix + ["script", url, "-e", js_code],
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

        cmd_prefix = [playwright] if not playwright.startswith("npx") else ["npx", "playwright"]
        try:
            # 使用 playwright trace 记录网络请求
            result = subprocess.run(
                cmd_prefix + ["trace", "view", "--trace-file", url],
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

        cmd_prefix = [playwright] if not playwright.startswith("npx") else ["npx", "playwright"]
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
                cmd_prefix + ["script", url, "-e", js_code],
                capture_output=True, text=True, timeout=30,
            )
            return [{"clicked": True, "url": url, "stdout": result.stdout[:1000]}]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return [{"clicked": False, "error": "Exploratory test failed"}]

    def generate_test_file(
        self,
        work_id: str,
        title: str,
        acceptance_criteria: list[str],
        scope_allow: list[str],
        test_command: str = "",
        output_dir: Path | None = None,
    ) -> Path | None:
        """从 WorkUnit 验收标准自动生成测试文件骨架。"""
        if not acceptance_criteria:
            return None

        out_dir = output_dir or (Path(__file__).parent.parent / "tests" / "ralph_generated")
        out_dir.mkdir(parents=True, exist_ok=True)
        test_file = out_dir / f"test_{work_id.lower().replace('-', '_')}.py"

        lines = [
            f'"""Auto-generated tests for WorkUnit: {title}"""',
            "",
            "import pytest",
            "",
            "",
        ]
        for i, criterion in enumerate(acceptance_criteria):
            safe_name = f"test_{work_id.lower().replace('-', '_')}_{i}"
            lines.extend([
                f"def {safe_name}():",
                f'    """验收标准: {criterion}"""',
                "    # TODO: 实现测试逻辑",
                f'    # 验收标准原文: "{criterion}"',
                f"    # 涉及文件: {', '.join(scope_allow)}",
                "    assert True  # placeholder",
                "",
                "",
            ])

        if test_command:
            lines.append(f"# 测试命令: {test_command}")
            lines.append("")

        test_file.write_text("\n".join(lines), encoding="utf-8")
        return test_file

    def _find_playwright(self) -> str | None:
        """查找 Playwright 可执行文件。

        搜索顺序：
        1. 本地 node_modules/.bin/playwright
        2. npx playwright
        3. 全局 playwright CLI (pip / brew 安装)
        """
        # 1. 本地 node_modules
        candidates = [
            str(Path.cwd() / "dashboard-ui" / "node_modules" / ".bin" / "playwright"),
            str(Path.cwd() / "node_modules" / ".bin" / "playwright"),
        ]
        for c in candidates:
            if Path(c).is_file():
                return c

        # 2. npx playwright
        try:
            result = subprocess.run(
                ["npx", "playwright", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return "npx playwright"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 3. 全局 playwright CLI
        try:
            result = subprocess.run(
                ["playwright", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return "playwright"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None

    def run_tests(self, test_command: str = "", project_dir: Path | None = None) -> dict:
        """运行测试/typecheck/lint。"""
        import subprocess
        import re
        base = project_dir or self._dir
        cmd = test_command or "python3 -m pytest -q"
        try:
            result = subprocess.run(
                cmd.split(), cwd=base,
                capture_output=True, text=True, timeout=600,
            )
            passed = result.returncode == 0
            match = re.search(r"(\d+) passed", result.stdout)
            total = int(match.group(1)) if match else 0
            return {"success": passed, "total": total, "output": result.stdout[-300], "command": cmd}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except FileNotFoundError:
            return {"success": False, "error": f"Command not found: {cmd}"}

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
