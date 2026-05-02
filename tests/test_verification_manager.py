"""VerificationManager 单元测试。"""

from pathlib import Path
from ralph.verification_manager import VerificationManager, VerificationChecklist
from ralph.schema.brainstorm_record import UserPath


def test_build_checklist(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    paths = [UserPath(name="main", steps=["step1", "step2"], edge_cases=["edge1"])]
    checklist = vm.build_checklist("wu-1", paths)
    assert checklist.work_id == "wu-1"
    assert len(checklist.user_paths) == 1


def test_verify_user_paths(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1", [UserPath(name="test", steps=["go to page"], edge_cases=[])])
    checklist = vm.verify_user_paths(checklist, "http://localhost:3000")
    assert len(checklist.checks) == 1
    assert "user_path" in checklist.checks[0]["check_name"]


def test_verify_boundary_states(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1")
    checklist = vm.verify_boundary_states(checklist)
    assert len(checklist.checks) == 4  # empty, loading, error, unauthorized


def test_verify_multi_size_screenshots(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1")
    checklist = vm.verify_multi_size_screenshots(checklist)
    assert len(checklist.checks) == 3  # mobile, tablet, desktop


def test_save_and_load(tmp_path: Path):
    vm = VerificationManager(tmp_path / ".ralph")
    checklist = vm.build_checklist("wu-1")
    vm.save_checklist(checklist)
    loaded = vm.get_checklist("wu-1")
    assert loaded is not None
    assert loaded.work_id == "wu-1"
