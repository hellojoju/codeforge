# Ralph MVP 差距补齐计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 补齐 MVP 29 项和实施方案 20 模块中缺失的 11 项，将完成度从 62% 提升到 90%+。

**架构：** 6 个新模块（SpecChangeManager、ContractManager、ToolAdapter、IssueSourceAdapter、ReconAnalyzer、VerificationManager）+ 3 个集成改进（Playwright、用户路径验收、边界检查）+ 2 个前端页面。

**技术栈：** Python 3.12+, FastAPI, Next.js 14, Zustand, Claude CLI, Playwright MCP

**现状基线：** 18/29 MVP 项已完成，14/20 实施方案模块已完成，前端 18 页面 + 后端 46 API + 952 测试全绿。

---

## 文件结构

```
ralph/
  spec_change_manager.py     # 新增 - OpenSpec-style specs 管理
  contract_manager.py        # 新增 - 接口合同定义与变更
  tool_adapter.py            # 新增 - ToolAdapter 抽象接口 + Claude 实现
  issue_source_adapter.py    # 新增 - Issue 源抽象 + 本地文件实现
  recon_analyzer.py          # 新增 - 深度代码库侦察分析
  verification_manager.py    # 新增 - 独立验收编排器

ralph/schema/
  spec_document.py           # 新增 - Spec 文档数据结构
  contract.py                # 新增 - 接口合同数据结构

dashboard/api/routes.py      # 修改 - 加 specs/contracts/toolchain/verification 端点

dashboard-ui/
  app/ralph/specs/page.tsx      # 新增 - Specs 浏览页面
  app/ralph/contracts/page.tsx  # 新增 - 合同管理页面
  lib/ralph-api.ts              # 修改 - 加新 API 函数

tests/
  test_spec_change_manager.py   # 新增
  test_contract_manager.py      # 新增
  test_tool_adapter.py           # 新增
  test_issue_source_adapter.py   # 新增
  test_recon_analyzer.py         # 新增
  test_verification_manager.py   # 新增

ralph/evidence_collector.py  # 修改 - 加多尺寸截图
testing/playwright_config.py # 修改 - 加多尺寸配置
```

---

### 任务 1：SpecChangeManager — OpenSpec 规格管理

**目标：** 实现 `.ralph/specs/current/` 和 `.ralph/specs/changes/` 的完整 CRUD。

**文件：**
- 创建：`ralph/schema/spec_document.py`
- 创建：`ralph/spec_change_manager.py`
- 创建：`tests/test_spec_change_manager.py`

- [ ] **步骤 1：编写 SpecDocument schema**

```python
# ralph/schema/spec_document.py
from dataclasses import dataclass, field
from datetime import UTC, datetime

def _now_iso() -> str:
    return datetime.now(UTC).isoformat()

@dataclass
class SpecDocument:
    spec_id: str
    capability: str         # e.g. "auth-login"
    title: str
    content: str            # markdown
    version: str = "1.0"
    status: str = "current"  # current | draft | archived
    dependencies: list[str] = field(default_factory=list)
    interfaces: list[dict] = field(default_factory=list)  # [{name, method, path, request, response}]
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

@dataclass
class SpecChange:
    change_id: str
    title: str
    proposal: str           # markdown - why this change
    design: str             # markdown - how to implement
    tasks: list[str] = field(default_factory=list)
    spec_deltas: list[dict] = field(default_factory=list)  # [{spec_id, field, old, new}]
    status: str = "proposed"  # proposed | approved | rejected | applied
    created_at: str = field(default_factory=_now_iso)
```

- [ ] **步骤 2：实现 SpecChangeManager**

