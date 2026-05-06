"""Smoke verify Ralph API endpoints are mounted and callable.

Run:
    python scripts/verify_ralph_endpoints.py
"""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.api.routes import create_dashboard_app
from dashboard.event_bus import EventBus
from dashboard.state_repository import ProjectStateRepository


def main() -> int:
    repo = ProjectStateRepository(
        base_dir=Path(tempfile.mkdtemp()),
        project_id="verify",
        run_id="verify",
    )
    app = create_dashboard_app(EventBus(), repository=repo)
    client = TestClient(app)

    checks: list[tuple[str, str, dict | None, tuple[int, ...]]] = [
        ("/api/ralph/health", "GET", None, (200,)),
        ("/api/ralph/capabilities", "GET", None, (200,)),
        ("/api/ralph/memory/status", "GET", None, (200,)),
        ("/api/ralph/memory/search?q=test", "GET", None, (200,)),
        ("/api/ralph/memory/l1-snapshot", "GET", None, (200,)),
        ("/api/ralph/memory/compact", "POST", {"work_id": "missing"}, (200,)),
        ("/api/ralph/context/pm", "POST", {"mode": "schedule"}, (200,)),
        ("/api/ralph/context/incremental", "POST", {"work_id": "wu-1"}, (200,)),
        ("/api/ralph/pm/status", "GET", None, (200,)),
        ("/api/ralph/pm/context", "GET", None, (200,)),
        ("/api/ralph/pm/schedule", "POST", {}, (200,)),
        ("/api/ralph/knowledge-graph/status", "GET", None, (200,)),
        ("/api/ralph/knowledge-graph/data", "GET", None, (200,)),
        ("/api/ralph/knowledge-graph/impact?file_path=README.md", "GET", None, (200,)),
        ("/api/ralph/search?q=demo", "GET", None, (200,)),
        (
            "/api/ralph/projects/pipeline",
            "POST",
            {"path": str(Path("/Users/jieson/auto-coding")), "prd_text": "demo"},
            (200,),
        ),
        (
            "/api/ralph/projects/deep-analyze",
            "POST",
            {"path": str(Path("/Users/jieson/auto-coding"))},
            (200,),
        ),
        ("/api/ralph/executions", "GET", None, (200,)),
        ("/api/ralph/budget", "GET", None, (200,)),
        ("/api/ralph/budget", "PUT", {"enabled": False, "daily_token_limit": 500000}, (200,)),
        ("/api/ralph/workspaces", "GET", None, (200,)),
        ("/api/ralph/issues/config", "GET", None, (200,)),
        ("/api/ralph/issues/sync-status", "GET", None, (200,)),
        ("/api/ralph/releases", "GET", None, (200,)),
        ("/api/recovery-report", "GET", None, (200,)),
    ]

    failed = 0
    for path, method, payload, expected in checks:
        if method == "GET":
            res = client.get(path)
        elif method == "POST":
            res = client.post(path, json=payload)
        elif method == "PUT":
            res = client.put(path, json=payload)
        else:
            raise ValueError(f"Unsupported method: {method}")
        ok = res.status_code in expected
        print(f"{method:4} {path:<45} -> {res.status_code} {'OK' if ok else 'FAIL'}")
        if not ok:
            failed += 1

    print(f"\nsummary: total={len(checks)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
