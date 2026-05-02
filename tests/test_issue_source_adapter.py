"""IssueSourceAdapter 单元测试。"""

from pathlib import Path
from ralph.issue_source_adapter import (
    LocalFileIssueSource, IssueClassifier, GitHubIssueSource, Issue,
)


def test_local_fetch_issues(tmp_path: Path):
    (tmp_path / "bug-login.md").write_text("# Login Bug\n\nCannot login with empty password")
    source = LocalFileIssueSource(tmp_path)
    issues = source.fetch()
    assert len(issues) == 1
    assert issues[0].title == "Login Bug"


def test_classifier_bug():
    classifier = IssueClassifier()
    issue = Issue(issue_id="1", title="Fix broken login", description="login is broken, error 500", source="local", issue_type="feature")
    classified = classifier.classify(issue)
    assert classified.issue_type == "bug"


def test_classifier_security():
    classifier = IssueClassifier()
    issue = Issue(issue_id="2", title="XSS vulnerability in comment form", description="...", source="local", issue_type="feature")
    classified = classifier.classify(issue)
    assert classified.issue_type == "security"


def test_source_type_local():
    source = LocalFileIssueSource(Path("/tmp"))
    assert source.source_type() == "local"


def test_source_type_github():
    source = GitHubIssueSource(repo="test/test")
    assert source.source_type() == "github"


def test_classify_by_labels():
    assert GitHubIssueSource._classify_by_labels(["bug"]) == "bug"
    assert GitHubIssueSource._classify_by_labels(["security"]) == "security"
    assert GitHubIssueSource._classify_by_labels(["documentation"]) == "docs"
    assert GitHubIssueSource._classify_by_labels(["enhancement"]) == "refactor"
    assert GitHubIssueSource._classify_by_labels(["good first issue"]) == "feature"


def test_classifier_fallback_to_feature():
    classifier = IssueClassifier()
    issue = Issue(issue_id="3", title="Add new button", description="users want a new button", source="local", issue_type="feature")
    classified = classifier.classify(issue)
    assert classified.issue_type == "feature"


def test_issue_id_format():
    issue = Issue(issue_id="test-123", title="Test", description="...")
    assert issue.issue_id == "test-123"
    assert issue.status == "open"
