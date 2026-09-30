"""Admin helper: ensure a Task catalog row exists."""

from __future__ import annotations

from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy, insert_tracked_row
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import TaskRowMeta
from base_schemas.schemas.scene.task import Task


def task_meta_payload(row: dict[str, Any]) -> dict[str, str]:
    """Non-key ``Task`` fields. A missing title hashes as an empty string."""
    return {"task_title": row.get("task_title") or ""}


def ensure_task(
    task: DjRow[Task],
    *,
    deployment: DjRow[Deployment] | None = None,
    if_exists: DuplicatePolicy = DuplicatePolicy.REJECT,
) -> DjKey[Task]:
    """Insert a task row and stamp the deployment that registered it.

    Runs atomically; joins the caller's transaction when one is open.

    Args:
        task: Full task insert dict (``task_name``, optional ``task_title``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        if_exists: Policy when ``task_name`` is already stored; see ``DuplicatePolicy``.

    Returns:
        Task primary key ``{task_name: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset, or ``if_exists`` rejects the existing row.
    """
    return insert_tracked_row(
        TaskRowMeta,
        task,
        payload=task_meta_payload(task),
        deployment=deployment if deployment is not None else deployment_row_from_settings(),
        if_exists=if_exists,
    )