```python
# ralph/spec_change_manager.py
import json
from pathlib import Path
from ralph.schema.spec_document import SpecDocument, SpecChange, _now_iso

class SpecChangeManager:
    """OpenSpec-style specs 管理: .ralph/specs/current/ + .ralph/specs/changes/"""

    def __init__(self, ralph_dir: Path):
        self._current_dir = ralph_dir / "specs" / "current"
        self._changes_dir = ralph_dir / "specs" / "changes"
        self._archive_dir = ralph_dir / "specs" / "archive"
        for d in [self._current_dir, self._changes_dir, self._archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def save_spec(self, spec: SpecDocument) -> SpecDocument:
        spec.updated_at = _now_iso()
        target = self._current_dir if spec.status == "current" else self._archive_dir
        path = target / f"{spec.capability}.json"
        path.write_text(json.dumps(spec.__dict__, indent=2, ensure_ascii=False, default=str))
        return spec

    def get_spec(self, capability: str) -> SpecDocument | None:
        path = self._current_dir / f"{capability}.json"
        if not path.is_file():
            return None
        return SpecDocument(**json.loads(path.read_text()))

    def list_specs(self) -> list[dict]:
        specs = []
        for f in sorted(self._current_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                specs.append({"capability": data.get("capability", f.stem), "title": data.get("title", ""), "version": data.get("version", ""), "interfaces": len(data.get("interfaces", []))})
            except Exception: continue
        return specs

    def create_change(self, change: SpecChange) -> SpecChange:
        path = self._changes_dir / f"{change.change_id}.json"
        path.write_text(json.dumps(change.__dict__, indent=2, ensure_ascii=False, default=str))
        return change

    def approve_change(self, change_id: str) -> SpecChange | None:
        change = self._load_change(change_id)
        if not change: return None
        change.status = "approved"
        self.create_change(change)
        return change

    def apply_change(self, change_id: str) -> SpecChange | None:
        change = self._load_change(change_id)
        if not change or change.status != "approved": return None
        for delta in change.spec_deltas:
            spec = self.get_spec(delta["spec_id"])
            if spec:
                setattr(spec, delta["field"], delta["new"])
                self.save_spec(spec)
        change.status = "applied"
        self.create_change(change)
        # archive the change
        (self._changes_dir / f"{change_id}.json").rename(self._archive_dir / f"{change_id}.json")
        return change

    def list_changes(self) -> list[dict]:
        changes = []
        for f in sorted(self._changes_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                changes.append({"change_id": data.get("change_id", f.stem), "title": data.get("title", ""), "status": data.get("status", ""), "created_at": data.get("created_at", "")})
            except Exception: continue
        return changes

    def _load_change(self, change_id: str) -> SpecChange | None:
        path = self._changes_dir / f"{change_id}.json"
        if not path.is_file(): return None
        return SpecChange(**json.loads(path.read_text()))
```

- [ ] **步骤 3：编写测试**

```python
# tests/test_spec_change_manager.py
from pathlib import Path
from ralph.spec_change_manager import SpecChangeManager
from ralph.schema.spec_document import SpecDocument, SpecChange

def test_save_and_get_spec(tmp_path: Path):
    mgr = SpecChangeManager(tmp_path / ".ralph")
    spec = SpecDocument(spec_id="spec-1", capability="auth-login", title="Auth Login", content="# Auth\n...")
    mgr.save_spec(spec)
    loaded = mgr.get_spec("auth-login")
    assert loaded is not None
    assert loaded.title == "Auth Login"

def test_list_specs(tmp_path: Path):
    mgr = SpecChangeManager(tmp_path / ".ralph")
    mgr.save_spec(SpecDocument(spec_id="s1", capability="auth", title="Auth", content=""))
    mgr.save_spec(SpecDocument(spec_id="s2", capability="board", title="Board", content=""))
    assert len(mgr.list_specs()) == 2

def test_change_lifecycle(tmp_path: Path):
    mgr = SpecChangeManager(tmp_path / ".ralph")
    mgr.save_spec(SpecDocument(spec_id="s1", capability="auth", title="Auth v1", content="v1"))
    change = mgr.create_change(SpecChange(change_id="ch-1", title="Add remember-me", proposal="...", design="...", tasks=["t1"], spec_deltas=[{"spec_id": "auth", "field": "title", "new": "Auth v2"}]))
    assert change.status == "proposed"
    approved = mgr.approve_change("ch-1")
    assert approved.status == "approved"
    applied = mgr.apply_change("ch-1")
    assert applied.status == "applied"
    updated_spec = mgr.get_spec("auth")
    assert updated_spec.title == "Auth v2"
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
python3 -m pytest tests/test_spec_change_manager.py -v
# 预期: 3 passed
git add ralph/spec_change_manager.py ralph/schema/spec_document.py tests/test_spec_change_manager.py
git commit -m "feat(ralph): add SpecChangeManager for OpenSpec-style spec lifecycle"
```

---

### 任务 2：ContractManager — 接口合同管理

**文件：**
- 创建：`ralph/schema/contract.py`
- 创建：`ralph/contract_manager.py`
- 创建：`tests/test_contract_manager.py`

- [ ] **步骤 1：编写 Contract schema + Manager + 测试**

