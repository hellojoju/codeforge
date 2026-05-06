"""ConcurrencyController — Semaphore + TokenBudget 并发控制。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    """日 token 预算控制。"""

    daily_limit: int = 1_000_000
    used_today: int = 0
    last_reset_date: str = field(default_factory=lambda: datetime.now(UTC).isoformat()[:10])

    def reset_if_new_day(self) -> None:
        today = datetime.now(UTC).isoformat()[:10]
        if today != self.last_reset_date:
            self.used_today = 0
            self.last_reset_date = today

    def can_spend(self, estimated_tokens: int) -> bool:
        self.reset_if_new_day()
        return self.used_today + estimated_tokens <= self.daily_limit

    def record_usage(self, tokens: int) -> None:
        self.reset_if_new_day()
        self.used_today += tokens

    def remaining(self) -> int:
        self.reset_if_new_day()
        return max(0, self.daily_limit - self.used_today)

    def to_dict(self) -> dict[str, Any]:
        self.reset_if_new_day()
        return {
            "daily_limit": self.daily_limit,
            "used_today": self.used_today,
            "remaining": self.remaining(),
            "date": self.last_reset_date,
        }


class ConcurrencyController:
    """asyncio.Semaphore 限制并发数 + TokenBudget 日预算控制。"""

    def __init__(self, max_concurrent: int = 3, daily_token_limit: int = 1_000_000):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._budget = TokenBudget(daily_limit=daily_token_limit)
        self._max_concurrent = max_concurrent
        self._active: dict[str, datetime] = {}

    async def acquire(self, work_id: str, estimated_tokens: int = 0) -> bool:
        """获取执行槽位。

        Args:
            work_id: 工作单元 ID
            estimated_tokens: 预估 token 用量

        Returns:
            True 如果获得了槽位，False 如果预算不足
        """
        if not self._budget.can_spend(estimated_tokens):
            logger.warning(
                "ConcurrencyController: token budget exceeded for %s "
                "(remaining=%d, estimated=%d)",
                work_id,
                self._budget.remaining(),
                estimated_tokens,
            )
            return False

        await self._semaphore.acquire()
        self._active[work_id] = datetime.now(UTC)
        logger.info(
            "ConcurrencyController: acquired slot for %s (active=%d/%d)",
            work_id,
            len(self._active),
            self._max_concurrent,
        )
        return True

    def release(self, work_id: str) -> None:
        """释放执行槽位。"""
        self._semaphore.release()
        self._active.pop(work_id, None)
        logger.info(
            "ConcurrencyController: released slot for %s (active=%d/%d)",
            work_id,
            len(self._active),
            self._max_concurrent,
        )

    def record_usage(self, work_id: str, tokens: int) -> None:
        """记录 token 用量。"""
        self._budget.record_usage(tokens)

    @property
    def budget(self) -> TokenBudget:
        return self._budget

    @property
    def active_count(self) -> int:
        return len(self._active)

    def status(self) -> dict[str, Any]:
        return {
            "max_concurrent": self._max_concurrent,
            "active_count": self.active_count,
            "active_work_units": list(self._active.keys()),
            "budget": self._budget.to_dict(),
        }
