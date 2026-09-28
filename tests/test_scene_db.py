"""Live-DB smoke tests for scene Lab / Session placeholders."""

import datetime as dt
import os

import pytest

_TRUTHY = frozenset({"1", "true", "yes", "on"})
# Deliberate mismatch row inserted by version tests; must not linger across runs.
_TEST_MISMATCH_VERSION = "0.0.0-test-mismatch"

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(
        not os.getenv("DJ_HOST"),
        reason="requires DataJoint DB (set DJ_HOST)",
    ),
    pytest.mark.skipif(
        (os.getenv("AUTO_ACTIVATE") or "").strip().lower() not in _TRUTHY,
        reason="tables are unbound unless AUTO_ACTIVATE is set",
    ),
]


def _clear_schema_version_test_rows(SchemaVersion):
    """Remove leftover mismatch rows (e.g. after a previous interrupted test)."""
    (SchemaVersion & {"version": _TEST_MISMATCH_VERSION}).delete(prompt=False)


def test_lab_session_insert_roundtrip(dj_connection):
    from base_schemas.schemas.scene.lab import Lab
    from base_schemas.schemas.scene.session import Session

    lab_key = {"lab_id": "testlab"}
    Lab.insert1(
        {**lab_key, "lab_name": "Test Lab", "institution": "Test U"},
        skip_duplicates=True,
    )
    session_id = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
    Session.insert1(
        {
            **lab_key,
            "session_id": session_id,
            "session_name": "test session",
            "session_date": dt.date(2026, 1, 15),
        },
        skip_duplicates=True,
    )

    assert (Lab & lab_key).fetch1("lab_name") == "Test Lab"
    assert (
        Session
        & {
            **lab_key,
            "session_id": session_id,
        }
    ).fetch1("session_date") == dt.date(2026, 1, 15)


def test_subject_task_and_multi_subject_session(dj_connection):
    from base_schemas.schemas.scene.lab import Lab
    from base_schemas.schemas.scene.session import Experimenter, Session
    from base_schemas.schemas.scene.subject import Subject, SubjectKind
    from base_schemas.schemas.scene.task import Task

    lab_key = {"lab_id": "spine"}
    Lab.insert1(
        {**lab_key, "lab_name": "Spine Lab", "institution": "Test U"},
        skip_duplicates=True,
    )
    assert len(SubjectKind()) >= 1

    Subject.insert1(
        {"subject_id": "11111111111111111111111111111111", "subject_kind": "mouse"},
        skip_duplicates=True,
    )
    Subject.insert1(
        {"subject_id": "22222222222222222222222222222222", "subject_kind": "mouse"},
        skip_duplicates=True,
    )
    Task.insert1(
        {"task_name": "gaze_v1", "task_title": "Gaze tracking"},
        skip_duplicates=True,
    )
    Experimenter.insert1(
        {"experimenter_name": "alice", "full_name": "Alice"},
        skip_duplicates=True,
    )

    session_key = {**lab_key, "session_id": "f0e1d2c3b4a5968778695a4b3c2d1e0f"}
    subject_ids = [
        "11111111111111111111111111111111",
        "22222222222222222222222222222222",
    ]
    session = {
        **session_key,
        "session_name": "multi-subject run",
        "session_date": dt.date(2026, 6, 1),
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
    }
    with Session.connection.transaction:
        Session.insert1(session, skip_duplicates=True)
        Session.Subject.insert(
            [{**session_key, "subject_id": sid} for sid in subject_ids],
            skip_duplicates=True,
        )

    row = (Session & session_key).fetch1()
    assert row["task_name"] == "gaze_v1"
    assert row["experimenter_name"] == "alice"
    assert set((Session.Subject & session_key).fetch("subject_id")) == set(subject_ids)