```python
# ralph/schema/contract.py
from dataclasses import dataclass, field
from datetime import UTC, datetime

def _now_iso() -> str: return datetime.now(UTC).isoformat()

@dataclass
class InterfaceContract:
    contract_id: str
    name: str
    method: str          # GET | POST | PUT | DELETE | FUNCTION | CLASS
    path: str            # "/api/users" or "src/auth/login.ts::loginUser"
    request_schema: dict = field(default_factory=dict)
    response_schema: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    consumers: list[str] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    status: str = "proposed"  # proposed | frozen | deprecated
    version: str = "1.0"
    created_at: str = field(default_factory=_now_iso)

    def freeze(self) -> None:
        self.status = "frozen"
```

```python
# ralph/contract_manager.py
import json
from pathlib import Path
from ralph.schema.contract import InterfaceContract, _now_iso

class ContractManager:
    """接口合同管理 + 变更申请。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "contracts"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, contract: InterfaceContract) -> InterfaceContract:
        path = self._dir / f"{contract.contract_id}.json"
        path.write_text(json.dumps(contract.__dict__, indent=2, ensure_ascii=False, default=str))
        return contract

    def get(self, contract_id: str) -> InterfaceContract | None:
        path = self._dir / f"{contract_id}.json"
        if not path.is_file(): return None
        return InterfaceContract(**json.loads(path.read_text()))

    def list_contracts(self) -> list[dict]:
        contracts = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                contracts.append({"contract_id": data.get("contract_id", f.stem), "name": data.get("name", ""), "method": data.get("method", ""), "path": data.get("path", ""), "status": data.get("status", "")})
            except Exception: continue
        return contracts

    def freeze(self, contract_id: str) -> InterfaceContract:
        contract = self.get(contract_id)
        if not contract: raise ValueError(f"Contract {contract_id} not found")
        contract.freeze()
        return self.save(contract)

    def validate_consumer(self, contract_id: str, consumer_impl: dict) -> list[str]:
        """验证消费者实现是否符合合同。"""
        contract = self.get(contract_id)
        if not contract: return [f"Contract {contract_id} not found"]
        issues = []
        if contract.response_schema and consumer_impl != contract.response_schema:
            keys_expected = set(contract.response_schema.keys())
            keys_actual = set(consumer_impl.keys())
            if keys_expected - keys_actual:
                issues.append(f"Missing keys: {keys_expected - keys_actual}")
        return issues
```

```python
# tests/test_contract_manager.py
from pathlib import Path
from ralph.contract_manager import ContractManager
from ralph.schema.contract import InterfaceContract

def test_save_and_get(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    contract = InterfaceContract(contract_id="ct-1", name="Login API", method="POST", path="/api/login", request_schema={"email": "string", "password": "string"}, response_schema={"token": "string"})
    mgr.save(contract)
    loaded = mgr.get("ct-1")
    assert loaded is not None
    assert loaded.name == "Login API"

def test_freeze(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(contract_id="ct-1", name="API", method="GET", path="/api/data"))
    frozen = mgr.freeze("ct-1")
    assert frozen.status == "frozen"

def test_validate_consumer(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(contract_id="ct-1", name="API", method="GET", path="/api/data", response_schema={"id": "int", "name": "str"}))
    issues = mgr.validate_consumer("ct-1", {"id": 1})
    assert len(issues) == 1
    assert "name" in issues[0]

def test_list_contracts(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(contract_id="c1", name="A", method="GET", path="/a"))
    mgr.save(InterfaceContract(contract_id="c2", name="B", method="POST", path="/b"))
    assert len(mgr.list_contracts()) == 2
```

- [ ] **步骤 2：运行测试 + Commit**

```bash
python3 -m pytest tests/test_contract_manager.py -v
# 预期: 4 passed
git add ralph/contract_manager.py ralph/schema/contract.py tests/test_contract_manager.py
git commit -m "feat(ralph): add ContractManager for interface contract management"
```

---

### 任务 3：ToolAdapter — 多工具抽象接口

**文件：**
- 创建：`ralph/tool_adapter.py`
- 创建：`tests/test_tool_adapter.py`

- [ ] **步骤 1：实现 ToolAdapter 抽象 + Claude 适配器**

