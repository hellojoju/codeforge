from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ralph.repository import RalphRepository


class ContextLayer(Enum):
    L0 = "project_meta"
    L1 = "structured_index"
    L2 = "graph_retrieval"
    L3 = "semantic_retrieval"


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int = 8000
    # rough token estimation: 1 token ~ 4 chars for English
    chars_per_token: int = 4

    def estimate_tokens(self, text: str) -> int:
        return len(text) // self.chars_per_token


@dataclass
class LayerOutput:
    layer: ContextLayer
    content: str
    token_count: int = 0


class ContextEngine:
    def __init__(self, project_dir: Path | str):
        self._project_dir = Path(project_dir)
        self._ralph_dir = self._project_dir / ".ralph"
        self._repo = RalphRepository(self._ralph_dir)
        self._budget = ContextBudget()

    # ── Public API ──────────────────────────────────────────────

    def build_initial(
        self,
        *,
        work_id: str = "",
        layers: set[ContextLayer] | None = None,
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """首轮上下文构建：L0 + L1 + L2（不含历史）。"""
        target_layers = layers or {ContextLayer.L0, ContextLayer.L1, ContextLayer.L2}
        budget = ContextBudget(max_tokens=max_tokens)

        outputs: list[LayerOutput] = []
        if ContextLayer.L0 in target_layers:
            outputs.append(self._build_l0())
        if ContextLayer.L1 in target_layers:
            outputs.append(self._build_l1(work_id=work_id))
        if ContextLayer.L2 in target_layers:
            outputs.append(self._build_l2(work_id=work_id))

        return self._assemble(outputs, budget)

    def build_incremental(
        self,
        *,
        work_id: str,
        checkpoint: int | None = None,
        current_error: str = "",
        next_goal: str = "",
        include_l2: bool = True,
        include_l3: bool = True,
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """增量上下文：上一轮 checkpoint + 本轮目标 + L2/L3 按需。"""
        budget = ContextBudget(max_tokens=max_tokens)

        # Load checkpoint data
        checkpoint_data = self._load_checkpoint(work_id, checkpoint)

        outputs: list[LayerOutput] = []

        # Always include checkpoint state
        checkpoint_text = json.dumps(checkpoint_data, ensure_ascii=False) if checkpoint_data else ""
        if checkpoint_text:
            outputs.append(
                LayerOutput(
                    layer=ContextLayer.L1,
                    content=f"Previous checkpoint state:\n{checkpoint_text}",
                    token_count=budget.estimate_tokens(checkpoint_text),
                )
            )

        # Add current error and next goal
        if current_error or next_goal:
            goal_text = f"Current error: {current_error}\nNext goal: {next_goal}"
            outputs.append(
                LayerOutput(
                    layer=ContextLayer.L1,
                    content=goal_text,
                    token_count=budget.estimate_tokens(goal_text),
                )
            )

        if include_l2:
            outputs.append(self._build_l2(work_id=work_id))
        if include_l3:
            outputs.append(self._build_l3(query=next_goal or work_id))

        return self._assemble(outputs, budget)

    # ── Layer Builders ─────────────────────────────────────────

    def _build_l0(self) -> LayerOutput:
        """L0: 项目元信息（路径、分支、文件树、最近 git log）。"""
        lines: list[str] = []
        lines.append(f"Project directory: {self._project_dir}")

        # Current branch
        try:
            branch = subprocess.check_output(
                ["git", "-C", str(self._project_dir), "branch", "--show-current"],
                text=True,
                timeout=5,
            ).strip()
            lines.append(f"Current branch: {branch}")
        except (subprocess.SubprocessError, FileNotFoundError):
            lines.append("Current branch: unknown")

        # Recent git log (last 5 commits)
        try:
            log = subprocess.check_output(
                ["git", "-C", str(self._project_dir), "log", "--oneline", "-5"],
                text=True,
                timeout=5,
            ).strip()
            lines.append(f"Recent commits:\n{log}")
        except (subprocess.SubprocessError, FileNotFoundError):
            lines.append("Recent commits: unavailable")

        # Top-level file tree (depth 2)
        try:
            tree = subprocess.check_output(
                ["find", str(self._project_dir), "-maxdepth", "2", "-not", "-path", "*/node_modules/*", "-not", "-path", "*/.git/*", "-not", "-path", "*/.next/*", "-not", "-path", "*/__pycache__/*"],
                text=True,
                timeout=10,
            ).strip()
            lines.append(f"File tree (depth 2):\n{tree}")
        except (subprocess.SubprocessError, FileNotFoundError):
            lines.append("File tree: unavailable")

        content = "\n".join(lines)
        return LayerOutput(layer=ContextLayer.L0, content=content, token_count=self._budget.estimate_tokens(content))

    def _build_l1(self, *, work_id: str = "") -> LayerOutput:
        """L1: 结构化索引（WorkUnit 列表、依赖图、当前状态快照）。"""
        lines: list[str] = []

        # WorkUnit summary
        work_units = self._repo.list_work_units()
        lines.append(f"Total work units: {len(work_units)}")

        by_status: dict[str, list[str]] = {}
        for wu in work_units:
            by_status.setdefault(wu.status.value, []).append(wu.work_id)

        for status, ids in sorted(by_status.items()):
            lines.append(f"  {status}: {', '.join(ids[:10])}{'...' if len(ids) > 10 else ''}")

        # Features summary
        try:
            features = self._repo.list_features()
            lines.append(f"Total features: {len(features)}")
            for f in features[:5]:
                lines.append(f"  {f.feature_id}: {f.title} [{f.status.value}]")
        except Exception:
            pass

        # Blocking issues
        try:
            blockers = self._repo.list_blocking_issues()
            unresolved = [b for b in blockers if b.status.value != "resolved"]
            if unresolved:
                lines.append(f"Unresolved blockers: {len(unresolved)}")
                for b in unresolved[:5]:
                    lines.append(f"  - {b.blocking_id}: {b.title}")
        except Exception:
            pass

        # Target work unit detail
        if work_id:
            wu = self._repo.get_work_unit(work_id)
            if wu:
                lines.append(f"\nTarget work unit [{work_id}]:")
                lines.append(f"  title: {wu.title}")
                lines.append(f"  status: {wu.status.value}")
                lines.append(f"  target: {wu.target[:300]}")

        content = "\n".join(lines)
        return LayerOutput(layer=ContextLayer.L1, content=content, token_count=self._budget.estimate_tokens(content))

    def _build_l2(self, *, work_id: str = "") -> LayerOutput:
        """L2: 知识图谱检索（影响范围、关联风险）。"""
        lines: list[str] = []
        graph_data = self._repo.snapshot().get("state_snapshot", {})

        if work_id:
            # Try to find related work units via scope overlap
            wu = self._repo.get_work_unit(work_id)
            if wu:
                scope = [str(p) for p in (wu.scope_allow or [])]
                if scope:
                    lines.append(f"Work unit {work_id} scope: {', '.join(scope)}")
                    related = []
                    for other in self._repo.list_work_units():
                        if other.work_id == work_id:
                            continue
                        other_scope = [str(p) for p in (other.scope_allow or [])]
                        overlap = set(scope) & set(other_scope)
                        if overlap:
                            related.append(f"  {other.work_id} ({other.status.value}) shares: {', '.join(list(overlap)[:3])}")
                    if related:
                        lines.append(f"Related work units ({len(related)}):")
                        lines.extend(related[:10])

        # Knowledge graph status
        kg_path = self._ralph_dir / "state" / "knowledge_graph.json"
        if kg_path.is_file():
            try:
                kg = json.loads(kg_path.read_text(encoding="utf-8"))
                lines.append(f"Knowledge graph: {len(kg.get('nodes', []))} nodes, {len(kg.get('edges', []))} edges")
            except (json.JSONDecodeError, OSError):
                lines.append("Knowledge graph: corrupted")
        else:
            lines.append("Knowledge graph: not yet built")

        content = "\n".join(lines)
        return LayerOutput(layer=ContextLayer.L2, content=content, token_count=self._budget.estimate_tokens(content))

    def _build_l3(self, *, query: str = "") -> LayerOutput:
        """L3: 语义检索（历史决策、retro 教训）。"""
        lines: list[str] = []
        query_lower = query.lower() if query else ""

        if not query_lower:
            lines.append("No query provided for semantic retrieval.")
            content = "\n".join(lines)
            return LayerOutput(layer=ContextLayer.L3, content=content, token_count=0)

        # Search retros
        retros = self._repo.list_retros(limit=50)
        matches = []
        for retro in retros:
            text = f"{retro.summary} {' '.join(lesson.content for lesson in retro.lessons)}".lower()
            if query_lower in text:
                matches.append(f"  retro[{retro.retro_id}]: {retro.summary}")
                for lesson in retro.lessons[:3]:
                    matches.append(f"    - [{lesson.severity}] {lesson.content[:150]}")

        if matches:
            lines.append(f"Retrospective matches ({len(matches)}):")
            lines.extend(matches[:10])
        else:
            lines.append("No retro matches found.")

        # Search work units by title/target
        work_units = self._repo.list_work_units()
        wu_matches = []
        for wu in work_units:
            text = f"{wu.title} {wu.target}".lower()
            if query_lower in text:
                wu_matches.append(f"  work_unit[{wu.work_id}]: {wu.title} [{wu.status.value}]")

        if wu_matches:
            lines.append(f"Work unit matches ({len(wu_matches)}):")
            lines.extend(wu_matches[:5])

        content = "\n".join(lines)
        return LayerOutput(layer=ContextLayer.L3, content=content, token_count=self._budget.estimate_tokens(content))

    # ── Assembly & Budget Control ───────────────────────────────

    def _assemble(self, outputs: list[LayerOutput], budget: ContextBudget) -> dict[str, Any]:
        """按预算组装上下文，超出时按 L3→L2→L1 优先级裁剪。"""
        # Priority order for trimming: L3 first, then L2, then L1, L0 last
        layer_priority = {ContextLayer.L3: 0, ContextLayer.L2: 1, ContextLayer.L1: 2, ContextLayer.L0: 3}
        outputs.sort(key=lambda o: layer_priority.get(o.layer, 0))

        # Calculate total tokens
        total_tokens = sum(o.token_count for o in outputs)

        # Trim if over budget
        while total_tokens > budget.max_tokens and outputs:
            # Trim from lowest priority
            removed = outputs.pop(0)
            total_tokens -= removed.token_count

        sections: dict[str, list[str]] = {}
        for output in outputs:
            sections.setdefault(output.layer.value, []).append(output.content)

        return {
            "layers": {k: "\n\n".join(v) for k, v in sections.items()},
            "total_tokens_estimated": total_tokens,
            "budget": budget.max_tokens,
            "trimmed": total_tokens < sum(o.token_count for o in outputs),
        }

    # ── Checkpoint Helpers ──────────────────────────────────────

    def _load_checkpoint(self, work_id: str, checkpoint: int | None = None) -> dict | None:
        checkpoint_dir = self._project_dir / ".ralph" / "checkpoints"
        if not checkpoint_dir.is_dir():
            return None

        checkpoint_file = None
        if checkpoint is not None:
            p = checkpoint_dir / f"{work_id}.turn-{checkpoint}.json"
            if p.is_file():
                checkpoint_file = p
        else:
            matched = sorted(checkpoint_dir.glob(f"{work_id}.turn-*.json"))
            if matched:
                checkpoint_file = matched[-1]

        if checkpoint_file and checkpoint_file.is_file():
            try:
                return json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return None

    # ── Legacy compatibility ────────────────────────────────────

    def build_pm_context(
        self,
        *,
        mode: str,
        active_work_units: list[dict[str, Any]],
        pending_decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "mode": mode,
            "project_dir": str(self._project_dir),
            "active_work_units": active_work_units,
            "pending_decisions": pending_decisions or [],
            "state_snapshot": self._repo.snapshot(),
        }
