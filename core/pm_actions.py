"""PM 意图识别 + 动作执行层。

通过关键词规则匹配用户意图，路由到对应动作执行器。
"""

import contextlib
import json
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --- 动作定义 ---

# 安全等级：safe = 直接执行；needs_approval = 需用户确认
ACTION_SECURITY: dict[str, str] = {
    "chat": "safe",
    "start_server": "safe",
    "stop_server": "safe",
    "run_tests": "safe",
    "build_project": "safe",
    "install_deps": "safe",
    "list_files": "safe",
    "read_file": "safe",
    "write_file": "needs_approval",
    "run_shell_command": "needs_approval",
}


@dataclass
class ActionResult:
    """动作执行结果。"""
    action: str
    success: bool
    reply: str
    output: str = ""


# --- 意图识别 ---

# 关键词规则：(action, [关键词列表])
_INTENT_RULES = [
    ("start_server", ["启动服务", "启动前后端", "启动项目", "run dev", "npm run dev", "启动前端", "启动后端"]),
    ("stop_server", ["停止服务", "停止项目", "kill", "停止前后端"]),
    ("run_tests", ["运行测试", "跑测试", "跑一下测试", "run test", "pytest", "执行测试"]),
    ("build_project", ["构建项目", "编译", "build", "打包"]),
    ("install_deps", ["安装依赖", "npm install", "pip install", "装依赖"]),
    ("list_files", ["列出文件", "目录列表", "ls", "文件列表", "看看项目结构"]),
    ("run_shell_command", ["执行命令", "shell", "terminal", "终端"]),
]


def classify_intent(
    user_message: str,
    project_dir: Path,
    initialized: bool,
) -> dict[str, Any]:
    """通过关键词规则匹配用户意图，返回 {action, params, reply}。"""
    msg_lower = user_message.lower()

    for action, keywords in _INTENT_RULES:
        for kw in keywords:
            if kw.lower() in msg_lower:
                # 生成默认回复
                reply = _default_reply(action, project_dir)
                return {"action": action, "params": {}, "reply": reply}

    # 未匹配任何规则 → 普通对话
    return {"action": "chat", "params": {}, "reply": ""}


def _default_reply(action: str, project_dir: Path) -> str:
    """生成动作的默认回复。"""
    replies = {
        "start_server": "好的，正在启动项目服务...",
        "stop_server": "好的，正在停止服务...",
        "run_tests": "好的，开始运行测试...",
        "build_project": "好的，开始构建项目...",
        "install_deps": "好的，正在安装依赖...",
        "list_files": "好的，这是项目文件列表：",
        "run_shell_command": "好的，执行命令...",
    }
    return replies.get(action, "收到！")


# --- 动作执行器 ---

def _find_project_package_dir(project_dir: Path) -> Path | None:
    """找到包含 package.json 的目录（前端目录）。"""
    # 先检查常见位置
    for candidate in [project_dir, project_dir / "frontend", project_dir / "web", project_dir / "app", project_dir / "dashboard-ui"]:
        if (candidate / "package.json").exists():
            return candidate
    # 递归搜索一层子目录
    for sub in project_dir.iterdir():
        if sub.is_dir() and (sub / "package.json").exists():
            return sub
    # 搜索 workspaces 下的 frontend 目录
    ws = project_dir / "workspaces"
    if ws.is_dir():
        for sub in ws.iterdir():
            if sub.is_dir() and sub.name.startswith("frontend") and (sub / "package.json").exists():
                return sub
    return None


def _find_python_entry(project_dir: Path) -> Path | None:
    """找到 Python 入口文件。"""
    for candidate in [
        project_dir / "main.py",
        project_dir / "app.py",
        project_dir / "server.py",
        project_dir / "api" / "main.py",
        project_dir / "backend" / "main.py",
        project_dir / "backend" / "app.py",
        project_dir / "backend" / "server.py",
    ]:
        if candidate.exists():
            return candidate
    # 搜索 workspaces 下的 backend 目录
    ws = project_dir / "workspaces"
    if ws.is_dir():
        for sub in ws.iterdir():
            if sub.is_dir() and sub.name.startswith("backend"):
                for entry in ["main.py", "app.py", "server.py"]:
                    p = sub / entry
                    if p.exists():
                        return p
    return None