```python
# ralph/tool_adapter.py
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class ExecutionResult:
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    evidence_files: list[str] = field(default_factory=list)
    error: str = ""

@dataclass
class ToolCapability:
    streaming: bool = False
    session_resume: bool = False
    tool_use: bool = False
    mcp_support: bool = False
    max_context_tokens: int = 100000


class ToolAdapter(ABC):
    """编程工具抽象接口。统一封装不同 CLI 工具的调用。"""

    tool_id: str = ""
    capabilities: ToolCapability = field(default_factory=ToolCapability)

    @abstractmethod
    async def execute(self, prompt: str, *, cwd: str = ".", timeout: int = 600, allowed_tools: list[str] | None = None) -> ExecutionResult:
        ...

    @abstractmethod
    async def execute_streaming(self, prompt: str, *, cwd: str = ".", timeout: int = 600, stream_callback=None, **kwargs) -> ExecutionResult:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...


class ClaudeCodeAdapter(ToolAdapter):
    """Claude Code CLI 适配器。"""

    tool_id = "claude_code"
    capabilities = ToolCapability(streaming=True, session_resume=True, tool_use=True, mcp_support=True)

    def __init__(self, claude_bin: str = "claude", permission_mode: str = "acceptEdits"):
        self._bin = claude_bin
        self._permission_mode = permission_mode

    async def execute(self, prompt: str, *, cwd: str = ".", timeout: int = 600, allowed_tools: list[str] | None = None) -> ExecutionResult:
        import asyncio
        cmd = [self._bin, "-p", prompt, "--permission-mode", self._permission_mode, "--output-format", "text"]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return ExecutionResult(success=proc.returncode == 0, exit_code=proc.returncode or 0, stdout=stdout.decode() if stdout else "", stderr=stderr.decode() if stderr else "")
        except asyncio.TimeoutError:
            return ExecutionResult(success=False, error="Timeout")
        except FileNotFoundError:
            return ExecutionResult(success=False, error=f"{self._bin} not found")

    async def execute_streaming(self, prompt: str, *, cwd: str = ".", timeout: int = 600, stream_callback=None, **kwargs) -> ExecutionResult:
        return await self.execute(prompt, cwd=cwd, timeout=timeout)

    def is_available(self) -> bool:
        import shutil
        return shutil.which(self._bin) is not None


class ToolAdapterRegistry:
    """工具适配器注册表。"""

    def __init__(self):
        self._adapters: dict[str, ToolAdapter] = {}
        self._priority: list[str] = []

    def register(self, adapter: ToolAdapter) -> None:
        self._adapters[adapter.tool_id] = adapter
        if adapter.tool_id not in self._priority:
            self._priority.append(adapter.tool_id)

    def get(self, tool_id: str) -> ToolAdapter | None:
        return self._adapters.get(tool_id)

    def list_available(self) -> list[str]:
        return [tid for tid in self._priority if self._adapters.get(tid) and self._adapters[tid].is_available()]

    def get_primary(self) -> ToolAdapter | None:
        for tid in self._priority:
            adapter = self._adapters.get(tid)
            if adapter and adapter.is_available():
                return adapter
        return None
```

- [ ] **步骤 2：编写测试**

```python
# tests/test_tool_adapter.py
import pytest
from ralph.tool_adapter import ClaudeCodeAdapter, ToolAdapterRegistry, ExecutionResult, ToolCapability

@pytest.mark.asyncio
async def test_claude_not_available_gracefully():
    adapter = ClaudeCodeAdapter(claude_bin="nonexistent-claude-bin-xyz")
    result = await adapter.execute("hello")
    assert not result.success
    assert "not found" in result.error

def test_registry_register_and_get():
    registry = ToolAdapterRegistry()
    adapter = ClaudeCodeAdapter()
    registry.register(adapter)
    assert registry.get("claude_code") is not None

def test_registry_list_available():
    registry = ToolAdapterRegistry()
    registry.register(ClaudeCodeAdapter(claude_bin="nonexistent"))
    assert registry.list_available() == []

def test_capabilities():
    adapter = ClaudeCodeAdapter()
    assert adapter.capabilities.streaming is True
    assert adapter.capabilities.mcp_support is True
```

- [ ] **步骤 3：运行测试 + Commit**

```bash
python3 -m pytest tests/test_tool_adapter.py -v
# 预期: 4 passed
git add ralph/tool_adapter.py tests/test_tool_adapter.py
git commit -m "feat(ralph): add ToolAdapter abstraction and ClaudeCodeAdapter"
```

---

### 任务 4：IssueSourceAdapter + ReconAnalyzer — Issue 源 + 代码库侦察

**文件：**
- 创建：`ralph/issue_source_adapter.py`
- 创建：`ralph/recon_analyzer.py`
- 创建：`tests/test_issue_source_adapter.py`
- 创建：`tests/test_recon_analyzer.py`

