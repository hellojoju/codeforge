"""Review Agent — 多维度代码审查"""

from agents.base_agent import BaseAgent


class ReviewAgent(BaseAgent):
    role = "reviewer"
    prompt_file = "review_agent"

    def _build_prompt(self, task: dict) -> str:
        feature_id = task.get("feature_id", "")
        description = task.get("description", "")
        category = task.get("category", "")
        test_steps = task.get("test_steps", [])
        prd = task.get("prd_summary", "")
        deps = task.get("dependencies_context", "")
        project_dir = task.get("project_dir", "")

        steps_text = "\n".join(f"- {s}" for s in test_steps) if test_steps else "无具体测试步骤"

        return f"""{self.system_prompt}

---

## 任务信息
Feature ID: {feature_id}
分类: {category}
描述: {description}

## 验收标准
{steps_text}

## 依赖上下文
{deps}

## PRD摘要
{prd}

## 工作目录
{project_dir}

## 执行要求
1. 你是评审专家，负责多维度代码审查
2. 检查功能完整性：需求是否全部实现
3. 检查边界状态：错误处理、异常分支、空值处理
4. 检查假实现：是否有 TODO、pass、占位代码
5. 检查接口一致性：API 契约是否与文档匹配
6. 输出审查报告，写入文件
7. 发现问题标注严重程度并给出修复建议
"""
