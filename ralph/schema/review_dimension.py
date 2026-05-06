"""ReviewDimension — 多维度审查配置。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DimensionResult:
    """单个审查维度的评审结果。"""

    dimension: str = ""
    passed: bool = True
    score: float = 1.0
    notes: str = ""


@dataclass(frozen=True)
class ReviewDimensionConfig:
    """审查维度配置。"""

    name: str = ""
    weight: float = 1.0
    enabled: bool = True
    description: str = ""
