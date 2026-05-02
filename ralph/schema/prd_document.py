"""PRD 文档数据结构。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class PRDDocument:
    prd_id: str
    project_name: str
    version: str = "1.0-draft"
    status: str = "draft"  # draft | frozen | archived

    # 核心章节
    background: str = ""
    product_positioning: str = ""
    user_goals: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    core_workflow: str = ""
    core_features: list[dict] = field(default_factory=list)
    non_functional: dict = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)

    # 元信息
    brainstorm_record_id: str = ""
    created_at: str = field(default_factory=_now_iso)
    frozen_at: str = ""

    def freeze(self) -> None:
        self.status = "frozen"
        self.frozen_at = _now_iso()

    def is_frozen(self) -> bool:
        return self.status == "frozen"

    def to_markdown(self) -> str:
        sections = [
            f"# {self.project_name} PRD",
            f"版本: {self.version} | 状态: {self.status}",
            "",
            "## 背景", self.background,
            "## 产品定位", self.product_positioning,
            "## 用户目标", *[f"- {g}" for g in self.user_goals],
            "## 不做什么", *[f"- {s}" for s in self.out_of_scope],
            "## 核心流程", self.core_workflow,
            "## 核心功能",
        ]
        for f in self.core_features:
            sections.append(f"- **{f.get('name', '')}**: {f.get('description', '')}")
        sections += [
            "## 非功能需求",
            *[f"- {k}: {v}" for k, v in self.non_functional.items()],
            "## 成功标准", *[f"- {c}" for c in self.success_criteria],
            "## 风险", *[f"- {r}" for r in self.risks],
            "## 待确认问题", *[f"- {q}" for q in self.open_questions],
        ]
        return "\n".join(sections)
