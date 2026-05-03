"""CouplingAnalyzer — 模块耦合分析：文件级、模块级、接口级。"""

from __future__ import annotations

import re
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CouplingEdge:
    src: str       # 源模块名
    dst: str       # 目标模块名
    kind: str      # import | call | shared_data
    weight: int = 1


@dataclass
class ModuleCoupling:
    name: str
    file_count: int = 0
    import_edges: list[CouplingEdge] = field(default_factory=list)
    import_degree: int = 0      # 出度(依赖别人)
    dependents: int = 0          # 入度(被别人依赖)
    risk_score: float = 0.0     # 0-1, 越高越危险


class CouplingAnalyzer:
    """分析文件级、模块级依赖耦合，识别高风险修改点。"""

    MODULE_DIRS = [
        "ralph", "dashboard", "agents", "core", "testing",
        "src", "app", "lib", "components",
    ]

    IMPORT_PATTERNS = [
        re.compile(r"from\s+([a-zA-Z_][\w.]*)\s+import"),
        re.compile(r"import\s+([a-zA-Z_][\w.]*)"),
    ]

    def analyze(self, project_dir: Path,
                recon_result: dict | None = None) -> list[ModuleCoupling]:
        """分析整个项目的模块耦合。

        recon_result: ReconAnalyzer.analyze() 的返回值。传入后用其中的
                    模块信息指导分析范围，忽略非相关目录。
        """
        if recon_result:
            # 用 recon 给出的模块列表指导分析
            known_modules = {m["name"] for m in recon_result.get("modules", [])}
            # 只分析 recon 确认存在的模块
            self.MODULE_DIRS = [m for m in self.MODULE_DIRS if m in known_modules]
        modules = self._discover_modules(project_dir)
        edges: list[CouplingEdge] = []
        import_graph: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for mod_name, mod_dir in modules:
            for py_file in mod_dir.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                imports = self._extract_imports(content)
                for imp in imports:
                    target_mod = self._resolve_module(imp, modules)
                    if target_mod and target_mod != mod_name:
                        import_graph[mod_name][target_mod] += 1
                        edges.append(CouplingEdge(
                            src=mod_name, dst=target_mod,
                            kind="import", weight=1,
                        ))

        # 计算每个模块的耦合指标
        result: list[ModuleCoupling] = []
        for mod_name, mod_dir in modules:
            out_edges = [e for e in edges if e.src == mod_name]
            in_degree = sum(1 for e in edges if e.dst == mod_name)
            file_count = len(list(mod_dir.rglob("*.py")))
            risk = self._calc_risk(in_degree, len(out_edges), file_count)

            result.append(ModuleCoupling(
                name=mod_name,
                file_count=file_count,
                import_edges=out_edges,
                import_degree=len(out_edges),
                dependents=in_degree,
                risk_score=risk,
            ))

        return sorted(result, key=lambda m: m.risk_score, reverse=True)

    def to_structured(self, modules: list[ModuleCoupling]) -> dict:
        """输出结构化数据供 ContractManager / TaskDecomposer 消费。"""
        return {
            "modules": [
                {
                    "name": m.name,
                    "file_count": m.file_count,
                    "import_edges": [
                        {"src": e.src, "dst": e.dst, "kind": e.kind, "weight": e.weight}
                        for e in m.import_edges
                    ],
                    "import_degree": m.import_degree,
                    "dependents": m.dependents,
                    "risk_score": m.risk_score,
                }
                for m in modules
            ],
        }

    def suggest_parallelization(self, modules: list[ModuleCoupling]) -> dict:
        """根据耦合分析，建议可并行和必须串行的模块。"""
        high_risk = {m.name for m in modules if m.risk_score > 0.5}
        leaf_modules = {m.name for m in modules if m.dependents == 0 and m.import_degree > 0}

        return {
            "high_risk_modes": sorted(high_risk),
            "can_parallelize": sorted(leaf_modules - high_risk),
            "must_serialize": sorted(high_risk),
            "recommendation": (
                f"{len(leaf_modules - high_risk)} 个模块可并行开发,"
                f" {len(high_risk)} 个模块须串行"
            ),
        }

    def _discover_modules(self, project_dir: Path) -> list[tuple[str, Path]]:
        modules = []
        for d in self.MODULE_DIRS:
            full = project_dir / d
            if full.is_dir() and full.name != "__pycache__":
                modules.append((d, full))
        return modules

    def _extract_imports(self, content: str) -> list[str]:
        imports = []
        for pattern in self.IMPORT_PATTERNS:
            for match in pattern.finditer(content):
                full_import = match.group(1)
                top_module = full_import.split(".")[0]
                if top_module not in ("__future__", "typing", "abc", "os", "sys",
                                      "json", "datetime", "re", "pathlib", "collections",
                                      "dataclasses", "enum", "subprocess", "tempfile",
                                      "contextlib", "threading", "asyncio", "logging",
                                      "shutil", "functools", "inspect", "importlib",
                                      "unittest", "pytest", "urllib", "http",
                                      "itertools", "math", "uuid", "time", "io",
                                      "copy", "glob", "hashlib", "base64"):
                    imports.append(top_module)
        return imports

    def _resolve_module(self, import_name: str,
                         modules: list[tuple[str, Path]]) -> str | None:
        for mod_name, _ in modules:
            if import_name.startswith(mod_name):
                return mod_name
        return None

    def _calc_risk(self, in_degree: int, out_degree: int,
                   file_count: int) -> float:
        if file_count == 0:
            return 0.0
        # 入度高 = 别人都依赖它 = 高风险
        # 出度高 = 依赖别人多 = 低风险
        # 文件多 = 模块大 = 中风险
        norm_in = min(in_degree / 10, 1.0)
        norm_file = min(file_count / 20, 1.0)
        return round((norm_in * 0.7 + norm_file * 0.3), 2)