def test_register_session_mints_id_and_stores_name(dj_connection, monkeypatch):
    from base_schemas.core.hash import content_hash
    from base_schemas.ingestion import SCENE_WRITER_VERSION, register_session
    from base_schemas.ingestion.register.session_meta import session_etag_payload
    from base_schemas.schemas.provenance.row_meta import SessionRowMeta
    from base_schemas.schemas.scene.lab import Lab
    from base_schemas.schemas.scene.session import Experimenter, Session
    from base_schemas.schemas.scene.subject import Subject
    from base_schemas.schemas.scene.task import Task

    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "test-local")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "test")

    lab_key = {"lab_id": "reglab"}
    Lab.insert1(
        {**lab_key, "lab_name": "Register Lab", "institution": "Test U"},
        skip_duplicates=True,
    )
    subject_id = "33333333333333333333333333333333"
    Subject.insert1(
        {"subject_id": subject_id, "subject_kind": "mouse"},
        skip_duplicates=True,
    )
    Task.insert1(
        {"task_name": "reg_task", "task_title": "Register task"},
        skip_duplicates=True,
    )
    Experimenter.insert1(
        {"experimenter_name": "reg_user", "full_name": "Reg User"},
        skip_duplicates=True,
    )

    session_date = dt.date(2026, 5, 1)
    key = register_session(
        "Morning run",
        session_date,
        lab=lab_key,
        subjects=[{"subject_id": subject_id}],
        task={"task_name": "reg_task"},
        experimenter={"experimenter_name": "reg_user"},
    )
    assert key["lab_id"] == "reglab"
    assert len(key["session_id"]) == 32
    row = (Session & key).fetch1()
    assert row["session_name"] == "Morning run"
    assert row["session_date"] == session_date
    assert row["task_name"] == "reg_task"
    assert row["experimenter_name"] == "reg_user"
    assert list((Session.Subject & key).fetch("subject_id")) == [subject_id]
    meta = (SessionRowMeta & key).fetch1()
    assert meta["ingestion_version"] == SCENE_WRITER_VERSION
    assert meta["content_hash"] == content_hash(session_etag_payload(row, [subject_id]))
    assert meta["deployment_id"] == os.environ["SCENE_DEPLOYMENT_ID"]


def test_ensure_schema_version_idempotent_then_assert(dj_connection):
    from base_schemas.core.versioning import assert_schema_compatible, ensure_schema_version
    from base_schemas.schemas.scene._schema import (
        SCENE_SCHEMA_VERSION,
        SchemaVersion,
    )

    _clear_schema_version_test_rows(SchemaVersion)
    assert (
        ensure_schema_version(SCENE_SCHEMA_VERSION, SchemaVersion, notes="test-init")
        == SCENE_SCHEMA_VERSION
    )
    # Second call must not insert again or raise when already compatible.
    assert ensure_schema_version(SCENE_SCHEMA_VERSION, SchemaVersion) == (SCENE_SCHEMA_VERSION)
    assert assert_schema_compatible(SCENE_SCHEMA_VERSION, SchemaVersion) == (SCENE_SCHEMA_VERSION)


def test_assert_schema_compatible_mismatch_against_live_db(dj_connection):
    from datetime import datetime, timezone

    from base_schemas.core.versioning import (
        SchemaVersionError,
        assert_schema_compatible,
        ensure_schema_version,
    )
    from base_schemas.schemas.scene._schema import (
        SCENE_SCHEMA_VERSION,
        SchemaVersion,
    )

    _clear_schema_version_test_rows(SchemaVersion)
    ensure_schema_version(SCENE_SCHEMA_VERSION, SchemaVersion, notes="test-init")
    try:
        # Newer applied_at wins as "current" DB version → deliberate mismatch.
        SchemaVersion.insert1(
            {
                "version": _TEST_MISMATCH_VERSION,
                "applied_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "notes": "force mismatch for test",
            },
            skip_duplicates=True,
        )
        with pytest.raises(SchemaVersionError, match="mismatch"):
            assert_schema_compatible(SCENE_SCHEMA_VERSION, SchemaVersion)
    finally:
        _clear_schema_version_test_rows(SchemaVersion)
