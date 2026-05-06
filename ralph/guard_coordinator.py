"""Guard Coordinator — 安全协调器

文档依据：
- AI 协议 §11 阻塞机制
- PRD §8.8 权限和安全
- 实施方案 §4.15 Permission Guard

职责：
- 委托 PermissionGuard 做 prompt / diff 安全检查
- 提供 canary token 注入和输出泄露检测
- 作为 WorkUnitEngine 的安全中间层
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from core.permission_guard import PermissionGuard, PermissionCheckResult

logger = logging.getLogger(__name__)

# 零宽字符 canary 包裹符
ZWSP = "​"
ZWNJ = "‌"
ZWJ = "‍"

# prompt 注入 / 系统标签泄露检测模式
INJECTION_PATTERNS = [
    r"<system[_-]?reminder>",
    r"<function[_-]?results>",
    r"<user[_-]?prompt[_-]?submit[_-]?hook>",
    r"\[system[_-]?instruction\]",
    r"\[HIDDEN\]",
    r"ignore\s+(all\s+)?(prior\s+|previous\s+)?instructions",
    r"forget\s+(your\s+|all\s+)?(prior\s+|previous\s+)?instructions",
    r"you are now",
    r"new system prompt",
    r"\[INST\].*\[/INST\]",
]


def _sanitize(text: str) -> str:
    """移除常见注入标签和零宽字符。"""
    cleaned = text
    for pattern in INJECTION_PATTERNS:
        cleaned = re.sub(pattern, "[已移除]", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(ZWSP, "").replace(ZWNJ, "").replace(ZWJ, "")
    return cleaned


class GuardCoordinator:
    """安全协调器，串联 PermissionGuard + canary 注入/检测。"""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = Path(project_dir) if project_dir else Path.cwd()
        self._permission = PermissionGuard(self._project_dir)
        self._session_id = uuid.uuid4().hex[:12]
        self._canary_token = self._build_canary()

    # ---- canary token ---------------------------------------------------

    def _build_canary(self) -> str:
        ts = str(time.monotonic_ns())
        return f"{ZWSP}rc-{self._session_id}-{ts}{ZWSP}"

    def embed_canary(self, text: str) -> str:
        """注入隐蔽 canary token，用于检测输出中的系统提示泄露。

        在文本的前、中、后三个位置注入零宽字符包裹的签名。
        """
        if not text:
            return text
        token = self._build_canary()
        parts = text.partition("\n")
        if len(text) > 80:
            mid = len(text) // 2
            return f"{ZWSP}{token}{text[:mid]}{token}{text[mid:]}{token}{ZWNJ}"
        return f"{token}{text}{token}"

    # ---- 核心接口 (供 WorkUnitEngine 调用) -----------------------------

    def check_input(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """执行前输入扫描。

        1. 清洗注入标签和零宽字符
        2. 委托 PermissionGuard.check_prompt() 扫描危险命令
        3. 返回 (清洗后文本, 违规列表)

        Returns:
            tuple[str, list[dict]]: (cleaned_text, violations)
        """
        cleaned = _sanitize(text)
        violations: list[dict[str, str]] = []

        # 检测是否被清洗了（原始文本含有注入标签）
        if cleaned != text:
            violations.append({
                "type": "injection_stripped",
                "detail": "输入文本包含系统标签或注入模式，已清洗",
            })

        result: PermissionCheckResult = self._permission.check_prompt(cleaned)
        for v in result.violations:
            violations.append({
                "type": v.operation,
                "detail": v.detail,
                "level": v.level.value,
            })

        if not result.allowed:
            logger.warning("GuardCoordinator: check_input 阻止了含危险命令的文本")
            return ("", violations)

        return (cleaned, violations)

    def check_output(self, text: str) -> tuple[bool, list[dict[str, str]]]:
        """执行后输出验证。

        1. 检测 canary token 泄露（说明系统提示被暴露）
        2. 委托 PermissionGuard.check_prompt() 扫描危险命令模式
        3. 检测输出中的注入标签

        Returns:
            tuple[bool, list[dict]]: (is_safe, violations)
        """
        violations: list[dict[str, str]] = []

        # Canary 泄露检测
        session_sig = f"rc-{self._session_id}"
        if session_sig in text or ZWSP in text or ZWNJ in text:
            violations.append({
                "type": "canary_leak",
                "detail": "输出中包含 canary token — 可能发生系统提示泄露",
            })

        # 注入标签检测
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append({
                    "type": "injection_in_output",
                    "detail": f"输出中包含疑似注入标签: {pattern}",
                })

        # 委托 PermissionGuard 扫描危险模式
        result: PermissionCheckResult = self._permission.check_prompt(text)
        for v in result.violations:
            violations.append({
                "type": "dangerous_output",
                "detail": v.detail,
                "level": v.level.value,
            })

        is_safe = len(violations) == 0
        if not is_safe:
            logger.warning(
                "GuardCoordinator: check_output 检测到 %d 项安全风险",
                len(violations),
            )

        return (is_safe, violations)

    # ---- 编排方法 (向后兼容) ---------------------------------------------

    def pre_execute(self, context_text: str = "", prd_summary: str = "", **_: Any) -> dict[str, Any]:
        """执行前编排：串联 check_input + embed_canary。"""
        cleaned_text, ctx_violations = self.check_input(context_text)
        cleaned_prd, prd_violations = self.check_input(prd_summary)
        all_cleaned = self.embed_canary(cleaned_text)
        all_violations = ctx_violations + prd_violations
        return {
            "allowed": all(v.get("level") != "blocked" for v in all_violations),
            "cleaned_text": all_cleaned,
            "cleaned_prd": cleaned_prd,
            "violations": all_violations,
        }

    def post_execute(self, output_text: str = "", **_: Any) -> dict[str, Any]:
        """执行后编排：串联 check_output。"""
        is_safe, violations = self.check_output(output_text)
        return {
            "allowed": is_safe,
            "violations": violations,
        }