def execute_action(
    action: str,
    params: dict[str, Any],
    project_dir: Path,
) -> ActionResult:
    """执行动作并返回结果。"""
    security = ACTION_SECURITY.get(action, "needs_approval")

    try:
        if action == "chat":
            return ActionResult(action=action, success=True, reply=params.get("reply", ""))

        elif action == "start_server":
            return _action_start_server(project_dir)

        elif action == "stop_server":
            return _action_stop_server(project_dir)

        elif action == "run_tests":
            return _action_run_tests(project_dir)

        elif action == "build_project":
            return _action_build_project(project_dir)

        elif action == "install_deps":
            return _action_install_deps(project_dir)

        elif action == "list_files":
            return _action_list_files(project_dir, params)

        elif action == "read_file":
            return _action_read_file(project_dir, params)

        elif action == "write_file":
            return _action_write_file(project_dir, params)

        elif action == "run_shell_command":
            return _action_run_shell_command(project_dir, params)

        else:
            return ActionResult(
                action=action, success=False, reply=f"未知动作: {action}"
            )
    except Exception as e:
        return ActionResult(
            action=action, success=False, reply=f"执行失败: {e}", output=str(e)
        )


def _action_start_server(project_dir: Path) -> ActionResult:
    """启动项目前后端服务。"""
    frontend_dir = _find_project_package_dir(project_dir)
    python_entry = _find_python_entry(project_dir)

    started = []
    errors = []

    if frontend_dir:
        # 检查端口 3000 是否被占用
        try:
            result = subprocess.run(
                ["lsof", "-i", ":3000", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                errors.append("端口 3000 已被占用，请先停止旧服务")
            else:
                # 在后台启动
                subprocess.Popen(
                    ["npm", "run", "dev", "--", "-p", "3000"],
                    cwd=str(frontend_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                started.append(f"前端 (http://localhost:3000)")
        except Exception as e:
            errors.append(f"前端启动失败: {e}")

    if python_entry:
        try:
            result = subprocess.run(
                ["lsof", "-i", ":8000", "-sTCP:LISTEN"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                errors.append("端口 8000 已被占用，请先停止旧服务")
            else:
                subprocess.Popen(
                    ["python3", str(python_entry)],
                    cwd=str(project_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                started.append(f"后端 (http://localhost:8000)")
        except Exception as e:
            errors.append(f"后端启动失败: {e}")

    if started:
        reply = f"已启动：{', '.join(started)}"
        if errors:
            reply += f"\n\n⚠️ 以下服务启动失败：{'；'.join(errors)}"
        return ActionResult(action="start_server", success=True, reply=reply)
    else:
        reply = "未找到可启动的服务（需要 package.json 或 Python 入口文件）"
        if errors:
            reply += f"\n\n错误：{'；'.join(errors)}"
        return ActionResult(action="start_server", success=False, reply=reply)


def _action_stop_server(project_dir: Path) -> ActionResult:
    """停止项目服务。"""
    stopped = []

    # 停止 3000 端口的进程
    try:
        result = subprocess.run(
            ["lsof", "-i", ":3000", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
            stopped.append("前端 (port 3000)")
    except Exception:
        pass

    # 停止 8000 端口的进程
    try:
        result = subprocess.run(
            ["lsof", "-i", ":8000", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
            stopped.append("后端 (port 8000)")
    except Exception:
        pass

    if stopped:
        return ActionResult(
            action="stop_server", success=True,
            reply=f"已停止：{', '.join(stopped)}"
        )
    return ActionResult(
        action="stop_server", success=True,
        reply="没有运行中的服务"
    )


def _action_run_tests(project_dir: Path) -> ActionResult:
    """运行测试。"""
    frontend_dir = _find_project_package_dir(project_dir)
    has_pytest = (project_dir / "pyproject.toml").exists() or (project_dir / "setup.py").exists()
    has_npm_test = frontend_dir and (frontend_dir / "package.json").exists()

    outputs = []

    if has_pytest:
        try:
            result = subprocess.run(
                ["python3", "-m", "pytest", "--tb=short", "-q"],
                cwd=str(project_dir), capture_output=True, text=True, timeout=60,
            )
            outputs.append(f"Python 测试：\n{result.stdout}\n{result.stderr}")
        except Exception as e:
            outputs.append(f"Python 测试失败: {e}")

    if has_npm_test:
        try:
            result = subprocess.run(
                ["npm", "test", "--", "--run"],
                cwd=str(frontend_dir), capture_output=True, text=True, timeout=60,
            )
            outputs.append(f"前端测试：\n{result.stdout}\n{result.stderr}")
        except Exception as e:
            outputs.append(f"前端测试失败: {e}")

    output_text = "\n\n---\n\n".join(outputs) if outputs else "未找到测试配置"
    return ActionResult(action="run_tests", success=True, reply=f"测试完成：\n{output_text}", output=output_text)


def _action_build_project(project_dir: Path) -> ActionResult:
    """构建项目。"""
    frontend_dir = _find_project_package_dir(project_dir)

    if frontend_dir:
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(frontend_dir), capture_output=True, text=True, timeout=120,
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return ActionResult(action="build_project", success=True, reply=f"构建成功：\n{output}", output=output)
            else:
                return ActionResult(action="build_project", success=False, reply=f"构建失败：\n{output}", output=output)
        except Exception as e:
            return ActionResult(action="build_project", success=False, reply=f"构建异常: {e}")

    return ActionResult(action="build_project", success=False, reply="未找到可构建的前端项目")


def _action_install_deps(project_dir: Path) -> ActionResult:
    """安装依赖。"""
    frontend_dir = _find_project_package_dir(project_dir)
    outputs = []

    # Python 依赖
    if (project_dir / "requirements.txt").exists():
        try:
            result = subprocess.run(
                ["python3", "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=str(project_dir), capture_output=True, text=True, timeout=120,
            )
            outputs.append(f"Python 依赖：\n{result.stdout}")
        except Exception as e:
            outputs.append(f"Python 依赖安装失败: {e}")
    elif (project_dir / "pyproject.toml").exists():
        try:
            result = subprocess.run(
                ["python3", "-m", "pip", "install", "-e", "."],
                cwd=str(project_dir), capture_output=True, text=True, timeout=120,
            )
            outputs.append(f"Python 依赖：\n{result.stdout}")
        except Exception as e:
            outputs.append(f"Python 依赖安装失败: {e}")

    # Node.js 依赖
    if frontend_dir:
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(frontend_dir), capture_output=True, text=True, timeout=120,
            )
            outputs.append(f"前端依赖：\n{result.stdout}")
        except Exception as e:
            outputs.append(f"前端依赖安装失败: {e}")

    output_text = "\n\n---\n\n".join(outputs) if outputs else "未找到依赖配置文件"
    return ActionResult(action="install_deps", success=True, reply=f"依赖安装完成：\n{output_text}", output=output_text)


def _action_list_files(project_dir: Path, params: dict) -> ActionResult:
    """列出项目文件。"""
    target = project_dir / (params.get("path") or "")
    if not target.exists():
        return ActionResult(action="list_files", success=False, reply=f"路径不存在: {params.get('path', '')}")
    if not target.is_dir():
        return ActionResult(action="list_files", success=False, reply=f"路径不是目录: {params.get('path', '')}")

    files = []
    for entry in sorted(target.iterdir()):
        prefix = "📁" if entry.is_dir() else "📄"
        files.append(f"{prefix} {entry.name}")

    listing = "\n".join(files) or "（空目录）"
    return ActionResult(
        action="list_files", success=True,
        reply=f"目录内容：\n{listing}"
    )


def _action_read_file(project_dir: Path, params: dict) -> ActionResult:
    """读取文件内容。"""
    path = params.get("path")
    if not path:
        return ActionResult(action="read_file", success=False, reply="请指定文件路径")

    target = project_dir / path
    if not target.exists():
        return ActionResult(action="read_file", success=False, reply=f"文件不存在: {path}")
    if not target.is_file():
        return ActionResult(action="read_file", success=False, reply=f"路径不是文件: {path}")

    try:
        content = target.read_text(encoding="utf-8")
        # 截断过长内容
        if len(content) > 5000:
            content = content[:5000] + "\n\n...（已截断，文件过长）"
        return ActionResult(
            action="read_file", success=True,
            reply=f"文件内容：\n```\n{content}\n```"
        )
    except Exception as e:
        return ActionResult(action="read_file", success=False, reply=f"读取失败: {e}")


def _action_write_file(project_dir: Path, params: dict) -> ActionResult:
    """写入文件（需审批）。"""
    path = params.get("path")
    content = params.get("content")
    if not path:
        return ActionResult(action="write_file", success=False, reply="请指定文件路径")

    target = project_dir / path
    # 安全检查：不允许跳出项目目录
    try:
        target.resolve().relative_to(project_dir.resolve())
    except ValueError:
        return ActionResult(
            action="write_file", success=False,
            reply=f"安全限制：文件必须在项目目录内"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content or "", encoding="utf-8")
    return ActionResult(
        action="write_file", success=True,
        reply=f"文件已创建：{path}"
    )


def _action_run_shell_command(project_dir: Path, params: dict) -> ActionResult:
    """执行 shell 命令（需审批）。"""
    command = params.get("command")
    if not command:
        return ActionResult(action="run_shell_command", success=False, reply="请指定要执行的命令")

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=str(project_dir), timeout=60,
        )
        output = result.stdout + result.stderr
        if result.returncode == 0:
            return ActionResult(
                action="run_shell_command", success=True,
                reply=f"命令执行成功：\n```\n{output}\n```", output=output
            )
        else:
            return ActionResult(
                action="run_shell_command", success=False,
                reply=f"命令执行失败 (exit {result.returncode})：\n```\n{output}\n```", output=output
            )
    except subprocess.TimeoutExpired:
        return ActionResult(action="run_shell_command", success=False, reply="命令执行超时（60s）")
    except Exception as e:
        return ActionResult(action="run_shell_command", success=False, reply=f"命令执行异常: {e}")