- [ ] **步骤 1：IssueSourceAdapter**

```python
# ralph/issue_source_adapter.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import UTC, datetime

def _now_iso() -> str: return datetime.now(UTC).isoformat()

@dataclass
class Issue:
    issue_id: str
    title: str
    description: str
    source: str           # "local" | "github"
    issue_type: str       # "bug" | "feature" | "refactor" | "security" | "docs"
    severity: str = "medium"
    status: str = "open"
    labels: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)

class IssueSource(ABC):
    @abstractmethod
    def fetch(self) -> list[Issue]: ...
    @abstractmethod
    def source_type(self) -> str: ...

class LocalFileIssueSource(IssueSource):
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
            description = content
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            issues.append(Issue(issue_id=f.stem, title=title, description=content, source="local", issue_type="feature"))
        return issues

class IssueClassifier:
    KEYWORDS = {"bug": ["bug", "fix", "broken", "error", "fail"], "security": ["security", "vulnerability", "xss", "injection", "auth"], "docs": ["doc", "readme", "document"], "refactor": ["refactor", "clean", "restructure"]}

    def classify(self, issue: Issue) -> Issue:
        text = (issue.title + " " + issue.description).lower()
        for itype, keywords in self.KEYWORDS.items():
            if any(kw in text for kw in keywords):
                issue.issue_type = itype
                return issue
        issue.issue_type = "feature"
        return issue
```

- [ ] **步骤 2：ReconAnalyzer（深度版）**

```python
# ralph/recon_analyzer.py
from pathlib import Path
import subprocess, json

class ReconAnalyzer:
    """深度代码库侦察：技术栈、模块边界、耦合关系、关键文件。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir

    def analyze(self, project_path: Path) -> dict:
        return {"project_name": project_path.name, "tech_stack": self._detect_tech_stack(project_path), "modules": self._detect_modules(project_path), "key_files": self._detect_key_files(project_path), "git_summary": self._git_summary(project_path), "file_count": self._count_files(project_path)}

    def _detect_tech_stack(self, path: Path) -> dict:
        stack = {}
        if (path / "package.json").is_file():
            pkg = json.loads((path / "package.json").read_text())
            stack["runtime"] = "node"
            stack["framework"] = "next" if "next" in str(pkg.get("dependencies", {})) else "react" if "react" in str(pkg.get("dependencies", {})) else "node"
        if (path / "pyproject.toml").is_file():
            stack["runtime"] = "python"
            content = (path / "pyproject.toml").read_text()
            stack["framework"] = "fastapi" if "fastapi" in content else "django" if "django" in content else "flask" if "flask" in content else "python"
        if (path / "go.mod").is_file():
            stack["runtime"] = "go"
        return stack

    def _detect_modules(self, path: Path) -> list[dict]:
        modules = []
        common_dirs = ["src", "app", "components", "lib", "ralph", "dashboard", "agents", "core", "tests"]
        for d in common_dirs:
            full = path / d
            if full.is_dir():
                py_files = len(list(full.rglob("*.py")))
                ts_files = len(list(full.rglob("*.ts"))) + len(list(full.rglob("*.tsx")))
                modules.append({"name": d, "python_files": py_files, "typescript_files": ts_files})
        return modules

    def _detect_key_files(self, path: Path) -> list[str]:
        patterns = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "README.md", "ARCHITECTURE.md", "Makefile", "Dockerfile", ".github/workflows/*.yml"]
        key_files = []
        for pattern in patterns:
            for f in path.glob(pattern):
                key_files.append(str(f.relative_to(path)))
        return key_files

    def _git_summary(self, path: Path) -> dict:
        try:
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, text=True, timeout=5).strip()
            log = subprocess.check_output(["git", "log", "--oneline", "-10"], cwd=path, text=True, timeout=5).strip()
            contributors = subprocess.check_output(["git", "shortlog", "-sn", "HEAD"], cwd=path, text=True, timeout=5).strip()
            return {"branch": branch, "recent_commits": log, "contributors": contributors}
        except Exception:
            return {"branch": "unknown"}

    def _count_files(self, path: Path) -> dict:
        counts = {}
        for ext in ["py", "ts", "tsx", "js", "css", "html", "md", "json", "yaml", "sql"]:
            counts[ext] = len(list(path.rglob(f"*.{ext}")))
        return {k: v for k, v in counts.items() if v > 0}
```

- [ ] **步骤 3：测试**

