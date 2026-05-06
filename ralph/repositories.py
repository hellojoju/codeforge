from __future__ import annotations

from pathlib import Path

from ralph.repository import RalphRepository


class FeatureRepository:
    def __init__(self, ralph_dir: Path | str):
        self._repo = RalphRepository(Path(ralph_dir))

    def list(self):
        return self._repo.list_features()

    def get(self, feature_id: str):
        return self._repo.get_feature(feature_id)

    def save(self, feature) -> None:
        self._repo.save_feature(feature)
