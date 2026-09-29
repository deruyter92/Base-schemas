"""Register a Subject (everyday pipeline write)."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import insert_row_meta
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import SubjectRowMeta
from base_schemas.schemas.scene.subject import Subject


def new_subject_id() -> str:
    """Return a new opaque ``subject_id`` (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex


def subject_meta_payload(row: dict[str, Any]) -> dict[str, str]:
    """Non-key ``Subject`` fields."""
    return {"subject_kind": row["subject_kind"]}


def register_subject(
    subject: DjRow[Subject],
    *,
    deployment: DjRow[Deployment] | None = None,
    skip_duplicates: bool = True,
    manage_transaction: bool = True,
) -> DjKey[Subject]:
    """Insert a subject row and stamp the deployment that first registered it.

    The ``SubjectRowMeta`` hash covers ``subject_kind`` only. With
    ``skip_duplicates``, an existing primary key is left unchanged.

    Args:
        subject: Full subject insert dict (``subject_id``, ``subject_kind``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        skip_duplicates: Forwarded to the ``Subject`` and ``SubjectRowMeta``
            inserts.
        manage_transaction: Set to False if the caller already holds the transaction.

    Returns:
        Subject primary key ``{subject_id: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset.
    """
    deployment_row = deployment if deployment is not None else deployment_row_from_settings()
    deployment_key = {name: deployment_row[name] for name in Deployment.primary_key}
    row_key = {name: subject[name] for name in Subject.primary_key}
    with nullcontext() if not manage_transaction else Subject.connection.transaction:
        Subject.insert1(subject, skip_duplicates=skip_duplicates)
        return insert_row_meta(
            row_key=row_key,
            row_meta_table=SubjectRowMeta,
            payload=subject_meta_payload(subject),
            deployment_key=deployment_key,
            skip_duplicates=skip_duplicates,
            replace=False,
        )
