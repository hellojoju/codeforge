from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Rule:
    id: str
    dimension: str
    name: str
    checker: Callable[[dict[str, Any]], bool] | None = None


class RulesEngine:
    def __init__(self):
        self._rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self._rules.append(rule)

    def list_rules(self, dimension: str | None = None) -> list[Rule]:
        if dimension is None:
            return list(self._rules)
        return [r for r in self._rules if r.dimension == dimension]

    def rule_count(self, dimension: str | None = None) -> int:
        return len(self.list_rules(dimension))


def register_builtin_rules(engine: RulesEngine) -> None:
    engine.register(Rule(id="r1", dimension="correctness", name="No Empty Diff"))
    engine.register(Rule(id="r2", dimension="safety", name="No Secret Leak"))
    engine.register(Rule(id="r3", dimension="maintainability", name="Readable Changes"))
