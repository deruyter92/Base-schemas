"""Admin helper: ensure a Task catalog row exists."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import insert_row_meta
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
    skip_duplicates: bool = True,
    manage_transaction: bool = True,
) -> DjKey[Task]:
    """Insert a task row if missing and stamp the deployment that registered it.

    With ``skip_duplicates``, an existing primary key is left unchanged,
    including a different title. The first ``TaskRowMeta`` stamp stays.

    Args:
        task: Full task insert dict (``task_name``, optional ``task_title``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        skip_duplicates: Forwarded to the ``Task`` and ``TaskRowMeta`` inserts.
        manage_transaction: Set to False if the caller already holds the transaction.

    Returns:
        Task primary key ``{task_name: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset.
    """
    deployment_row = deployment if deployment is not None else deployment_row_from_settings()
    deployment_key = {name: deployment_row[name] for name in Deployment.primary_key}
    row_key = {name: task[name] for name in Task.primary_key}
    with nullcontext() if not manage_transaction else Task.connection.transaction:
        Task.insert1(task, skip_duplicates=skip_duplicates)
        return insert_row_meta(
            row_key=row_key,
            row_meta_table=TaskRowMeta,
            payload=task_meta_payload(task),
            deployment_key=deployment_key,
            skip_duplicates=skip_duplicates,
            replace=False,
        )
