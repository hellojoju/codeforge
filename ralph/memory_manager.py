from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository
from ralph.schema.retro_record import Lesson, RetroRecord
from ralph.taste_memory import TasteMemory


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class _RetroService:
    def auto_tune_params(self, keywords: list[str]) -> dict[str, Any]:
        text = " ".join(k.lower() for k in keywords if isinstance(k, str))
        tuning: dict[str, Any] = {}
        if "timeout" in text:
            tuning["timeout_multiplier"] = 1.5
        if "rework" in text or "返工" in text:
            tuning["enable_intermediate_checks"] = True
        if "scope" in text or "边界" in text:
            tuning["strict_scope_enforcement"] = True
        return tuning

    def create_follow_up_work_units(self, retro_record: dict[str, Any]) -> list[dict[str, Any]]:
        improvements = retro_record.get("improvements", []) if isinstance(retro_record, dict) else []
        result = []
        for i, item in enumerate(improvements[:3], start=1):
            result.append(
                {
                    "work_id": f"fu-{retro_record.get('feature_id', 'unknown')}-{i}",
                    "title": f"Follow-up {i}",
                    "description": item,
                }
            )
        return result


class MemoryManager:
    def __init__(self, ralph_dir: Path | str, project_dir: Path | None = None):
        self._ralph_dir = Path(ralph_dir)
        self._project_dir = Path(project_dir) if project_dir else self._ralph_dir.parent
        self._mem_dir = self._ralph_dir / "memory"
        self._mem_dir.mkdir(parents=True, exist_ok=True)
        self._repo = RalphRepository(self._ralph_dir)
        self._taste = TasteMemory(self._ralph_dir)
        self._retro_service = _RetroService()
        self._thresholds_path = self._mem_dir / "thresholds.json"
        self._thresholds = self._load_thresholds()

    @property
    def thresholds(self) -> dict[str, Any]:
        return dict(self._thresholds)

    def _load_thresholds(self) -> dict[str, Any]:
        defaults = {
            "max_context_items": 20,
            "retro_auto_tune": True,
            "taste_confidence_threshold": 0.6,
        }
        if not self._thresholds_path.is_file():
            return defaults
        try:
            data = json.loads(self._thresholds_path.read_text(encoding="utf-8"))
            return {**defaults, **(data if isinstance(data, dict) else {})}
        except (json.JSONDecodeError, OSError):
            return defaults

    def update_thresholds(self, body: dict[str, Any]) -> None:
        self._thresholds.update(body)
        self._thresholds_path.write_text(
            json.dumps(self._thresholds, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def record_taste(
        self,
        *,
        taste_id: str,
        preference_type: str,
        category: str,
        description: str,
        source: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not description.strip():
            return None
        return self._taste.upsert(
            {
                "id": taste_id,
                "preference_type": preference_type,
                "category": category,
                "description": description,
                "source": source,
                "confidence": confidence,
                "metadata": metadata or {},
            }
        )

    def get_status(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "tastes_count": len(self._taste.get_all()),
            "retros_count": len(self.get_recent_retros(500)),
            "thresholds": self.thresholds,
        }

    def search(self, q: str, top_k: int = 10) -> list[dict[str, Any]]:
        query = q.strip().lower()
        if not query:
            return []

        result: list[dict[str, Any]] = []
        for t in self._taste.get_all():
            text = f"{t.get('category', '')} {t.get('description', '')}".lower()
            score = text.count(query)
            if score:
                result.append({"type": "taste", "score": score, "item": t})

        for r in self.get_recent_retros(200):
            text = f"{r.get('summary', '')} {' '.join(r.get('improvements', []))}".lower()
            score = text.count(query)
            if score:
                result.append({"type": "retro", "score": score, "item": r})

        result.sort(key=lambda x: x["score"], reverse=True)
        return result[: max(1, top_k)]

    def get_l1_snapshot(self, active_work_units: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "active_count": len(active_work_units),
            "active_work_units": active_work_units[:20],
            "top_tastes": self._taste.get_all()[:10],
            "generated_at": _now_iso(),
        }

    def on_work_unit_completed(self, work_unit: dict[str, Any], exec_log: str = "") -> dict[str, Any]:
        feature_id = work_unit.get("work_id") or work_unit.get("feature_id", "")
        improvements = []
        if "timeout" in exec_log.lower():
            improvements.append("增加 timeout 并优化前置检查")
        if work_unit.get("status") in ("failed", "blocked"):
            improvements.append("补充失败分类与重试策略")
        if not improvements:
            improvements.append("保持当前执行策略并补充回归验证")

        summary = f"WorkUnit {feature_id} 状态: {work_unit.get('status', 'unknown')}"
        record = RetroRecord(
            feature_id=feature_id,
            retro_id=f"retro-{feature_id}",
            summary=summary,
            lessons=[
                Lesson(
                    lesson_id=f"retro-{feature_id}-l1",
                    category="optimization",
                    content=improvements[0],
                )
            ],
            what_went_well=["执行链路已形成闭环"],
            what_went_wrong=[work_unit.get("error", "")] if work_unit.get("error") else [],
            improvements=improvements,
        )
        self._repo.save_retro(record)
        return {
            "feature_id": feature_id,
            "summary": summary,
            "improvements": improvements,
            "created_at": _now_iso(),
        }

    def trigger_retro(self, work_unit: dict[str, Any], exec_log: str = "") -> dict[str, Any]:
        return self.on_work_unit_completed(work_unit, exec_log)

    def get_recent_retros(self, limit: int = 10) -> list[dict[str, Any]]:
        result = []
        for r in self._repo.list_retros(limit=limit):
            data = asdict(r)
            data["lessons"] = [asdict(x) for x in r.lessons]
            result.append(data)
        return result

    def get_retro_summary(self, period: str = "week") -> dict[str, Any]:
        days = 7 if period == "week" else 30
        threshold = datetime.now(UTC) - timedelta(days=days)
        selected = [
            r for r in self.get_recent_retros(500) if r.get("created_at", _now_iso()) >= threshold.isoformat()
        ]
        return {
            "period": period,
            "count": len(selected),
            "total_improvements": sum(len(r.get("improvements", [])) for r in selected),
            "generated_at": _now_iso(),
        }

    def get_taste_context(self) -> str:
        tastes = self._taste.get_all()[:5]
        return "\n".join(f"- {t.get('category', 'overall')}: {t.get('description', '')}" for t in tastes)

    def close(self) -> None:
        return
