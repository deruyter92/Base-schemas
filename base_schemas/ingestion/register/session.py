"""Register a Session from existing keys (+ Deployment + SessionRowMeta)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.types import DjKey, DjRow
from base_schemas.ingestion.provenance.row_meta import insert_row_meta
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


def _upsert_session_row_meta(
    session_key: DjKey[Session],
    session: dict[str, Any],
    *,
    deployment_key: DjKey[Deployment],
    subject_ids: Sequence[str] = (),
    writer_version: str | None = None,
) -> None:
    """Insert or replace ``SessionRowMeta`` for a session."""
    insert_row_meta(
        row_key=session_key,
        row_meta_table=SessionRowMeta,
        payload=session_etag_payload(session, subject_ids),
        deployment_key=deployment_key,
        writer_version=writer_version,
        replace=True,
        skip_duplicates=False,
    )


def _insert_session_bundle(
    *,
    lab: DjKey[Lab],
    name: str,
    session_date: date,
    subjects: Sequence[DjKey[Subject]],
    task: DjKey[Task] | None,
    experimenter: DjKey[Experimenter] | None,
    deployment_row: DjRow[Deployment],
    skip_duplicates: bool,
) -> DjKey[Session]:
    """Write Deployment + Session + Subject links + row meta (caller owns txn)."""
    deployment_key: DjKey[Deployment] = {k: deployment_row[k] for k in Deployment.primary_key}
    subject_ids = [s["subject_id"] for s in subjects]
    session_id = new_session_id()
    session = {
        **lab,
        "session_id": session_id,
        "session_name": name,
        "session_date": session_date,
        **(task or {}),
        **(experimenter or {}),
    }
    session_key: DjKey[Session] = {**lab, "session_id": session_id}

    Deployment.insert1(deployment_row, skip_duplicates=skip_duplicates)
    Session.insert1(session, skip_duplicates=skip_duplicates)
    if subject_ids:
        Session.Subject.insert(
            [{**session_key, "subject_id": sid} for sid in subject_ids],
            skip_duplicates=skip_duplicates,
        )
    _upsert_session_row_meta(
        session_key,
        session,
        deployment_key=deployment_key,
        subject_ids=subject_ids,
    )
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
    skip_duplicates: bool = True,
) -> DjKey[Session]:
    """Insert a session (and link optional subjects) with deployment provenance.

    Catalog keys (``lab``, ``subjects``, ``task``, ``experimenter``) must already
    exist; this helper does not create them. ``session_id`` is minted. Writes run
    in one transaction.

    Args:
        session_name: User-facing session label (non-empty after strip).
        session_date: Calendar date of the session.
        lab: Existing lab primary key, e.g. ``{"lab_id": "mlai"}``.
        subjects: Existing subject keys (may be empty).
        task: Optional existing task key.
        experimenter: Optional existing experimenter key.
        deployment: Optional deployment row to insert. If omitted, built from
            ``SCENE_DEPLOYMENT_ID`` / ``SCENE_DEPLOYMENT_LABEL``.
        skip_duplicates: Forwarded to DataJoint inserts.

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
            skip_duplicates=skip_duplicates,
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
    skip_duplicates: bool = True,
) -> DjKey[Session]:
    """Insert subject rows, then register a session linking them (one transaction).

    ``subjects`` must be full insert dicts (not keys only). Existing primary keys
    are left unchanged when ``skip_duplicates`` is true (attributes are not
    updated). ``lab`` / ``task`` / ``experimenter`` remain existing keys only.

    Args:
        session_name: User-facing session label (non-empty after strip).
        session_date: Calendar date of the session.
        lab: Existing lab primary key.
        subjects: Subject insert rows (``subject_id``, ``subject_kind``, …).
        task: Optional existing task key.
        experimenter: Optional existing experimenter key.
        deployment: Optional deployment row; else from settings env vars.
        skip_duplicates: Forwarded to DataJoint inserts.

    Returns:
        Session primary key ``{lab_id, session_id}``.

    Raises:
        ValueError: If ``session_name`` is empty, ``subjects`` is empty, or
            ``deployment`` is omitted and ``SCENE_DEPLOYMENT_ID`` is unset.
    """
    name = session_name.strip()
    if not name:
        raise ValueError("session_name must be a non-empty string")
    if not subjects:
        raise ValueError("subjects must be a non-empty sequence of subject rows")

    deployment_row = deployment if deployment is not None else deployment_row_from_settings()

    with Session.connection.transaction:
        subject_keys = [
            register_subject(
                row,
                deployment=deployment_row,
                skip_duplicates=skip_duplicates,
                manage_transaction=False,
            )
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
            skip_duplicates=skip_duplicates,
        )
