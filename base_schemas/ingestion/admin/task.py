"""Admin helper: ensure a Task catalog row exists."""

from __future__ import annotations

from base_schemas.core.types import DjKey, DjRow
from base_schemas.schemas.scene.task import Task


def ensure_task(
    task: DjRow[Task],
    *,
    skip_duplicates: bool = True,
) -> DjKey[Task]:
    """Insert a task row if missing; return its primary key.

    Admin-only catalog write. Existing primary keys are left unchanged when
    ``skip_duplicates`` is true.

    Args:
        task: Full task insert dict (``task_name``, optional ``task_title``, …).
        skip_duplicates: Forwarded to DataJoint ``insert1``.

    Returns:
        Task primary key ``{task_name: ...}``.
    """
    Task.insert1(task, skip_duplicates=skip_duplicates)
    return {k: task[k] for k in Task.primary_key}
