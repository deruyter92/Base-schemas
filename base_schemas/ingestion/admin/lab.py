"""Admin helper: ensure a Lab catalog row exists."""

from __future__ import annotations

from base_schemas.core.types import DjKey, DjRow
from base_schemas.schemas.scene.lab import Lab


def ensure_lab(
    lab: DjRow[Lab],
    *,
    skip_duplicates: bool = True,
) -> DjKey[Lab]:
    """Insert a lab row if missing; return its primary key.

    Admin-only catalog write. Existing primary keys are left unchanged when
    ``skip_duplicates`` is true.

    Args:
        lab: Full lab insert dict (``lab_id``, optional ``lab_name``, …).
        skip_duplicates: Forwarded to DataJoint ``insert1``.

    Returns:
        Lab primary key ``{lab_id: ...}``.
    """
    Lab.insert1(lab, skip_duplicates=skip_duplicates)
    return {k: lab[k] for k in Lab.primary_key}
