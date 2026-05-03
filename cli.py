"""CodeForge CLI — AI 全自动开发平台

用法:
    codeforge "我想做一个任务管理系统"
    codeforge --status
    codeforge --init "我想做一个博客系统" --dir ./my-blog
    codeforge --run
    codeforge --dashboard      # 启动 Dashboard 后端 + WebSocket
"""

from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.project_manager import ProjectManager

console = Console()
app = typer.Typer(help="AI全自动开发平台 - 人类当甲方，AI干所有活")


@contextmanager
def _switch_data_dir(project_dir: Path) -> AbstractContextManager[None]:
    """临时切换数据目录，退出时自动恢复"""
    import core.config
    import core.execution_ledger
    import core.feature_tracker
    import core.progress_logger
    import core.task_queue

    data_dir = project_dir / "data"
    original_data_dir = core.config.DATA_DIR
    original_features_file = core.config.FEATURES_FILE
    original_progress_file = core.config.PROGRESS_FILE
    original_task_db = core.config.TASK_DB
    original_prd_file = core.config.PRD_FILE
    original_project_state_file = core.config.PROJECT_STATE_FILE
    original_execution_ledger_file = core.config.EXECUTION_LEDGER_FILE

    original_tracker_features_file = core.feature_tracker.FEATURES_FILE
    original_progress_logger_file = core.progress_logger.PROGRESS_FILE
    original_task_queue_db = core.task_queue.TASK_DB
    original_ledger_file = core.execution_ledger.EXECUTION_LEDGER_FILE

    core.config.DATA_DIR = data_dir
    core.config.FEATURES_FILE = core.config.DATA_DIR / "features.json"
    core.config.PROGRESS_FILE = core.config.DATA_DIR / "claude-progress.txt"
    core.config.TASK_DB = core.config.DATA_DIR / "tasks.db"
    core.config.PRD_FILE = core.config.DATA_DIR / "prd.md"
    core.config.PROJECT_STATE_FILE = core.config.DATA_DIR / "project-state.json"
    core.config.EXECUTION_LEDGER_FILE = core.config.DATA_DIR / "execution-plan.json"

    core.feature_tracker.FEATURES_FILE = core.config.FEATURES_FILE
    core.progress_logger.PROGRESS_FILE = core.config.PROGRESS_FILE
    core.task_queue.TASK_DB = core.config.TASK_DB
    core.execution_ledger.EXECUTION_LEDGER_FILE = core.config.EXECUTION_LEDGER_FILE
    try:
        yield
    finally:
        core.config.DATA_DIR = original_data_dir
        core.config.FEATURES_FILE = original_features_file
        core.config.PROGRESS_FILE = original_progress_file
        core.config.TASK_DB = original_task_db
        core.config.PRD_FILE = original_prd_file
        core.config.PROJECT_STATE_FILE = original_project_state_file
        core.config.EXECUTION_LEDGER_FILE = original_execution_ledger_file

        core.feature_tracker.FEATURES_FILE = original_tracker_features_file
        core.progress_logger.PROGRESS_FILE = original_progress_logger_file
        core.task_queue.TASK_DB = original_task_queue_db
        core.execution_ledger.EXECUTION_LEDGER_FILE = original_ledger_file


def _validate_project_dir(project_dir: Path) -> None:
    if not project_dir.exists():
        console.print("[red]项目目录不存在[/red]")
        raise typer.Exit(1)


