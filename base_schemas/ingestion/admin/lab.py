"""Admin helper: ensure a Lab catalog row exists."""

from __future__ import annotations

from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy, insert_tracked_row
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import LabRowMeta
from base_schemas.schemas.scene.lab import Lab


def lab_meta_payload(row: dict[str, Any]) -> dict[str, str]:
    """Non-key ``Lab`` fields. Missing names hash as empty strings."""
    return {
        "lab_name": row.get("lab_name") or "",
        "institution": row.get("institution") or "",
    }


def ensure_lab(
    lab: DjRow[Lab],
    *,
    deployment: DjRow[Deployment] | None = None,
    if_exists: DuplicatePolicy = DuplicatePolicy.REJECT,
) -> DjKey[Lab]:
    """Insert a lab row and stamp the deployment that registered it.

    Runs atomically; joins the caller's transaction when one is open.

    Args:
        lab: Full lab insert dict (``lab_id``, optional ``lab_name``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        if_exists: Policy when ``lab_id`` is already stored; see ``DuplicatePolicy``.

    Returns:
        Lab primary key ``{lab_id: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset, or ``if_exists`` rejects the existing row.
    """
    return insert_tracked_row(
        LabRowMeta,
        lab,
        payload=lab_meta_payload(lab),
        deployment=deployment if deployment is not None else deployment_row_from_settings(),
        if_exists=if_exists,
    )
