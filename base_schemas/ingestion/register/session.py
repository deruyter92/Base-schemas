"""Register a Session from existing keys (+ Deployment + SessionRowMeta)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy, insert_tracked_row
from base_schemas.ingestion.register.subject import register_subject
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import SessionRowMeta
from base_schemas.schemas.scene.lab import Lab
from base_schemas.schemas.scene.session import Experimenter, Session
from base_schemas.schemas.scene.subject import Subject
from base_schemas.schemas.scene.task import Task


def new_session_id() -> str:
    """Return a new opaque ``session_id`` (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex


def session_etag_payload(
    session: dict[str, Any],
    subject_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Non-key session fields + subjects that should affect ``content_hash``."""
    return {
        "session_date": str(session["session_date"]),
        "session_name": session["session_name"],
        "task_name": session.get("task_name"),
        "experimenter_name": session.get("experimenter_name"),
        "subject_ids": list(subject_ids),
    }


def _insert_session_bundle(
    *,
    lab: DjKey[Lab],
    name: str,
    session_date: date,
    subjects: Sequence[DjKey[Subject]],
    task: DjKey[Task] | None,
    experimenter: DjKey[Experimenter] | None,
    deployment_row: DjRow[Deployment],
) -> DjKey[Session]:
    """Write Session + stamp + Subject links for a freshly minted id (caller holds the txn)."""
    subject_ids = [s["subject_id"] for s in subjects]
    session = {
        **lab,
        "session_id": new_session_id(),
        "session_name": name,
        "session_date": session_date,
        **(task or {}),
        **(experimenter or {}),
    }
    # The id is minted, so an existing key is a bug rather than a re-registration.
    session_key = insert_tracked_row(
        SessionRowMeta,
        session,
        payload=session_etag_payload(session, subject_ids),
        deployment=deployment_row,
        if_exists=DuplicatePolicy.REJECT,
    )
    if subject_ids:
        Session.Subject.insert([{**session_key, "subject_id": sid} for sid in subject_ids])
    return session_key


def register_session(
    session_name: str,
    session_date: date,
    *,
    lab: DjKey[Lab],
    subjects: Sequence[DjKey[Subject]] = (),
    task: DjKey[Task] | None = None,
    experimenter: DjKey[Experimenter] | None = None,
    deployment: DjRow[Deployment] | None = None,
) -> DjKey[Session]:
    """Insert a session (and link optional subjects) with deployment provenance.

    Catalog keys (``lab``, ``subjects``, ``task``, ``experimenter``) must already
    exist; this helper does not create them. ``session_id`` is minted, so every
    call creates a new session. Writes run in one transaction.

    Args:
        session_name: User-facing session label (non-empty after strip).
        session_date: Calendar date of the session.
        lab: Existing lab primary key, e.g. ``{"lab_id": "mlai"}``.
        subjects: Existing subject keys (may be empty).
        task: Optional existing task key.
        experimenter: Optional existing experimenter key.
        deployment: Optional deployment row to stamp with. If omitted, built
            from ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.

    Returns:
        Session primary key ``{lab_id, session_id}``.

    Raises:
        ValueError: If ``session_name`` is empty, or ``deployment`` is omitted
            and ``SCENE_DEPLOYMENT_ID`` is unset.
    """
    name = session_name.strip()
    if not name:
        raise ValueError("session_name must be a non-empty string")

    deployment_row = deployment if deployment is not None else deployment_row_from_settings()

    with Session.connection.transaction:
        return _insert_session_bundle(
            lab=lab,
            name=name,
            session_date=session_date,
            subjects=subjects,
            task=task,
            experimenter=experimenter,
            deployment_row=deployment_row,
        )


def register_session_with_new_subjects(
    session_name: str,
    session_date: date,
    *,
    lab: DjKey[Lab],
    subjects: Sequence[DjRow[Subject]],
    task: DjKey[Task] | None = None,
    experimenter: DjKey[Experimenter] | None = None,
    deployment: DjRow[Deployment] | None = None,
    if_exists: DuplicatePolicy = DuplicatePolicy.SKIP,
) -> DjKey[Session]:
    """Insert subject rows, then register a session linking them (one transaction).

    ``subjects`` are full insert dicts and are written first (existing
    ``subject_id`` values are handled by ``if_exists``). ``lab``, ``task`` and
    ``experimenter`` are primary keys of rows that must already exist.

    Args:
        session_name: User-facing session label (non-empty after strip).
        session_date: Calendar date of the session.
        lab: Existing lab primary key.
        subjects: Subject insert rows (``subject_id``, ``subject_kind``, …).
        task: Optional existing task key.
        experimenter: Optional existing experimenter key.
        deployment: Optional deployment row; else from settings env vars.
        if_exists: Policy for subjects whose ``subject_id`` is already stored;
            forwarded to ``register_subject``. The default ``SKIP`` keeps them.

    Returns:
        Session primary key ``{lab_id, session_id}``.

    Raises:
        ValueError: If ``session_name`` is empty, ``subjects`` is empty,
            ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID`` is unset, or
            ``if_exists`` rejects an existing subject.
    """
    name = session_name.strip()
    if not name:
        raise ValueError("session_name must be a non-empty string")
    if not subjects:
        raise ValueError("subjects must be a non-empty sequence of subject rows")

    deployment_row = deployment if deployment is not None else deployment_row_from_settings()

    with Session.connection.transaction:
        subject_keys = [
            register_subject(row, deployment=deployment_row, if_exists=if_exists)
            for row in subjects
        ]
        return _insert_session_bundle(
            lab=lab,
            name=name,
            session_date=session_date,
            subjects=subject_keys,
            task=task,
            experimenter=experimenter,
            deployment_row=deployment_row,
        )
