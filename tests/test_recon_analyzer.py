"""ReconAnalyzer 单元测试。"""

from pathlib import Path
from ralph.recon_analyzer import ReconAnalyzer


def test_analyze_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\ndependencies=['fastapi']")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    analyzer = ReconAnalyzer()
    result = analyzer.analyze(tmp_path)
    assert result["tech_stack"]["runtime"] == "python"


def test_count_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    (tmp_path / "c.ts").write_text("z")
    analyzer = ReconAnalyzer()
    counts = analyzer._count_files(tmp_path)
    assert counts.get("py") == 2
    assert counts.get("ts") == 1


def test_detect_key_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "package.json").write_text("{}")
    analyzer = ReconAnalyzer()
    key_files = analyzer._detect_key_files(tmp_path)
    assert "README.md" in key_files
    assert "package.json" in key_files


def test_detect_modules(tmp_path: Path):
    (tmp_path / "ralph").mkdir()
    (tmp_path / "ralph" / "mod.py").write_text("x")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.py").write_text("y")
    analyzer = ReconAnalyzer()
    modules = analyzer._detect_modules(tmp_path)
    names = [m["name"] for m in modules]
    assert "ralph" in names
    assert "agents" in names
