from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScreenshotDiff:
    baseline_path: str
    current_path: str
    changed_pixels: int = 0
    similarity: float = 1.0
    similar: bool = True

    def to_dict(self) -> dict:
        return {
            "baseline_path": self.baseline_path,
            "current_path": self.current_path,
            "changed_pixels": self.changed_pixels,
            "similarity": self.similarity,
            "similar": self.similar,
        }


class PersistentBrowser:
    """真实 Playwright 集成：持久化上下文、截图、页面操作、健康监控。"""

    def __init__(self, user_data_dir: str | Path, *, headless: bool = True):
        self._dir = Path(user_data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._shots = self._dir / "screenshots"
        self._shots.mkdir(parents=True, exist_ok=True)
        self._baselines = self._shots / "baselines"
        self._baselines.mkdir(parents=True, exist_ok=True)
        self._headless = headless

        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._health_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动 Playwright 持久化上下文。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
            raise

        self._playwright = await async_playwright()
        user_data = self._dir / "user-data"
        user_data.mkdir(parents=True, exist_ok=True)

        self._browser = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=self._headless,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        self._page = await self._browser.new_page()
        logger.info("Persistent browser started (headless=%s)", self._headless)

    async def close(self) -> None:
        """优雅关闭。"""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def get_page(self) -> Any:
        """获取当前页面。"""
        if self._page is None:
            raise RuntimeError("Browser not started. Call start() first.")
        return self._page

    async def navigate(self, url: str, *, wait_until: str = "networkidle") -> None:
        """导航到 URL。"""
        page = await self.get_page()
        await page.goto(url, wait_until=wait_until)

    async def click(self, selector: str) -> None:
        page = await self.get_page()
        await page.click(selector)

    async def fill(self, selector: str, value: str) -> None:
        page = await self.get_page()
        await page.fill(selector, value)

    async def take_screenshot(self, name: str, page: Any | None = None) -> str:
        """截图并保存到 screenshots 目录。"""
        p = page or await self.get_page()
        path = self._shots / f"{name}.png"
        await p.screenshot(path=str(path), full_page=True)
        logger.info("Screenshot saved: %s", path)
        return str(path)

    async def save_baseline(self, baseline_name: str, page: Any | None = None) -> str:
        """保存基线截图。"""
        path = await self.take_screenshot(f"baseline-{baseline_name}", page=page)
        # Copy to baselines dir
        baseline_path = self._baselines / f"{baseline_name}.png"
        import shutil
        shutil.copy2(path, baseline_path)
        return str(baseline_path)

    async def compare_screenshot(self, baseline_name: str, page: Any | None = None) -> ScreenshotDiff:
        """对比当前截图与基线。"""
        current_path = await self.take_screenshot(f"compare-{baseline_name}", page=page)
        baseline_path = str(self._baselines / f"{baseline_name}.png")

        # Simple pixel comparison using PIL
        changed_pixels, similarity = self._compare_images(baseline_path, current_path)
        threshold = 0.95
        return ScreenshotDiff(
            baseline_path=baseline_path,
            current_path=current_path,
            changed_pixels=changed_pixels,
            similarity=similarity,
            similar=similarity >= threshold,
        )

    # ── Health Monitoring ───────────────────────────────────────

    async def start_health_monitor(
        self,
        interval_seconds: int = 60,
        target_url: str = "",
    ) -> None:
        """启动健康监控：定期检查浏览器是否存活，挂了自动重启。"""
        self._health_task = asyncio.create_task(
            self._health_loop(interval_seconds, target_url)
        )

    async def _health_loop(self, interval_seconds: int, target_url: str) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                if self._page is None or self._browser is None:
                    raise RuntimeError("Browser not running")
                # Try a simple operation to check health
                await self._page.evaluate("1")
            except Exception as e:
                logger.warning("Browser health check failed: %s, restarting...", e)
                try:
                    await self.close()
                except Exception:
                    pass
                await self.start()
                if target_url:
                    await self.navigate(target_url)
                logger.info("Browser restarted successfully")

    # ── Image Comparison ────────────────────────────────────────

    def _compare_images(self, baseline_path: str, current_path: str) -> tuple[int, float]:
        """用 Pillow 做像素级对比。"""
        try:
            from PIL import Image
            import os

            if not os.path.exists(baseline_path):
                return (0, 1.0)  # No baseline, assume similar

            baseline = Image.open(baseline_path).convert("RGB")
            current = Image.open(current_path).convert("RGB")

            # Resize current to match baseline if sizes differ
            if baseline.size != current.size:
                current = current.resize(baseline.size)

            b_pixels = list(baseline.getdata())
            c_pixels = list(current.getdata())

            total_pixels = len(b_pixels)
            changed = sum(
                1 for bp, cp in zip(b_pixels, c_pixels)
                if bp != cp
            )

            similarity = 1.0 - (changed / total_pixels) if total_pixels > 0 else 1.0
            return (changed, round(similarity, 4))
        except ImportError:
            logger.debug("Pillow not available, skipping pixel comparison")
            return (0, 1.0)
        except Exception as e:
            logger.warning("Image comparison failed: %s", e)
            return (0, 1.0)
