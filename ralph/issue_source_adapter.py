"""IssueSourceAdapter — Issue 源抽象 + 本地文件实现 + 分类器。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Issue:
    issue_id: str
    title: str
    description: str
    source: str = "local"
    issue_type: str = "feature"
    severity: str = "medium"
    status: str = "open"
    labels: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)


class IssueSource(ABC):
    """Issue 源抽象接口。"""
    @abstractmethod
    def fetch(self) -> list[Issue]: ...
    @abstractmethod
    def source_type(self) -> str: ...


class LocalFileIssueSource(IssueSource):
    """本地 .ralph/issues/*.md 文件 Issue 源。"""

    def __init__(self, issues_dir: Path):
        self._dir = issues_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def source_type(self) -> str:
        return "local"

    def fetch(self) -> list[Issue]:
        issues = []
        for f in sorted(self._dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            title = f.stem
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            issues.append(Issue(
                issue_id=f.stem, title=title, description=content,
                source="local", issue_type="feature",
            ))
        return issues


class GitHubIssueSource(IssueSource):
    """通过 GitHub API 拉取 Issues。"""

    def __init__(self, repo: str, token: str = "", label: str = ""):
        self._repo = repo
        self._token = token
        self._label = label

    def source_type(self) -> str:
        return "github"

    def fetch(self) -> list[Issue]:
        import json
        import urllib.request

        url = f"https://api.github.com/repos/{self._repo}/issues?state=open&per_page=50"
        if self._label:
            url += f"&labels={self._label}"

        req = urllib.request.Request(url)
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github.v3+json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                gh_issues = json.loads(resp.read().decode())
        except Exception:
            return []

        issues = []
        for gi in gh_issues:
            if "pull_request" in gi:
                continue  # 跳过 PR
            labels = [l.get("name", "") for l in gi.get("labels", [])]
            issues.append(Issue(
                issue_id=f"github-{gi['id']}",
                title=gi.get("title", ""),
                description=gi.get("body") or "",
                source="github",
                issue_type=self._classify_by_labels(labels),
                status="open" if gi.get("state") == "open" else "closed",
                labels=labels,
                created_at=gi.get("created_at", ""),
            ))
        return issues

    # ── 写回方法 ─────────────────────────────────────────────

    def write_comment(self, issue_number: int, body: str) -> dict:
        """向 Issue 添加评论。"""
        import json
        import urllib.request

        url = f"https://api.github.com/repos/{self._repo}/issues/{issue_number}/comments"
        req = urllib.request.Request(url, method="POST")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps({"body": body}).encode()

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_labels(self, issue_number: int, labels: list[str]) -> dict:
        """替换 Issue 的标签（保留已有标签，追加新标签）。"""
        import json
        import urllib.request

        url = f"https://api.github.com/repos/{self._repo}/issues/{issue_number}"
        req = urllib.request.Request(url, method="GET")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github.v3+json")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                current = json.loads(resp.read().decode())
        except Exception:
            current = {}

        existing_labels = [l.get("name", "") for l in current.get("labels", [])]
        # 过滤掉已有的 status: 前缀标签，追加新标签
        existing_labels = [l for l in existing_labels if not l.startswith("status:")]
        merged = list(dict.fromkeys(existing_labels + labels))

        put_req = urllib.request.Request(url, method="PATCH")
        if self._token:
            put_req.add_header("Authorization", f"Bearer {self._token}")
        put_req.add_header("Accept", "application/vnd.github.v3+json")
        put_req.add_header("Content-Type", "application/json")
        put_req.data = json.dumps({"labels": merged}).encode()

        try:
            with urllib.request.urlopen(put_req, timeout=15) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def close_issue(self, issue_number: int) -> dict:
        """关闭 Issue。"""
        import json
        import urllib.request

        url = f"https://api.github.com/repos/{self._repo}/issues/{issue_number}"
        req = urllib.request.Request(url, method="PATCH")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps({"state": "closed"}).encode()

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return {"ok": True, "data": json.loads(resp.read().decode())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _classify_by_labels(labels: list[str]) -> str:
        label_lower = " ".join(labels).lower()
        if any(kw in label_lower for kw in ("bug", "bugfix")):
            return "bug"
        if any(kw in label_lower for kw in ("security", "vulnerability")):
            return "security"
        if any(kw in label_lower for kw in ("doc", "documentation")):
            return "docs"
        if any(kw in label_lower for kw in ("refactor", "enhancement")):
            return "refactor"
        return "feature"


def issues_to_work_units(issues: list[Issue], policy: dict | None = None) -> list[dict]:
    """根据 Issue 列表和策略自动生成 WorkUnit 创建请求。"""
    if policy is None:
        policy = {"classification_rules": {}}

    rules = policy.get("classification_rules", {})
    units = []

    for issue in issues:
        action = rules.get(issue.issue_type, "require_approval")
        if action == "ignore":
            continue
        units.append({
            "source": "issue",
            "issue_id": issue.issue_id,
            "title": f"[{issue.issue_type}] {issue.title}",
            "description": issue.description,
            "work_type": issue.issue_type,
            "action": action,
            "producer_role": _issue_type_to_role(issue.issue_type),
        })

    return units


def _issue_type_to_role(issue_type: str) -> str:
    mapping = {"bug": "qa", "security": "security", "feature": "backend",
               "refactor": "architect", "docs": "docs"}
    return mapping.get(issue_type, "backend")


class IssueClassifier:
    """基于关键词的 Issue 分类器 + LLM 增强。"""

    KEYWORDS: dict[str, list[str]] = {
        "bug": ["bug", "fix", "broken", "error", "fail", "crash", "exception"],
        "security": ["security", "vulnerability", "xss", "injection", "auth bypass"],
        "docs": ["doc", "readme", "document", "guide", "tutorial"],
        "refactor": ["refactor", "clean", "restructure", "rename", "deprecate"],
    }

    def classify(self, issue: Issue) -> Issue:
        text = (issue.title + " " + issue.description).lower()
        for itype, keywords in self.KEYWORDS.items():
            if any(kw in text for kw in keywords):
                issue.issue_type = itype
                return issue
        return issue  # stays as "feature"

    def classify_with_llm(self, issue: Issue) -> Issue:
        """尝试用 LLM 增强分类（通过 claude CLI）。"""
        keyword_result = self.classify(issue)
        if keyword_result.issue_type != "feature":
            return keyword_result  # 关键词已经足够判断

        # LLM 兜底：对关键词无法判断的 issue 调用 Claude
        import subprocess
        prompt = (
            f"Classify this issue into exactly one: bug|feature|refactor|security|docs\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description[:500]}\n"
            f"Output only the type name."
        )
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--print"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                llm_type = result.stdout.strip().lower()
                if llm_type in ("bug", "feature", "refactor", "security", "docs"):
                    issue.issue_type = llm_type
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass  # LLM 不可用时静默使用关键词结果

        return issue
