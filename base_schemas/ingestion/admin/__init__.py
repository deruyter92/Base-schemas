"""Admin catalog writes (Lab, Task, …).

Pipeline roles should SELECT these tables only; use these helpers with an
admin DB role. ``Lab`` and ``Task`` are marked ``WriteRole.ADMIN``.
"""

from base_schemas.ingestion.admin.lab import ensure_lab
from base_schemas.ingestion.admin.task import ensure_task

__all__ = ["ensure_lab", "ensure_task"]
