"""Register a Subject (everyday pipeline write)."""

from __future__ import annotations

import uuid
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy, insert_tracked_row
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
    if_exists: DuplicatePolicy = DuplicatePolicy.SKIP,
) -> DjKey[Subject]:
    """Insert a subject row and stamp the deployment that registered it.

    The ``SubjectRowMeta`` hash covers ``subject_kind`` only. Runs atomically;
    joins the caller's transaction when one is open.

    Args:
        subject: Full subject insert dict (``subject_id``, ``subject_kind``, …).
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        if_exists: Policy when ``subject_id`` is already stored; see
            ``DuplicatePolicy``. The default ``SKIP`` keeps the stored row.

    Returns:
        Subject primary key ``{subject_id: ...}``.

    Raises:
        ValueError: If ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID``
            is unset, or ``if_exists`` rejects the existing row.
    """
    return insert_tracked_row(
        SubjectRowMeta,
        subject,
        payload=subject_meta_payload(subject),
        deployment=deployment if deployment is not None else deployment_row_from_settings(),
        if_exists=if_exists,
    )
