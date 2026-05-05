"""Dashboard 数据模型 — 薄层 re-export，权威定义在 core.state_models。"""

from core.state_models import (
    AgentInstance,
    ApprovalRequest,
    BlockingIssue,
    BlockingStatus,
    BlockingType,
    ChatMessage,
    Command,
    CommandStatus,
    DashboardState,
    Event,
    Feature,
    FeatureStatus,
    ModuleAssignment,
    ModuleStatus,
    Snapshot,
)

__all__ = [
    "AgentInstance",
    "ApprovalRequest",
    "BlockingIssue",
    "BlockingStatus",
    "BlockingType",
    "ChatMessage",
    "Command",
    "CommandStatus",
    "DashboardState",
    "Event",
    "Feature",
    "FeatureStatus",
    "ModuleAssignment",
    "ModuleStatus",
    "Snapshot",
]
