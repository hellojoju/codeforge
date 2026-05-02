"""MemoryArchiver 单元测试。"""

from pathlib import Path

from ralph.memory_archiver import MemoryArchiver


def test_append_short_term_basic(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "accepted", "title": "Login API"})
    memory = ma.get_short_term()
    assert len(memory) == 1
    assert memory[0]["work_id"] == "wu-1"


def test_fifo_eviction_to_medium(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    for i in range(25):
        ma.append_short_term({"work_id": f"wu-{i}", "status": "accepted", "title": f"Task {i}"})

    assert len(ma.get_short_term()) <= 20
    medium = ma.get_medium_term()
    assert len(medium) > 0


def test_record_decision(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.record_decision("使用 SQLite", "轻量无需运维", ["PostgreSQL", "MongoDB"])
    medium = ma.get_medium_term()
    assert len(medium) == 1
    assert medium[0]["type"] == "decision"


def test_search(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "accepted", "title": "JWT Auth"})
    ma.append_short_term({"work_id": "wu-2", "status": "running", "title": "CRUD API"})
    results = ma.search("JWT")
    assert len(results) >= 1
    assert results[0]["entry"]["title"] == "JWT Auth"


def test_get_status(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-1", "status": "done"})
    status = ma.get_status()
    assert status["short_term"]["count"] == 1
    assert "total_stored" in status


def test_summarize_short_term(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    ma.append_short_term({"work_id": "wu-a", "status": "accepted", "title": "Auth"})
    ma.append_short_term({"work_id": "wu-b", "status": "running", "title": "API"})
    summary = ma.summarize_short_term()
    assert "Auth" in summary
    assert "API" in summary


def test_archive_task_log(tmp_path: Path):
    ma = MemoryArchiver(tmp_path / ".ralph")
    path = ma.archive_task_log("wu-log", "# Task Log\n\n完成内容...")
    assert Path(path).is_file()
    assert "# Task Log" in Path(path).read_text()
