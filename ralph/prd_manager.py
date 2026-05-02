"""PRDManager — 从 BrainstormRecord 生成结构化 PRD，管理冻结流程。"""

from __future__ import annotations

import json
from pathlib import Path

from ralph.schema.prd_document import PRDDocument, _now_iso
from ralph.brainstorm_manager import BrainstormManager


class PRDManager:
    """从需求共创记录生成 PRD，管理冻结/变更流程。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "prd"
        self._dir.mkdir(parents=True, exist_ok=True)

    def generate_from_brainstorm(
        self, brainstorm_record_id: str, ralph_dir: Path,
    ) -> PRDDocument:
        """从需求共创记录生成 PRD 草案。"""
        brainstorm_mgr = BrainstormManager(ralph_dir)
        record = brainstorm_mgr.load(brainstorm_record_id)
        if record is None:
            raise ValueError(f"Brainstorm record {brainstorm_record_id} not found")

        summary = brainstorm_mgr.get_summary(record)

        prd = PRDDocument(
            prd_id=f"prd-{_now_iso().replace(':', '-')}",
            project_name=summary["project_name"],
            brainstorm_record_id=brainstorm_record_id,
        )

        # 从 facts 映射到 PRD 章节（含追溯关系 source_facts）
        prd.user_goal_sources = []
        prd.feature_sources = []
        prd.scope_sources = []
        prd.criteria_sources = []

        for fact in summary["confirmed_facts"]:
            topic, content = fact["topic"], fact["fact"]
            if topic == "目标用户":
                prd.user_goals.append(f"目标用户: {content}")
                prd.user_goal_sources.append(topic)
            elif topic == "核心功能":
                prd.core_features.append({"name": content, "description": ""})
                prd.feature_sources.append(topic)
            elif topic == "暂不做的功能":
                prd.out_of_scope.append(content)
                prd.scope_sources.append(topic)
            elif topic == "验收标准":
                prd.success_criteria.append(content)
                prd.criteria_sources.append(topic)
            elif topic == "权限规则":
                prd.non_functional["权限"] = content
            elif topic == "数据模型概要":
                prd.non_functional["数据模型"] = content
            elif topic == "成功路径":
                prd.core_workflow += f"\n成功路径: {content}"

        for assumption in summary["open_assumptions"]:
            prd.open_questions.append(assumption["question"])

        self._save(prd)
        return prd

    def enrich_with_llm(self, prd: PRDDocument, llm_response: dict) -> PRDDocument:
        """用 LLM 返回的结构化内容填充 PRD 各章节。"""
        prd.background = llm_response.get("background", prd.background)
        prd.product_positioning = llm_response.get(
            "product_positioning", prd.product_positioning,
        )
        prd.core_workflow = llm_response.get("core_workflow", prd.core_workflow)
        if "core_features" in llm_response:
            prd.core_features = llm_response["core_features"]
        if "non_functional" in llm_response:
            prd.non_functional.update(llm_response["non_functional"])
        if "success_criteria" in llm_response:
            prd.success_criteria = llm_response["success_criteria"]
        if "risks" in llm_response:
            prd.risks = llm_response["risks"]
        self._save(prd)
        return prd

    def freeze(self, prd_id: str) -> PRDDocument:
        prd = self.load(prd_id)
        if prd is None:
            raise ValueError(f"PRD {prd_id} not found")
        prd.freeze()
        self._save(prd)
        return prd

    def load(self, prd_id: str) -> PRDDocument | None:
        path = self._dir / f"{prd_id}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text())
        return PRDDocument(**data)

    def list_prds(self) -> list[dict]:
        prds = []
        for f in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text())
                prds.append({
                    "prd_id": data.get("prd_id", f.stem),
                    "project_name": data.get("project_name", ""),
                    "version": data.get("version", ""),
                    "status": data.get("status", "draft"),
                    "created_at": data.get("created_at", ""),
                })
            except Exception:
                continue
        return prds

    def _save(self, prd: PRDDocument) -> None:
        path = self._dir / f"{prd.prd_id}.json"
        path.write_text(json.dumps(
            {k: v for k, v in prd.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
