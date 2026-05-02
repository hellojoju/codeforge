"""ContractManager 单元测试。"""

from pathlib import Path

from ralph.contract_manager import ContractManager
from ralph.schema.contract import InterfaceContract


def test_save_and_get(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    contract = InterfaceContract(
        contract_id="ct-1", name="Login API", method="POST", path="/api/login",
        request_schema={"email": "string", "password": "string"},
        response_schema={"token": "string"},
    )
    mgr.save(contract)
    loaded = mgr.get("ct-1")
    assert loaded is not None
    assert loaded.name == "Login API"


def test_freeze(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(contract_id="ct-1", name="API", method="GET", path="/api/data"))
    frozen = mgr.freeze("ct-1")
    assert frozen.status == "frozen"


def test_validate_consumer_missing_keys(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(
        contract_id="ct-1", name="API", method="GET", path="/api/data",
        response_schema={"id": "int", "name": "str"},
    ))
    issues = mgr.validate_consumer("ct-1", {"id": 1})
    assert len(issues) >= 1
    assert any("name" in i for i in issues)


def test_validate_consumer_passes(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(
        contract_id="ct-1", name="API", method="GET", path="/api/data",
        response_schema={"id": "int", "name": "str"},
    ))
    issues = mgr.validate_consumer("ct-1", {"id": 1, "name": "test"})
    assert len(issues) == 0


def test_list_contracts(tmp_path: Path):
    mgr = ContractManager(tmp_path / ".ralph")
    mgr.save(InterfaceContract(contract_id="c1", name="A", method="GET", path="/a"))
    mgr.save(InterfaceContract(contract_id="c2", name="B", method="POST", path="/b"))
    assert len(mgr.list_contracts()) == 2
