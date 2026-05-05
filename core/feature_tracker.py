"""ProjectStateRepository 的薄适配层，提供 Feature 操作便利方法。"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from typing import TYPE_CHECKING

from core.progress_logger import progress
from core.state_models import Feature

if TYPE_CHECKING:
    from dashboard.state_repository import ProjectStateRepository


class FeatureTracker:
    """管理 Feature 列表的增删改查，委托给 ProjectStateRepository。"""

    def __init__(self, *, repository: ProjectStateRepository):
        self._repository = repository

    def add(self, feature) -> None:
        self._repository.upsert_feature(feature)

    def bulk_add(self, features: list) -> None:
        for f in features:
            self._repository.upsert_feature(f)
        progress.log(f"批量导入 {len(features)} 个features")

    def get(self, feature_id: str):
        return self._repository.get_feature(feature_id)

    def get_next_ready(self):
        """获取下一个可执行的 feature（依赖全部完成、优先级最高）。"""
        return self._repository.get_next_ready_feature()

    def _update_feature(self, feature_id: str, **updates: str) -> None:
        """更新 feature 字段。Repository 模式下深拷贝后写入，否则就地修改。"""
        if self._repository is not None:
            existing = self._repository.get_feature(feature_id)
            if existing is None:
                return
            existing = copy.deepcopy(existing)
            for key, value in updates.items():
                setattr(existing, key, value)
            self._repository.upsert_feature(existing, event_type="feature_updated")
        else:
            f = self.get(feature_id)
            if f:
                for key, value in updates.items():
                    setattr(f, key, value)
                self._save()

    def mark_in_progress(self, feature_id: str, instance_id: str = "", workspace_path: str = "") -> None:
        updates = {
            "status": "in_progress",
            "assigned_instance": instance_id,
            "workspace_path": workspace_path,
            "started_at": datetime.now().isoformat(),
        }
        self._update_feature(feature_id, **updates)
        f = self.get(feature_id)
        if f:
            progress.log(f"{feature_id} 开始开发: {f.description}")

    def mark_review(self, feature_id: str) -> None:
        self._update_feature(feature_id, status="review")
        progress.log(f"{feature_id} 进入验收阶段")

    def mark_done(self, feature_id: str, files_changed: list[str] | None = None) -> None:
        updates = {
            "status": "done",
            "passes": True,
            "completed_at": datetime.now().isoformat(),
        }
        if files_changed:
            updates["files_changed"] = files_changed
        self._update_feature(feature_id, **updates)
        f = self.get(feature_id)
        if f:
            progress.log(f"{feature_id} 完成: {f.description}")

    def mark_blocked(self, feature_id: str, reason: str) -> None:
        f = self.get(feature_id)
        if f:
            error_log = list(getattr(f, "error_log", []))
            error_log.append(reason)
            self._update_feature(
                feature_id,
                status="blocked",
                error_log=error_log,
            )
            progress.log(f"{feature_id} 被阻塞: {reason}")

    def mark_pending(self, feature_id: str, reason: str = "") -> None:
        """退回重试：将 feature 状态重置为 pending，追加错误日志。"""
        if self._repository is not None:
            f = self.get(feature_id)
            if f:
                error_log = list(getattr(f, "error_log", []))
                if reason:
                    error_log.append(reason)
                self._update_feature(feature_id, status="pending", error_log=error_log)
        else:
            f = self.get(feature_id)
            if f:
                f.status = "pending"
                if reason:
                    f.error_log.append(reason)
                self._save()

    def add_error(self, feature_id: str, error: str) -> None:
        f = self.get(feature_id)
        if f:
            error_log = list(getattr(f, "error_log", []))
            error_log.append(error)
            self._update_feature(feature_id, error_log=error_log)

    def summary(self) -> dict:
        return self._repository.feature_summary()

    def all_done(self) -> bool:
        return self._repository.all_features_done()

    def all_features(self) -> list:
        return self._repository.list_features()
