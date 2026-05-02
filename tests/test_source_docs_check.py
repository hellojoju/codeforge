"""SourceDocsCheck 单元测试。"""

from pathlib import Path
from ralph.source_docs_check import SourceDocsCheck


def test_scan_package_json(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"next": "^15.0.0", "react": "^19.0.0"}}'
    )
    checker = SourceDocsCheck()
    deps = checker.scan_dependencies(tmp_path)
    names = [d.name for d in deps]
    assert "next" in names
    assert "react" in names


def test_get_docs_for_next():
    checker = SourceDocsCheck()
    docs = checker.get_docs("next")
    assert len(docs) >= 1
    assert "nextjs.org" in docs[0].url


def test_get_docs_fallback():
    checker = SourceDocsCheck()
    docs = checker.get_docs("some-unknown-pkg")
    assert len(docs) >= 1
    assert "pypi.org" in docs[0].url


def test_get_all_docs():
    checker = SourceDocsCheck()
    from ralph.source_docs_check import DependencyInfo
    deps = [
        DependencyInfo(name="next", version="15.0.0"),
        DependencyInfo(name="fastapi", version="0.110.0"),
    ]
    docs = checker.get_all_docs(deps)
    assert len(docs) >= 2


def test_markdown_report(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"next": "15.0.0"}}'
    )
    checker = SourceDocsCheck()
    report = checker.markdown_report(tmp_path)
    assert "# Source Docs Check" in report
    assert "next" in report


def test_guess_required_for():
    assert SourceDocsCheck._guess_required_for("next") == ["frontend"]
    assert SourceDocsCheck._guess_required_for("fastapi") == ["backend", "api"]
    assert SourceDocsCheck._guess_required_for("playwright") == ["test"]
