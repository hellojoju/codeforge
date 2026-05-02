"""接口合同数据结构。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
