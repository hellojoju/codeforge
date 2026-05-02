"""ContractManager — 接口合同管理与变更验证。"""

from __future__ import annotations

import json
from pathlib import Path

from ralph.schema.contract import InterfaceContract


class ContractManager:
    """接口合同管理：定义、冻结、消费者验证。"""

    def __init__(self, ralph_dir: Path):
        self._dir = ralph_dir / "contracts"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, contract: InterfaceContract) -> InterfaceContract:
        path = self._dir / f"{contract.contract_id}.json"
        path.write_text(json.dumps(
            {k: v for k, v in contract.__dict__.items() if not k.startswith("_")},
            indent=2, ensure_ascii=False, default=str,
        ))
        return contract

    def get(self, contract_id: str) -> InterfaceContract | None:
        path = self._dir / f"{contract_id}.json"
        if not path.is_file():
            return None
        return InterfaceContract(**json.loads(path.read_text()))

    def list_contracts(self) -> list[dict]:
        contracts = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                contracts.append({
                    "contract_id": data.get("contract_id", f.stem),
                    "name": data.get("name", ""),
                    "method": data.get("method", ""),
                    "path": data.get("path", ""),
                    "status": data.get("status", ""),
                })
            except Exception:
                continue
        return contracts

    def freeze(self, contract_id: str) -> InterfaceContract:
        contract = self.get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        contract.freeze()
        return self.save(contract)

    def validate_consumer(
        self, contract_id: str, consumer_impl: dict,
    ) -> list[str]:
        """验证消费者实现是否符合合同。返回问题列表。"""
        contract = self.get(contract_id)
        if not contract:
            return [f"Contract {contract_id} not found"]

        issues = []
        if contract.response_schema:
            keys_expected = set(contract.response_schema.keys())
            keys_actual = set(consumer_impl.keys())
            missing = keys_expected - keys_actual
            if missing:
                issues.append(f"Missing keys: {missing}")
            extra = keys_actual - keys_expected
            if extra:
                issues.append(f"Unexpected keys: {extra}")

        return issues