@app.command()
def init(
    request: str = typer.Argument(..., help="你的需求描述，比如'我想做一个任务管理系统'"),
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """初始化一个新项目 - 头脑风暴 + PRD + Feature分解"""
    project_dir = Path(directory).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold green]AI全自动开发平台[/bold green]\n"
        f"需求: {request}\n"
        f"项目目录: {project_dir}",
        title="🚀 项目初始化",
    ))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("正在初始化项目...", total=None)
        pm = ProjectManager(project_dir)

        progress.update(task1, description="正在分析需求...")
        _ = pm.initialize_project(request)

        progress.update(task1, description=f"已生成 {len(pm.feature_tracker.all_features())} 个features")

    # 显示状态
    status = pm.get_status()
    features = status["features"]

    table = Table(title="Feature分解结果")
    table.add_column("指标", style="cyan")
    table.add_column("数量", style="green")
    table.add_row("总计", str(features["total"]))
    table.add_row("待执行", str(features["pending"]))
    table.add_row("已完成", str(features["done"]))
    console.print(table)

    console.print(f"\n[bold]PRD已保存到:[/bold] {project_dir / 'data' / 'prd.md'}")
    console.print(f"[bold]Feature列表已保存到:[/bold] {project_dir / 'data' / 'features.json'}")
    console.print(f"\n[bold]下一步:[/bold] 运行 [green]codeforge --run --dir {directory}[/green] 开始开发")


