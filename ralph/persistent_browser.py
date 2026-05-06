from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScreenshotDiff:
    baseline_path: str
    current_path: str
    changed_pixels: int = 0
    similar: bool = True

    def to_dict(self) -> dict:
        return {
            "baseline_path": self.baseline_path,
            "current_path": self.current_path,
            "changed_pixels": self.changed_pixels,
            "similar": self.similar,
        }


class _MockPage:
    async def goto(self, url: str, wait_until: str = "networkidle") -> None:
        _ = (url, wait_until)
        await asyncio.sleep(0)

    async def click(self, selector: str) -> None:
        _ = selector
        await asyncio.sleep(0)

    async def fill(self, selector: str, value: str) -> None:
        _ = (selector, value)
        await asyncio.sleep(0)


class PersistentBrowser:
    def __init__(self, user_data_dir: str | Path):
        self._dir = Path(user_data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._shots = self._dir / "screenshots"
        self._shots.mkdir(parents=True, exist_ok=True)
        self._page = _MockPage()

    async def start(self) -> None:
        await asyncio.sleep(0)

    async def close(self) -> None:
        await asyncio.sleep(0)

    async def start_health_monitor(self, interval_seconds: int = 60, target_url: str = "") -> None:
        _ = (interval_seconds, target_url)
        await asyncio.sleep(0)

    async def get_page(self) -> _MockPage:
        await asyncio.sleep(0)
        return self._page

    async def take_screenshot(self, name: str, page: _MockPage | None = None) -> str:
        _ = page
        path = self._shots / f"{name}.png"
        path.write_bytes(b"")
        await asyncio.sleep(0)
        return str(path)

    async def save_baseline(self, baseline_name: str, page: _MockPage | None = None) -> str:
        return await self.take_screenshot(f"baseline-{baseline_name}", page=page)

    async def compare_screenshot(self, baseline_name: str, page: _MockPage | None = None) -> ScreenshotDiff:
        current = await self.take_screenshot(f"compare-{baseline_name}", page=page)
        baseline = str(self._shots / f"baseline-{baseline_name}.png")
        return ScreenshotDiff(baseline_path=baseline, current_path=current, changed_pixels=0, similar=True)