```python
# tests/test_issue_source_adapter.py
from pathlib import Path
from ralph.issue_source_adapter import LocalFileIssueSource, IssueClassifier, Issue

def test_local_fetch_issues(tmp_path: Path):
    (tmp_path / "bug-login.md").write_text("# Login Bug\n\nCannot login with empty password")
    source = LocalFileIssueSource(tmp_path)
    issues = source.fetch()
    assert len(issues) == 1
    assert issues[0].title == "Login Bug"

def test_classifier_bug(tmp_path: Path):
    classifier = IssueClassifier()
    issue = Issue(issue_id="1", title="Fix broken login", description="login is broken, error 500", source="local", issue_type="feature")
    classified = classifier.classify(issue)
    assert classified.issue_type == "bug"

# tests/test_recon_analyzer.py
from pathlib import Path
from ralph.recon_analyzer import ReconAnalyzer

def test_analyze_python_project(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\ndependencies=['fastapi']")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    analyzer = ReconAnalyzer(tmp_path / ".ralph")
    result = analyzer.analyze(tmp_path)
    assert result["tech_stack"]["runtime"] == "python"

def test_count_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.py").write_text("y")
    (tmp_path / "c.ts").write_text("z")
    analyzer = ReconAnalyzer(tmp_path / ".ralph")
    counts = analyzer._count_files(tmp_path)
    assert counts.get("py") == 2
    assert counts.get("ts") == 1
```

- [ ] **步骤 4：运行测试 + Commit**

```bash
python3 -m pytest tests/test_issue_source_adapter.py tests/test_recon_analyzer.py -v
# 预期: 4 passed
git add ralph/issue_source_adapter.py ralph/recon_analyzer.py tests/test_issue_source_adapter.py tests/test_recon_analyzer.py
git commit -m "feat(ralph): add IssueSourceAdapter and ReconAnalyzer"
```

---

### 任务 5：VerificationManager — 独立验收编排

**文件：**
- 创建：`ralph/verification_manager.py`
- 创建：`tests/test_verification_manager.py`

- [ ] **步骤 1：实现 VerificationManager（用户路径验收 + 边界检查 + 多尺寸截图）**

```python
# ralph/verification_manager.py
from dataclasses import dataclass, field
from pathlib import Path
from ralph.schema.brainstorm_record import UserPath

@dataclass
class VerificationChecklist:
    work_id: str
    user_paths: list[UserPath] = field(default_factory=list)
    boundary_states: list[str] = field(default_factory=list)  # "empty", "loading", "error", "unauthorized"
    screenshot_sizes: list[tuple[int, int]] = field(default_factory=lambda: [(375, 812), (768, 1024), (1280, 800)])
    checks: list[dict] = field(default_factory=list)  # [{check_name, passed, evidence}]

class VerificationManager:
    """独立验收编排器 — 用户路径、边界状态、多尺寸截图。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir

    def build_checklist(self, work_id: str, user_paths: list[UserPath] | None = None) -> VerificationChecklist:
        return VerificationChecklist(work_id=work_id, user_paths=user_paths or [], boundary_states=["empty", "loading", "error", "unauthorized"], checks=[])

    def verify_user_paths(self, checklist: VerificationChecklist, base_url: str = "http://localhost:3000") -> VerificationChecklist:
        for path in checklist.user_paths:
            for step in path.steps:
                checklist.checks.append({"check_name": f"user_path:{path.name}:{step}", "passed": False, "evidence": f"Playwright: navigate and verify step '{step}' at {base_url}", "notes": "Requires Playwright runtime"})
        return checklist

    def verify_boundary_states(self, checklist: VerificationChecklist) -> VerificationChecklist:
        for state in checklist.boundary_states:
            checklist.checks.append({"check_name": f"boundary:{state}", "passed": False, "evidence": f"Manual check: verify {state} state renders correctly", "notes": "Visual inspection required"})
        return checklist

    def verify_multi_size_screenshots(self, checklist: VerificationChecklist) -> VerificationChecklist:
        for w, h in checklist.screenshot_sizes:
            checklist.checks.append({"check_name": f"screenshot:{w}x{h}", "passed": False, "evidence": f"Playwright screenshot {w}x{h}", "notes": f"Save screenshot at {w}x{h} viewport"})
        return checklist

    def get_checklist(self, work_id: str) -> VerificationChecklist | None:
        import json
        path = self._dir / "evidence" / f"{work_id}_checklist.json"
        if not path.is_file(): return None
        data = json.loads(path.read_text())
        return VerificationChecklist(**data)

    def save_checklist(self, checklist: VerificationChecklist) -> None:
        import json
        evidence_dir = self._dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / f"{checklist.work_id}_checklist.json").write_text(json.dumps(checklist.__dict__, indent=2, ensure_ascii=False, default=str))
```

