"""SpecChangeManager 单元测试。"""

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

    change = mgr.create_change(SpecChange(
        change_id="ch-1", title="Add remember-me", proposal="...", design="...",
        tasks=["t1"], spec_deltas=[{"spec_id": "auth", "field": "title", "new": "Auth v2"}],
    ))
    assert change.status == "proposed"

    approved = mgr.approve_change("ch-1")
    assert approved is not None
    assert approved.status == "approved"

    applied = mgr.apply_change("ch-1")
    assert applied is not None
    assert applied.status == "applied"

    updated = mgr.get_spec("auth")
    assert updated is not None
    assert updated.title == "Auth v2"


def test_reject_change(tmp_path: Path):
    mgr = SpecChangeManager(tmp_path / ".ralph")
    mgr.create_change(SpecChange(change_id="ch-r", title="Bad idea", proposal="no"))
    rejected = mgr.reject_change("ch-r")
    assert rejected is not None
    assert rejected.status == "rejected"


def test_list_changes(tmp_path: Path):
    mgr = SpecChangeManager(tmp_path / ".ralph")
    mgr.create_change(SpecChange(change_id="c1", title="Change 1", proposal="p1"))
    mgr.create_change(SpecChange(change_id="c2", title="Change 2", proposal="p2"))
    assert len(mgr.list_changes()) == 2
