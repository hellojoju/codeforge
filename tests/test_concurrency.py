"""并发控制测试 — Semaphore + TokenBudget + ConcurrencyController。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from ralph.concurrency_controller import ConcurrencyController, TokenBudget


class TestTokenBudget:
    """TokenBudget 日预算控制。"""

    def test_default_limit(self) -> None:
        budget = TokenBudget()
        assert budget.daily_limit == 1_000_000
        assert budget.used_today == 0

    def test_custom_limit(self) -> None:
        budget = TokenBudget(daily_limit=5000)
        assert budget.daily_limit == 5000

    def test_can_spend_within_limit(self) -> None:
        budget = TokenBudget(daily_limit=10000)
        assert budget.can_spend(5000) is True
        budget.record_usage(5000)
        assert budget.used_today == 5000
        assert budget.can_spend(5000) is True  # exactly at limit

    def test_can_spend_exceeds_limit(self) -> None:
        budget = TokenBudget(daily_limit=10000)
        budget.record_usage(9000)
        assert budget.can_spend(2000) is False

    def test_remaining(self) -> None:
        budget = TokenBudget(daily_limit=10000)
        assert budget.remaining() == 10000
        budget.record_usage(3000)
        assert budget.remaining() == 7000

    def test_reset_if_new_day(self) -> None:
        budget = TokenBudget(daily_limit=10000)
        budget.record_usage(5000)
        # Simulate new day by setting last_reset_date to yesterday
        budget.last_reset_date = "2020-01-01"
        budget.reset_if_new_day()
        assert budget.used_today == 0
        assert budget.last_reset_date == datetime.now(UTC).isoformat()[:10]

    def test_to_dict(self) -> None:
        budget = TokenBudget(daily_limit=50000)
        d = budget.to_dict()
        assert d["daily_limit"] == 50000
        assert d["used_today"] == 0
        assert "remaining" in d
        assert "date" in d


class TestConcurrencyController:
    """ConcurrencyController 并发控制。"""

    def test_initial_status(self) -> None:
        cc = ConcurrencyController(max_concurrent=3, daily_token_limit=100000)
        status = cc.status()
        assert status["max_concurrent"] == 3
        assert status["active_count"] == 0
        assert status["active_work_units"] == []

    def test_acquire_release(self) -> None:
        async def _test() -> None:
            cc = ConcurrencyController(max_concurrent=2)
            assert await cc.acquire("wu-1") is True
            assert cc.active_count == 1

            assert await cc.acquire("wu-2") is True
            assert cc.active_count == 2

            cc.release("wu-1")
            assert cc.active_count == 1

            cc.release("wu-2")
            assert cc.active_count == 0

        asyncio.run(_test())

    def test_token_budget_exceeded(self) -> None:
        async def _test() -> None:
            cc = ConcurrencyController(max_concurrent=2, daily_token_limit=100)
            cc._budget.record_usage(90)
            # estimated_tokens=20 would exceed budget
            assert await cc.acquire("wu-blk", estimated_tokens=20) is False
            assert cc.active_count == 0

        asyncio.run(_test())

    def test_acquire_exceeding_semaphore_blocks(self) -> None:
        async def _test() -> None:
            cc = ConcurrencyController(max_concurrent=1)
            assert await cc.acquire("wu-1") is True

            # Second acquire should block (we don't await it fully)
            acquire_task = asyncio.create_task(cc.acquire("wu-2"))
            # Give it a moment to try
            await asyncio.sleep(0.05)
            assert not acquire_task.done()  # still waiting

            cc.release("wu-1")
            await asyncio.sleep(0.05)
            assert acquire_task.done()
            assert await acquire_task is True

            cc.release("wu-2")

        asyncio.run(_test())

    def test_record_usage(self) -> None:
        cc = ConcurrencyController(max_concurrent=2, daily_token_limit=10000)
        cc.record_usage("wu-1", 3000)
        assert cc._budget.used_today == 3000

    def test_budget_property(self) -> None:
        cc = ConcurrencyController(max_concurrent=2)
        assert isinstance(cc.budget, TokenBudget)
        assert cc.budget.daily_limit == 1_000_000

    def test_acquire_and_record(self) -> None:
        async def _test() -> None:
            cc = ConcurrencyController(max_concurrent=3, daily_token_limit=50000)
            assert await cc.acquire("wu-abc", estimated_tokens=1000) is True
            cc.record_usage("wu-abc", 800)
            assert cc._budget.used_today == 800
            assert cc.active_count == 1
            cc.release("wu-abc")

        asyncio.run(_test())

    def test_status_reflects_active(self) -> None:
        async def _test() -> None:
            cc = ConcurrencyController(max_concurrent=2)
            assert await cc.acquire("wu-x") is True
            status = cc.status()
            assert status["active_count"] == 1
            assert "wu-x" in status["active_work_units"]
            cc.release("wu-x")

        asyncio.run(_test())