@app.command()
def run(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
    use_coordinator: bool = typer.Option(
        True,
        "--coordinator/--no-coordinator",
        help="启用 PM 审批协调（默认启用，每一步完成后等待用户审批）",
    ),
) -> None:
    """开始执行开发循环（默认启用 PM 审批闸门）"""
    project_dir = Path(directory).resolve()
    _validate_project_dir(project_dir)

    mode_text = (
        "[green]已启用[/green]（每步完成后等待审批）"
        if use_coordinator
        else "[yellow]已关闭[/yellow]（自动执行）"
    )
    console.print(Panel.fit(
        f"[bold green]开始AI全自动开发[/bold green]\n项目目录: {project_dir}\n审批模式: {mode_text}",
        title="⚡ 执行循环",
    ))

    pm = ProjectManager(project_dir)

    if not pm._initialized:
        console.print("[yellow]项目未初始化，尝试从已有文件恢复...[/yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        _ = progress.add_task("正在执行开发循环...", total=None)

        if use_coordinator:
            # 使用 PMCoordinator：每步完成后暂停等待用户审批
            import uuid

            from dashboard.coordinator import PMCoordinator
            from dashboard.event_bus import EventBus
            from dashboard.state_repository import ProjectStateRepository

            state_dir = project_dir / "data" / "dashboard"
            state_dir.mkdir(parents=True, exist_ok=True)
            event_log = state_dir / "events.jsonl"

            event_bus = EventBus(log_file=event_log)
            repository = ProjectStateRepository(
                base_dir=state_dir,
                project_id=str(project_dir.name),
                run_id=uuid.uuid4().hex[:8],
            )
            coordinator = PMCoordinator(pm, repository, event_bus)
            result = coordinator.run_coordinated_loop()
        else:
            # 原始自动执行模式（无审批闸门）
            result = pm.run_execution_loop()

    # 显示最终结果
    table = Table(title="最终开发结果")
    table.add_column("指标", style="cyan")
    table.add_column("数量", style="green")
    table.add_row("总Features", str(result["total"]))
    table.add_row("已完成", str(result["done"]))
    table.add_row("验收通过", str(result["passing"]))
    table.add_row("进行中", str(result["in_progress"]))
    table.add_row("被阻塞", str(result["blocked"]))
    table.add_row("待执行", str(result["pending"]))
    console.print(table)

    if result["blocked"] > 0 or result["pending"] > 0:
        console.print(f"\n[yellow]有 {result['blocked']} 个features被阻塞，{result['pending']} 个待执行[/yellow]")
    else:
        console.print(f"\n[bold green]全部完成！{result['done']} 个features全部通过验收！[/bold green]")


@app.command()
def status(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """查看当前项目状态"""
    project_dir = Path(directory).resolve()
    _validate_project_dir(project_dir)

    state_dir = project_dir / "data" / "dashboard"
    if (state_dir / "state.json").exists():
        from dashboard.state_repository import ProjectStateRepository

        repo = ProjectStateRepository(base_dir=state_dir, project_id=str(project_dir.name))
        snapshot = repo.load_snapshot()
        features = snapshot.features
        summary = {
            "total": len(features),
            "done": sum(1 for f in features if f.status == "done"),
            "in_progress": sum(1 for f in features if f.status == "in_progress"),
            "blocked": sum(1 for f in features if f.status == "blocked"),
            "pending": sum(1 for f in features if f.status == "pending"),
        }
        state = {"initialized": True, "features": summary}
    else:
        pm = ProjectManager(project_dir)
        state = pm.get_status()

    console.print(Panel.fit(
        f"[bold]项目状态[/bold]\n"
        f"已初始化: {'是' if state['initialized'] else '否'}",
        title="📊 状态",
    ))

    features = state["features"]
    table = Table()
    table.add_column("状态", style="cyan")
    table.add_column("数量", style="green")
    for key, value in features.items():
        table.add_row(key, str(value))
    console.print(table)

    # 显示最近进度
    from core.progress_logger import progress
    recent = progress.tail(10)
    if recent:
        console.print("\n[bold]最近进度:[/bold]")
        for line in recent:
            console.print(f"  {line}")


@app.command()
def tail(
    n: int = typer.Option(20, "-n", help="显示最后N行进度"),
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """查看最近进度日志"""
    project_dir = Path(directory).resolve()
    from core.progress_logger import progress

    with _switch_data_dir(project_dir):
        lines = progress.tail(n)
        if lines:
            for line in lines:
                console.print(line)
        else:
            console.print("[yellow]暂无进度记录[/yellow]")


@app.command()
def plan(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """显示执行计划和特性队列"""
    project_dir = Path(directory).resolve()
    _validate_project_dir(project_dir)

    from core.execution_ledger import ExecutionLedger
    from core.feature_tracker import FeatureTracker
    from dashboard.state_repository import ProjectStateRepository

    features = None
    state_dir = project_dir / "data" / "dashboard"
    with _switch_data_dir(project_dir):
        ledger = ExecutionLedger()
        ledger_summary = ledger.get_summary()
        if (state_dir / "state.json").exists():
            repo = ProjectStateRepository(base_dir=state_dir, project_id=str(project_dir.name))
            snapshot = repo.load_snapshot()
            features = snapshot.features
            summary = {
                "total": len(features),
                "done": sum(1 for f in features if f.status == "done"),
                "in_progress": sum(1 for f in features if f.status == "in_progress"),
                "blocked": sum(1 for f in features if f.status == "blocked"),
                "pending": sum(1 for f in features if f.status == "pending"),
            }
        else:
            tracker = FeatureTracker()
            features = tracker.all_features()
            summary = tracker.summary()

    console.print(Panel.fit(
        f"[bold]Execution Plan Summary[/bold]\n"
        f"Total: {summary['total']}\n"
        f"Done: {summary['done']}\n"
        f"In Progress: {summary['in_progress']}\n"
        f"Blocked: {summary['blocked']}\n"
        f"Pending: {summary['pending']}",
        title="📋 执行计划",
    ))

    console.print(
        f"[dim]Execution ledger:[/dim] total={ledger_summary['total_executions']} "
        f"completed={ledger_summary['completed']} failed={ledger_summary['failed']} "
        f"blocked={ledger_summary['blocked']} retrying={ledger_summary['retrying']}"
    )

    pending = [f for f in features if f.status == "pending"]
    if pending:
        table = Table(title="Pending features")
        table.add_column("Priority", style="cyan", width=8)
        table.add_column("ID", style="green", width=12)
        table.add_column("Description", style="white")
        table.add_column("Dependencies", style="yellow")
        for f in pending:
            deps = ", ".join(f.dependencies) if f.dependencies else "-"
            table.add_row(f.priority, f.id, f.description, deps)
        console.print(table)

    blocked = [f for f in features if f.status == "blocked"]
    if blocked:
        console.print("\n[bold red]Blocked features:[/bold red]")
        for f in blocked:
            last_error = f.error_log[-1] if f.error_log else "Unknown"
            console.print(f"  [red]{f.id}:[/red] {last_error}")


@app.command()
def blocked(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """显示所有阻塞问题"""
    project_dir = Path(directory).resolve()
    _validate_project_dir(project_dir)

    from dashboard.state_repository import ProjectStateRepository

    state_dir = project_dir / "data" / "dashboard"
    if not state_dir.exists():
        console.print("[yellow]Dashboard 状态目录不存在，尝试从 feature_tracker 读取...[/yellow]")
        with _switch_data_dir(project_dir):
            from core.feature_tracker import FeatureTracker
            tracker = FeatureTracker()
            blocked_features = [f for f in tracker.all_features() if f.status == "blocked"]
        if not blocked_features:
            console.print("[green]No blocking issues.[/green]")
            return
        console.print(f"\n[bold]Blocking Issues ({len(blocked_features)})[/bold]\n")
        for f in blocked_features:
            last_error = f.error_log[-1] if f.error_log else "Unknown"
            console.print(f"  [red][code_error][/red] {f.id}")
            console.print(f"    Description: {last_error}")
            console.print()
        return

    repo = ProjectStateRepository(base_dir=state_dir, project_id=str(project_dir.name))
    issues = repo.list_blocking_issues(resolved=False)

    if not issues:
        console.print("[green]No blocking issues.[/green]")
        return

    console.print(f"\n[bold]Blocking Issues ({len(issues)})[/bold]\n")
    for issue in issues:
        console.print(f"  [red][{issue.issue_type}][/red] {issue.feature_id}")
        console.print(f"    Description: {issue.description}")
        console.print(f"    Detected by: {issue.detected_by}")
        console.print(f"    Detected at: {issue.detected_at}")
        ctx_str = ", ".join(f"{k}={v}" for k, v in (issue.context or {}).items())
        if ctx_str:
            console.print(f"    Context: {ctx_str}")
        console.print()


@app.command()
def doctor(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """运行系统健康检查"""
    import os

    project_dir = Path(directory).resolve()

    console.print(Panel.fit("[bold]System Health Check[/bold]", title="🏥 Doctor"))

    # 环境变量
    required_vars = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    console.print("\n[bold]Environment Variables:[/bold]")
    for var in required_vars:
        value = os.environ.get(var)
        status = "[green]OK[/green]" if value else "[red]MISSING[/red]"
        console.print(f"  {var}: {status}")

    # 数据目录检查
    data_dir = project_dir / "data"
    console.print("\n[bold]Project Directory:[/bold]")
    console.print(f"  {project_dir}: {'[green]EXISTS[/green]' if project_dir.exists() else '[red]MISSING[/red]'}")

    # Feature 文件
    with _switch_data_dir(project_dir):
        import core.config
        console.print("\n[bold]Feature File:[/bold]")
        if core.config.FEATURES_FILE.exists():
            console.print(f"  {core.config.FEATURES_FILE}: [green]EXISTS[/green]")
        else:
            console.print(f"  {core.config.FEATURES_FILE}: [red]MISSING[/red]")

    # Task 数据库
    task_db = data_dir / "tasks.db"
    console.print("\n[bold]Task Database:[/bold]")
    if task_db.exists():
        console.print(f"  {task_db}: [green]EXISTS[/green]")
    else:
        console.print(f"  {task_db}: [yellow]NOT CREATED YET[/yellow]")

    # Git 仓库
    git_dir = project_dir / ".git"
    console.print("\n[bold]Git Repository:[/bold]")
    if git_dir.exists():
        console.print("  [green]OK[/green]")
    else:
        console.print("  [red]NOT INITIALIZED[/red]")

    # Dashboard 状态
    dashboard_state = data_dir / "dashboard" / "state.json"
    console.print("\n[bold]Dashboard State:[/bold]")
    if dashboard_state.exists():
        console.print(f"  {dashboard_state}: [green]EXISTS[/green]")
    else:
        console.print(f"  {dashboard_state}: [yellow]NOT CREATED YET[/yellow]")

    execution_plan = data_dir / "execution-plan.json"
    console.print("\n[bold]Execution Ledger:[/bold]")
    if execution_plan.exists():
        console.print(f"  {execution_plan}: [green]EXISTS[/green]")
    else:
        console.print(f"  {execution_plan}: [yellow]NOT CREATED YET[/yellow]")

    console.print(f"\n{'='*60}\n")


@app.command()
def dashboard(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
    port: int = typer.Option(8080, "-p", "--port", help="Dashboard 服务端口"),
    auto_start: bool = typer.Option(False, "--auto-start", help="自动启动执行循环"),
) -> None:
    """启动 Dashboard 后端服务（REST API + WebSocket）"""
    project_dir = Path(directory).resolve()
    state_dir = project_dir / "data" / "dashboard"
    state_dir.mkdir(parents=True, exist_ok=True)
    event_log = state_dir / "events.jsonl"

    from dashboard.api.routes import create_dashboard_app
    from dashboard.coordinator import PMCoordinator
    from dashboard.event_bus import EventBus
    from dashboard.state_repository import ProjectStateRepository

    event_bus = EventBus(log_file=event_log)
    repository = ProjectStateRepository(
        base_dir=state_dir,
        project_id=str(project_dir.name),
        run_id="dashboard-standalone",
    )
    pm = ProjectManager(project_dir) if project_dir.exists() else None
    coordinator = PMCoordinator(pm, repository, event_bus) if pm and pm._initialized else None
    fastapi_app = create_dashboard_app(event_bus, repository, coordinator, product_manager=pm)

    if auto_start and coordinator:
        result = coordinator.start_execution()
        console.print(f"[green]执行循环已自动启动: {result}[/green]")

    console.print(Panel.fit(
        f"[bold green]Dashboard 服务启动[/bold green]\n"
        f"项目目录: {project_dir}\n"
        f"REST API: http://localhost:{port}\n"
        f"WebSocket: ws://localhost:{port}/ws/dashboard\n"
        f"执行控制: {'PMCoordinator 已配置' if coordinator else 'standalone 模式'}",
        title="📊 Dashboard",
    ))

    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)


@app.command("explain-state")
def explain_state(
    directory: str = typer.Option("./project", "-d", "--dir", help="项目目录"),
) -> None:
    """用自然语言解释当前项目状态"""
    project_dir = Path(directory).resolve()
    _validate_project_dir(project_dir)

    from core.feature_tracker import FeatureTracker
    from dashboard.state_repository import ProjectStateRepository

    with _switch_data_dir(project_dir):
        state_dir = project_dir / "data" / "dashboard"
        if (state_dir / "state.json").exists():
            repo = ProjectStateRepository(base_dir=state_dir, project_id=str(project_dir.name))
            snapshot = repo.load_snapshot()
            features = snapshot.features
            summary = {
                "total": len(features),
                "done": sum(1 for f in features if f.status == "done"),
                "in_progress": sum(1 for f in features if f.status == "in_progress"),
                "blocked": sum(1 for f in features if f.status == "blocked"),
                "pending": sum(1 for f in features if f.status == "pending"),
            }
        else:
            tracker = FeatureTracker()
            features = tracker.all_features()
            summary = tracker.summary()

        console.print(Panel.fit(
            f"[bold]Project Status[/bold]\n"
            f"{summary['done']}/{summary['total']} features completed\n"
            f"{summary['in_progress']} in progress\n"
            f"{summary['blocked']} blocked\n"
            f"{summary['pending']} pending",
            title="📋 状态概览",
        ))

        if summary["blocked"] > 0:
            blocked = [f for f in features if f.status == "blocked"]
            console.print("\n[bold red]Blocking issues:[/bold red]")
            for f in blocked:
                last_error = f.error_log[-1] if f.error_log else "Unknown"
                console.print(f"  [red]- {f.id}:[/red] {last_error}")

        next_ready = next((f for f in features if f.status == "pending"), None)
        if next_ready:
            console.print(
                f"\n[bold green]Next feature to execute:[/bold green]\n"
                f"  [{next_ready.priority}] {next_ready.id}: {next_ready.description}"
            )
        else:
            console.print("\n[yellow]No features ready to execute.[/yellow]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
