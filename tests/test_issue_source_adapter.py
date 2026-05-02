"""IssueSourceAdapter 单元测试。"""

from pathlib import Path
from ralph.issue_source_adapter import LocalFileIssueSource, IssueClassifier, Issue


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


def test_source_type():
    source = LocalFileIssueSource(Path("/tmp"))
    assert source.source_type() == "local"