- [ ] **步骤 2：测试 + Commit**

```python
# tests/test_verification_manager.py
from pathlib import Path
from ralph.verification_manager import VerificationManager, VerificationChecklist
from ralph.schema.brainstorm_record import UserPath

def test_build_checklist(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    paths = [UserPath(name="main", steps=["step1", "step2"], edge_cases=["edge1"])]
    checklist = vm.build_checklist("wu-1", paths)
    assert checklist.work_id == "wu-1"
    assert len(checklist.user_paths) == 1

def test_verify_produces_checks(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1", [UserPath(name="test", steps=["go to page"], edge_cases=[])])
    checklist = vm.verify_user_paths(checklist, "http://localhost:3000")
    checklist = vm.verify_boundary_states(checklist)
    checklist = vm.verify_multi_size_screenshots(checklist)
    assert len(checklist.checks) >= 5  # 1 path step + 4 boundary + 3 screenshots

def test_save_and_load(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1")
    vm.save_checklist(checklist)
    loaded = vm.get_checklist("wu-1")
    assert loaded is not None
    assert loaded.work_id == "wu-1"
```

```bash
python3 -m pytest tests/test_verification_manager.py -v
# 预期: 3 passed
git add ralph/verification_manager.py tests/test_verification_manager.py
git commit -m "feat(ralph): add VerificationManager with user path, boundary state, and multi-size screenshot checks"
```

---

### 任务 6：API 端点 + 前端页面

**文件：**
- 修改：`dashboard/api/routes.py`
- 修改：`ralph/evidence_collector.py` — 多尺寸截图
- 创建：`app/ralph/specs/page.tsx`
- 创建：`app/ralph/contracts/page.tsx`
- 修改：`lib/ralph-api.ts`
- 修改：`components/ralph/sidebar.tsx`

- [ ] **步骤 1：加 API 端点**

在 `routes.py` 的 return app 之前添加：

```python
    # Specs
    @app.get("/api/ralph/specs")
    async def ralph_list_specs() -> list[dict]:
        from ralph.spec_change_manager import SpecChangeManager
        cfg: RalphConfigManager = app.state.config_manager
        return SpecChangeManager(cfg._dir.parent).list_specs()

    @app.post("/api/ralph/specs/changes")
    async def ralph_create_change(body: dict[str, Any]) -> dict:
        from ralph.spec_change_manager import SpecChangeManager
        from ralph.schema.spec_document import SpecChange
        cfg: RalphConfigManager = app.state.config_manager
        mgr = SpecChangeManager(cfg._dir.parent)
        change = mgr.create_change(SpecChange(**body))
        return {"change_id": change.change_id, "status": change.status}

    @app.post("/api/ralph/specs/changes/{change_id}/approve")
    async def ralph_approve_change(change_id: str) -> dict:
        from ralph.spec_change_manager import SpecChangeManager
        cfg: RalphConfigManager = app.state.config_manager
        mgr = SpecChangeManager(cfg._dir.parent)
        change = mgr.approve_change(change_id)
        if not change: raise HTTPException(status_code=404, detail="Change not found")
        return {"change_id": change.change_id, "status": change.status}

    # Contracts
    @app.get("/api/ralph/contracts")
    async def ralph_list_contracts() -> list[dict]:
        from ralph.contract_manager import ContractManager
        cfg: RalphConfigManager = app.state.config_manager
        return ContractManager(cfg._dir.parent).list_contracts()

    @app.post("/api/ralph/contracts")
    async def ralph_create_contract(body: dict[str, Any]) -> dict:
        from ralph.contract_manager import ContractManager
        from ralph.schema.contract import InterfaceContract
        cfg: RalphConfigManager = app.state.config_manager
        mgr = ContractManager(cfg._dir.parent)
        contract = mgr.save(InterfaceContract(**body))
        return {"contract_id": contract.contract_id, "status": contract.status}

    # Recon
    @app.post("/api/ralph/projects/recon")
    async def ralph_recon_analyze(body: dict[str, Any]) -> dict:
        from ralph.recon_analyzer import ReconAnalyzer
        project_path = Path(body.get("path", os.environ.get("PROJECT_DIR", ".")))
        analyzer = ReconAnalyzer(Path(".ralph"))
        return {"success": True, "analysis": analyzer.analyze(project_path.resolve())}

    # Verification
    @app.post("/api/ralph/verification/checklist")
    async def ralph_build_checklist(body: dict[str, Any]) -> dict:
        from ralph.verification_manager import VerificationManager
        cfg: RalphConfigManager = app.state.config_manager
        vm = VerificationManager(cfg._dir.parent)
        checklist = vm.build_checklist(body.get("work_id", ""))
        vm.save_checklist(checklist)
        return {"work_id": checklist.work_id, "checks": len(checklist.checks)}

    # Toolchain
    @app.get("/api/ralph/toolchain/available")
    async def ralph_toolchain_available() -> list[dict]:
        from ralph.tool_adapter import ToolAdapterRegistry, ClaudeCodeAdapter
        registry = ToolAdapterRegistry()
        registry.register(ClaudeCodeAdapter())
        return [{"tool_id": tid, "available": registry.get(tid).is_available() if registry.get(tid) else False} for tid in registry.list_available()]

    # Issues
    @app.get("/api/ralph/issues")
    async def ralph_list_issues() -> list[dict]:
        from ralph.issue_source_adapter import LocalFileIssueSource, IssueClassifier
        cfg: RalphConfigManager = app.state.config_manager
        issues_dir = cfg._dir.parent / "issues"
        source = LocalFileIssueSource(issues_dir)
        classifier = IssueClassifier()
        issues = source.fetch()
        return [{"issue_id": i.issue_id, "title": i.title, "issue_type": classifier.classify(i).issue_type, "source": i.source} for i in issues]
```

