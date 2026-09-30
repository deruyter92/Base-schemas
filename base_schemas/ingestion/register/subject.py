"""Register a Subject (everyday pipeline write)."""

from __future__ import annotations

from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.db import atomic, lookup_key, new_id
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.normalization.code import normalize_code
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy, insert_tracked_row
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import SubjectRowMeta
from base_schemas.schemas.scene.lab import Lab
from base_schemas.schemas.scene.subject import Subject, SubjectKind


def subject_meta_payload(row: dict[str, Any]) -> dict[str, str]:
    """Non-key ``Subject`` fields."""
    return {
        "lab_id": row["lab_id"],
        "subject_code": row["subject_code"],
        "subject_kind": row["subject_kind"],
    }


def register_subject(
    subject_code: str,
    subject_kind: DjKey[SubjectKind] | str,
    *,
    lab: DjKey[Lab],
    deployment: DjRow[Deployment] | None = None,
    if_exists: DuplicatePolicy = DuplicatePolicy.VERIFY,
) -> DjKey[Subject]:
    """Register a subject by its lab code; mint ``subject_id`` when new.

    The subject is looked up by ``(lab, subject_code)``. A new code gets a
    freshly minted ``subject_id``; an existing code is handled by ``if_exists``
    against the stored subject. Runs atomically; joins the caller's
    transaction when one is open.

    Args:
        subject_code: Pseudonymous code, unique within ``lab``; see
            ``normalize_code``. Never a real name.
        subject_kind: Existing ``SubjectKind`` key or its name, e.g. ``"mouse"``.
        lab: Existing lab primary key, e.g. ``{"lab_id": "mlai"}``.
        deployment: Optional deployment row. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        if_exists: Policy when ``subject_code`` is already registered in
            ``lab``; see ``DuplicatePolicy``. The default ``VERIFY`` returns
            the stored key when the content matches and raises otherwise.

    Returns:
        Subject primary key ``{subject_id: ...}``.

    Raises:
        ValueError: If ``subject_code`` is not a valid code, ``deployment`` is omitted
            and ``SCENE_DEPLOYMENT_ID`` is unset, or ``if_exists`` rejects the
            existing subject.
    """
    code = normalize_code(subject_code, field="subject_code", max_length=64)
    kind = subject_kind["subject_kind"] if isinstance(subject_kind, dict) else subject_kind
    deployment_row = deployment if deployment is not None else deployment_row_from_settings()

    with atomic(Subject.connection):
        # insert_tracked_row matches on the primary key, which is minted: resolve an
        # existing code to its stored id first, so if_exists applies to re-registrations.
        existing = lookup_key(Subject, {**lab, "subject_code": code})
        row = {
            "subject_id": existing["subject_id"] if existing else new_id(),
            **lab,
            "subject_code": code,
            "subject_kind": kind,
        }
        return insert_tracked_row(
            SubjectRowMeta,
            row,
            payload=subject_meta_payload(row),
            deployment=deployment_row,
            if_exists=if_exists,
        )
