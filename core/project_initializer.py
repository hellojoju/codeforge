"""ProjectInitializer — 项目初始化：生成 PRD + Feature 分解。"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.config import GIT_AUTHOR_NAME
from core.permission_guard import PermissionGuard, PERMISSION_RULES_PROMPT

if TYPE_CHECKING:
    from core.state_models import Feature


class ProjectInitializer:
    """封装项目初始化的完整流程：git init + PRD 生成 + Feature 解析。"""

    def __init__(self, project_dir: Path, guard: PermissionGuard) -> None:
        self.project_dir = project_dir
        self._guard = guard

    def initialize(
        self,
        user_request: str,
        upsert_feature: Callable[[Feature], None],
    ) -> str:
        """执行初始化。

        Args:
            user_request: 用户需求描述
            upsert_feature: 回调函数，用于写入 Feature 到状态源

        Returns:
            PRD 摘要字符串
        """
        # 1. 初始化 git
        self._init_git()

        # 2. 生成 PRD + Features
        project_data = self.project_dir / "data"
        project_data.mkdir(parents=True, exist_ok=True)
        output_file = project_data / "prd.json"

        prompt = self._build_prd_prompt(user_request, output_file)

        pre_check = self._guard.check_prompt(prompt)
        if not pre_check.allowed:
            violations = [v.detail for v in pre_check.blocked_violations]
            raise RuntimeError(f"PRD generation blocked by permission guard: {violations}")

        full_prompt = prompt + "\n\n" + PERMISSION_RULES_PROMPT

        result = subprocess.run(
            ["claude", "-p", full_prompt, "--permission-mode", "acceptEdits"],
            capture_output=True,
            timeout=300,
            cwd=str(self.project_dir),
        )

        stderr_text = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI PRD generation failed (rc={result.returncode}): {stderr_text}")

        # 等待文件写入
        max_wait = 30
        waited = 0
        while not output_file.exists() and waited < max_wait:
            time.sleep(1)
            waited += 1

        if not output_file.exists():
            raise RuntimeError(f"Claude CLI did not write JSON to {output_file}. stderr: {stderr_text[:500]}")

        json_str = output_file.read_text(encoding="utf-8")
        if not json_str.strip():
            raise RuntimeError(f"Claude CLI wrote empty JSON to {output_file}")

        data = json.loads(json_str)
        prd_summary = data["prd_summary"]

        # 导入 features 到状态源
        features_data = data.get("features", [])
        for f in features_data:
            from core.state_models import Feature
            upsert_feature(Feature(**f))

        # 保存 PRD.md 和 features.json 审计副本
        (project_data / "prd.md").write_text(prd_summary, encoding="utf-8")
        (project_data / "features.json").write_text(
            json.dumps(features_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return prd_summary

    def _build_prd_prompt(self, user_request: str, output_file: Path) -> str:
        return f"""你是一个资深产品经理和技术架构师。请严格按以下要求完成任务。

**重要任务：你必须生成一个JSON文件并写入指定路径，不要输出任何其他文字。**

用户需求：{user_request}

请完成以下任务：

1. 写一份简洁的PRD（产品需求文档），包含：
   - 产品概述
   - 核心功能
   - 技术选型建议
   - 非功能需求（性能、安全、可扩展性）

2. 将功能分解为具体的features，每个feature要求：
   - 足够小，一个Agent能在一次会话内完成
   - 有明确的验收标准
   - 标注依赖关系
   - 标注优先级（P0-P3）
   - 指定负责的Agent角色（backend/frontend/database/qa/ui/security/docs）

**你必须将以下JSON内容写入文件：{output_file}**

JSON结构：
{{
  "prd_summary": "PRD内容字符串",
  "features": [
    {{
      "id": "F001",
      "category": "backend",
      "description": "用户可以注册账号",
      "priority": "P0",
      "assigned_to": "backend",
      "dependencies": [],
      "test_steps": ["访问注册页面", "填写表单", "提交成功"]
    }}
  ]
}}

确保features按合理的执行顺序排列，依赖关系正确。
**只执行一个操作：将JSON写入 {output_file}，不要输出任何其他内容。**"""

    def _init_git(self) -> None:
        try:
            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=self.project_dir,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", GIT_AUTHOR_NAME],
                cwd=self.project_dir,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "ai-dev@local"],
                cwd=self.project_dir,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            # git 已存在时 init 会失败，忽略
            if "already exists" not in (e.stderr.decode("utf-8", errors="replace").lower()):
                raise
