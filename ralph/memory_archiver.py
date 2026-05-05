"""MemoryArchiver — 三层记忆系统（短期/中期/长期）+ 关键词检索。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class MemoryArchiver:
    """记忆系统：短期→中期→长期三层 + 轻量关键词检索。

    短期: .ralph/memory/short_term.json (FIFO, max 20)
    中期: .ralph/memory/medium_term.json (关键决策, max 100)
    长期: .ralph/memory/long_term/ (完整日志, 按日期归档)
    """

    SHORT_TERM_MAX = 20
    MEDIUM_TERM_MAX = 100

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "memory"
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "long_term").mkdir(exist_ok=True)

    # --- Short-term ---

    def append_short_term(self, entry: dict) -> None:
        memory = self._read_short_term()
        entry["recorded_at"] = _now_iso()
        memory.append(entry)

        while len(memory) > self.SHORT_TERM_MAX:
            oldest = memory.pop(0)
            self._promote_to_medium(oldest)

        self._write_json("short_term.json", memory)

    def get_short_term(self) -> list[dict]:
        return self._read_short_term()

    def summarize_short_term(self) -> str:
        memory = self._read_short_term()
        if not memory:
            return "暂无近期活动"

        lines = []
        for entry in memory[-5:]:
            status = entry.get("status", "?")
            title = entry.get("title", entry.get("work_id", "?"))
            lines.append(f"- [{status}] {title}")

        statuses: dict[str, int] = {}
        for entry in memory:
            s = str(entry.get("status", "unknown"))
            statuses[s] = statuses.get(s, 0) + 1

        summary = f"近期任务 ({len(memory)}): "
        summary += ", ".join(f"{s}: {c}" for s, c in statuses.items())
        summary += "\n最近活动:\n" + "\n".join(lines)
        return summary

    # --- Medium-term ---

    def record_decision(self, decision: str, context: str,
                        alternatives: list[str] | None = None) -> None:
        memory = self._read_medium_term()
        # 标记之前相同主题的决策为 superseded
        for entry in memory:
            if (entry.get("type") == "decision"
                    and not entry.get("superseded_by")
                    and any(w in str(entry.get("decision", "")).lower()
                            for w in decision.lower().split()[:3])):
                entry["superseded_by"] = decision
                entry["superseded_at"] = _now_iso()
        memory.append({
            "type": "decision",
            "decision": decision,
            "context": context,
            "alternatives": alternatives or [],
            "superseded_by": None,
            "superseded_at": None,
            "recorded_at": _now_iso(),
        })
        if len(memory) > self.MEDIUM_TERM_MAX:
            memory = memory[-self.MEDIUM_TERM_MAX:]
        self._write_json("medium_term.json", memory)

    def get_medium_term(self) -> list[dict]:
        return self._read_medium_term()

    # --- Long-term ---

    def archive_task_log(self, work_id: str, full_log: str) -> str:
        date_str = _now_iso()[:10]
        archive_dir = self._dir / "long_term" / date_str
        archive_dir.mkdir(parents=True, exist_ok=True)
        path = archive_dir / f"{work_id}.md"
        path.write_text(full_log, encoding="utf-8")
        return str(path)

    def archive_compressed_summary(self, work_id: str, summary: dict) -> None:
        archive_dir = self._dir / "long_term" / _now_iso()[:10]
        archive_dir.mkdir(parents=True, exist_ok=True)
        path = archive_dir / f"{work_id}.summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    # --- Retrieval ---

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        query_lower = query.lower()
        results: list[dict] = []

        for entry in self._read_short_term():
            if query_lower in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"source": "short_term", "entry": entry, "score": 1.0})

        for entry in self._read_medium_term():
            if query_lower in json.dumps(entry, ensure_ascii=False).lower():
                results.append({"source": "medium_term", "entry": entry, "score": 0.8})

        return sorted(results, key=lambda r: r["score"], reverse=True)[:top_k]

    def get_status(self) -> dict:
        short = self._read_short_term()
        medium = self._read_medium_term()
        long_dir = self._dir / "long_term"

        long_count = 0
        if long_dir.is_dir():
            for d in long_dir.iterdir():
                if d.is_dir():
                    long_count += len(list(d.glob("*.md"))) + len(list(d.glob("*.json")))

        return {
            "short_term": {"count": len(short), "max": self.SHORT_TERM_MAX},
            "medium_term": {"count": len(medium), "max": self.MEDIUM_TERM_MAX},
            "long_term": {"count": long_count},
            "total_stored": len(short) + len(medium) + long_count,
            "last_updated": _now_iso(),
        }

    # --- Internal ---

    def _read_short_term(self) -> list[dict]:
        return self._read_json("short_term.json", [])

    def _read_medium_term(self) -> list[dict]:
        return self._read_json("medium_term.json", [])

    def _promote_to_medium(self, entry: dict) -> None:
        if entry.get("status") in ("accepted", "failed", "blocked"):
            memory = self._read_medium_term()
            entry["archived_from_short_term"] = True
            memory.append(entry)
            if len(memory) > self.MEDIUM_TERM_MAX:
                memory = memory[-self.MEDIUM_TERM_MAX:]
            self._write_json("medium_term.json", memory)

    def _read_json(self, filename: str, default=None) -> any:
        path = self._dir / filename
        if not path.is_file():
            return default if default is not None else []
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return default if default is not None else []

    def _write_json(self, filename: str, data) -> None:
        (self._dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
        )
