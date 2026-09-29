"""Admin helper: ensure a Lab catalog row exists."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import insert_row_meta
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
    skip_duplicates: bool = True,
    manage_transaction: bool = True,
) -> DjKey[Lab]:
    """Insert a lab row if missing and stamp the deployment that registered it.

    With ``skip_duplicates``, an existing primary key is left unchanged,
    including a different lab name or institution. The first ``LabRowMeta``
    stamp stays.

    Args:
        lab: Full lab insert dict (``lab_id``, optional ``lab_name``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        skip_duplicates: Forwarded to the ``Lab`` and ``LabRowMeta`` inserts.
        manage_transaction: Set to False if the caller already holds the transaction.

    Returns:
        Lab primary key ``{lab_id: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset.
    """
    deployment_row = deployment if deployment is not None else deployment_row_from_settings()
    deployment_key = {name: deployment_row[name] for name in Deployment.primary_key}
    row_key = {name: lab[name] for name in Lab.primary_key}
    with nullcontext() if not manage_transaction else Lab.connection.transaction:
        Lab.insert1(lab, skip_duplicates=skip_duplicates)
        return insert_row_meta(
            row_key=row_key,
            row_meta_table=LabRowMeta,
            payload=lab_meta_payload(lab),
            deployment_key=deployment_key,
            skip_duplicates=skip_duplicates,
            replace=False,
        )