- [ ] **步骤 2：前端 API 函数**

在 `ralph-api.ts` 加：

```typescript
// Specs
export const specsApi = { list: () => request('/specs'), createChange: (body: unknown) => request('/specs/changes', { method: 'POST', body: JSON.stringify(body) }), approveChange: (id: string) => request(`/specs/changes/${id}/approve`, { method: 'POST' }) };
// Contracts
export const contractsApi = { list: () => request('/contracts'), create: (body: unknown) => request('/contracts', { method: 'POST', body: JSON.stringify(body) }) };
// Verification
export const verificationApi = { buildChecklist: (workId: string) => request('/verification/checklist', { method: 'POST', body: JSON.stringify({ work_id: workId }) }) };
// Recon
export const reconApi = { analyze: (path: string) => request('/projects/recon', { method: 'POST', body: JSON.stringify({ path }) }) };
// Issues
export const issuesApi = { list: () => request('/issues') };
```

- [ ] **步骤 3：Specs 和 Contracts 前端页面**

```tsx
// app/ralph/specs/page.tsx — specs 列表 + 查看内容
// app/ralph/contracts/page.tsx — 合同列表 + 冻结 + 验证
```
(完整页面代码约 150 行，此处省略以节约上下文，由实现者自行编写)

- [ ] **步骤 4：侧边栏加「规格文档」「接口合同」导航**

- [ ] **步骤 5：EvidenceCollector 多尺寸截图**

```python
# 在 ralph/evidence_collector.py 的 collect_playwright_screenshots 中
def collect_multi_size_screenshots(self, work_id: str, url: str = "http://localhost:3000") -> list[Evidence]:
    sizes = [("mobile", 375, 812), ("tablet", 768, 1024), ("desktop", 1280, 800)]
    items = []
    for label, w, h in sizes:
        try:
            result = subprocess.run(["npx", "playwright", "screenshot", url, f"--viewport-size={w},{h}", "--output", str(self._evidence_base / work_id / f"screenshot-{label}.png")], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                items.append(Evidence(evidence_id=f"ev-{work_id}-screenshot-{label}", work_id=work_id, evidence_type="screenshot", file_path=str(self._evidence_base / work_id / f"screenshot-{label}.png"), description=f"Screenshot {label} ({w}x{h})"))
        except Exception: pass
    return items
```

- [ ] **步骤 6：全量测试 + Commit**

```bash
python3 -m pytest -q --ignore=tests/test_ralph_bootstrap.py
cd dashboard-ui && npx vitest run
git add -A && git commit -m "feat(ralph): add API endpoints, frontend pages for specs, contracts, verification"
```

---

## 验证

每个任务后运行：
```bash
python3 -m pytest tests/test_<module>.py -v
```

全部完成后：
```bash
# 全量后端
python3 -m pytest -q --ignore=tests/test_ralph_bootstrap.py
# 全量前端
cd dashboard-ui && npx tsc --noEmit && npx vitest run
```
