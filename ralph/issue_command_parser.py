from __future__ import annotations

from typing import Any


def comment_to_command(comment_data: dict[str, Any], issue_number: str) -> dict[str, Any] | None:
    body = str(comment_data.get("body", "")).strip()
    if not body.startswith("/ralph"):
        return None

    parts = body.split()
    if len(parts) < 2:
        return {"type": "issue_help", "issue_number": issue_number}

    cmd = parts[1].lower()
    arg = parts[2] if len(parts) >= 3 else ""
    mapping = {
        "approve": "approve_decision",
        "reject": "reject_decision",
        "retry": "retry_feature",
        "pause": "pause_feature",
        "resume": "resume_feature",
        "ship": "ship_work_unit",
        "sync": "sync_issues",
    }
    command_type = mapping.get(cmd)
    if not command_type:
        return {"type": "issue_help", "issue_number": issue_number, "raw": body}

    return {"type": command_type, "work_id": arg, "issue_number": issue_number, "raw": body}
