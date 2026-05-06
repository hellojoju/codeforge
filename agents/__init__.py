"""Agents包 - 各角色AI工程师"""

import importlib
from pathlib import Path

from core.ralph_paths import resolve_ralph_dir

from agents.architect import Architect
from agents.backend_dev import BackendDeveloper
from agents.base_agent import BaseAgent, DynamicAgent
from agents.database_expert import DatabaseExpert
from agents.docs_writer import DocsWriter
from agents.frontend_dev import FrontendDeveloper
from agents.product_manager import ProductManager
from agents.qa_tester import QATester
from agents.review_agent import ReviewAgent
from agents.security_reviewer import SecurityReviewer
from agents.ui_designer import UIDesigner

# 角色 -> Agent类 映射（保留用于特例角色，如 ProductManager 有 chat_response 方法）
AGENT_REGISTRY = {
    "backend": BackendDeveloper,
    "frontend": FrontendDeveloper,
    "qa": QATester,
    "product": ProductManager,
    "ui_designer": UIDesigner,
    "database": DatabaseExpert,
    "security": SecurityReviewer,
    "docs": DocsWriter,
    "architect": Architect,
    "reviewer": ReviewAgent,
}


def _load_config_manager():
    cfg_mod = importlib.import_module("ralph.config_manager")
    return getattr(cfg_mod, "RalphConfigManager")


def _load_agent_roles() -> dict[str, str]:
    """从配置动态构建角色中文名映射。"""
    try:
        RalphConfigManager = _load_config_manager()
        cfg = RalphConfigManager(resolve_ralph_dir(Path(project_dir)))
        defs = cfg.list_agent_definitions()
        return {d["role"]: d.get("display_name", d["role"]) for d in defs}
    except Exception:
        # 回退到硬编码
        return {
            "backend": "后端开发工程师",
            "frontend": "前端开发工程师",
            "database": "数据库专家",
            "qa": "QA测试工程师",
            "product": "产品经理",
            "ui_designer": "UI/UX设计师",
            "security": "安全工程师",
            "docs": "技术文档工程师",
            "architect": "系统架构师",
            "reviewer": "评审工程师",
        }


# 角色中文名映射（动态加载 + 回退）
AGENT_ROLES = _load_agent_roles()


def get_agent(role: str, project_dir):
    """根据角色获取对应的Agent实例。

    优先从 AGENT_REGISTRY 查找（支持 ProductManager 等有特殊方法的类），
    否则从 JSON 配置动态创建 DynamicAgent。
    """
    agent_cls = AGENT_REGISTRY.get(role)
    if agent_cls is not None:
        return agent_cls(Path(project_dir))

    # 动态角色：从配置加载
    try:
        RalphConfigManager = _load_config_manager()
        cfg = RalphConfigManager(resolve_ralph_dir(Path(project_dir)))
        defs = cfg.list_agent_definitions_raw()
        for d in defs:
            if d.get("role") == role:
                if not d.get("enabled", True):
                    raise ValueError(f"Agent角色 {role} 已禁用")
                return DynamicAgent(
                    project_dir=Path(project_dir),
                    role=d["role"],
                    prompt_file=d.get("prompt_file", f"{role}.md"),
                    display_name=d.get("display_name", ""),
                    execution_requirements=d.get("execution_requirements", ""),
                )
    except ValueError:
        raise
    except Exception:
        pass

    raise ValueError(f"未知的Agent角色: {role}")


from agents.pool import AgentInstance, AgentPool  # noqa: E402, I001


__all__ = [
    "BaseAgent",
    "DynamicAgent",
    "BackendDeveloper",
    "FrontendDeveloper",
    "QATester",
    "ProductManager",
    "UIDesigner",
    "DatabaseExpert",
    "SecurityReviewer",
    "DocsWriter",
    "Architect",
    "ReviewAgent",
    "AGENT_REGISTRY",
    "AGENT_ROLES",
    "get_agent",
    "AgentPool",
    "AgentInstance",
]
