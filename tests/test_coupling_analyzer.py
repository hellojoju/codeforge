"""CouplingAnalyzer 单元测试。"""

from pathlib import Path
from ralph.coupling_analyzer import CouplingAnalyzer


def test_discover_modules(tmp_path: Path):
    (tmp_path / "ralph").mkdir()
    (tmp_path / "ralph" / "mod.py").write_text("x = 1")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "a.py").write_text("y = 2")
    analyzer = CouplingAnalyzer()
    modules = analyzer._discover_modules(tmp_path)
    names = [m[0] for m in modules]
    assert "ralph" in names
    assert "agents" in names


def test_extract_imports():
    analyzer = CouplingAnalyzer()
    content = """
from ralph.work_unit import WorkUnit
import os
from dashboard.models import Feature
import json
from abc import ABC
"""
    imports = analyzer._extract_imports(content)
    assert "ralph" in imports
    assert "dashboard" in imports
    assert "os" not in imports  # stdlib excluded
    assert "abc" not in imports  # stdlib excluded


def test_analyze_simple_project(tmp_path: Path):
    """分析一个简单项目结构。"""
    (tmp_path / "ralph").mkdir()
    (tmp_path / "ralph" / "a.py").write_text("x = 1")
    (tmp_path / "ralph" / "b.py").write_text("from ralph.a import x; from dashboard.c import y")
    (tmp_path / "dashboard").mkdir()
    (tmp_path / "dashboard" / "c.py").write_text("y = 2")

    analyzer = CouplingAnalyzer()
    result = analyzer.analyze(tmp_path)
    names = [m.name for m in result]
    assert "ralph" in names
    assert "dashboard" in names


def test_suggest_parallelization():
    analyzer = CouplingAnalyzer()
    from ralph.coupling_analyzer import ModuleCoupling
    modules = [
        ModuleCoupling(name="ralph", file_count=10, dependents=5, import_degree=2, risk_score=0.7),
        ModuleCoupling(name="agents", file_count=5, dependents=0, import_degree=3, risk_score=0.2),
        ModuleCoupling(name="core", file_count=3, dependents=0, import_degree=1, risk_score=0.1),
    ]
    suggestion = analyzer.suggest_parallelization(modules)
    assert "ralph" in suggestion["must_serialize"]
    assert "must_serialize" in suggestion


def test_calc_risk():
    analyzer = CouplingAnalyzer()
    # 高入度 = 高风险
    high = analyzer._calc_risk(in_degree=8, out_degree=0, file_count=2)
    low = analyzer._calc_risk(in_degree=1, out_degree=5, file_count=1)
    assert high > low
