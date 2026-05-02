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


class IssueClassifier:
    """基于关键词的 Issue 分类器。"""

    KEYWORDS: dict[str, list[str]] = {
        "bug": ["bug", "fix", "broken", "error", "fail", "crash"],
        "security": ["security", "vulnerability", "xss", "injection", "auth bypass"],
        "docs": ["doc", "readme", "document", "guide"],
        "refactor": ["refactor", "clean", "restructure", "rename"],
    }

    def classify(self, issue: Issue) -> Issue:
        text = (issue.title + " " + issue.description).lower()
        for itype, keywords in self.KEYWORDS.items():
            if any(kw in text for kw in keywords):
                issue.issue_type = itype
                return issue
        return issue  # stays as "feature"
