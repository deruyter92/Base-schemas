"""Unit tests for register_session / SessionRowMeta writers (no MySQL)."""

from __future__ import annotations

from contextlib import ExitStack, nullcontext
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from base_schemas.core.hash import content_hash
from base_schemas.ingestion.register import session as session_reg
from base_schemas.ingestion.register import session_meta as meta_reg


def test_new_session_id_is_uuid4_hex():
    sid = session_reg.new_session_id()
    assert len(sid) == 32
    assert sid != session_reg.new_session_id()
    int(sid, 16)


def test_build_deployment_row_from_settings_requires_env(monkeypatch):
    monkeypatch.delenv("SCENE_DEPLOYMENT_ID", raising=False)
    with pytest.raises(ValueError, match="SCENE_DEPLOYMENT_ID"):
        session_reg._build_deployment_row_from_settings()


def test_build_deployment_row_from_settings(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env label")
    assert session_reg._build_deployment_row_from_settings() == {
        "deployment_id": "from-env",
        "label": "Env label",
    }


def test_session_etag_payload_includes_lookups_and_subjects():
    session = {
        "lab_id": "mlai",
        "session_id": "deadbeef" * 4,
        "session_name": "morning run",
        "session_date": date(2026, 5, 1),
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
    }
    subject_ids = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    payload = meta_reg.session_etag_payload(session, subject_ids)
    assert payload == {
        "session_date": "2026-05-01",
        "session_name": "morning run",
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
        "subject_ids": subject_ids,
    }
    assert content_hash(payload) != content_hash({**payload, "session_name": "evening run"})


def test_upsert_session_row_meta_writes_version_hash_and_deployment():
    key = {"lab_id": "mlai", "session_id": "abc" * 10 + "ab"}
    session = {
        **key,
        "session_name": "morning run",
        "session_date": date(2026, 5, 1),
        "task_name": None,
        "experimenter_name": None,
    }
    subject_ids = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    with patch.object(meta_reg.SessionRowMeta, "insert1") as ins:
        meta_reg.upsert_session_row_meta(
            key,
            session,
            deployment_key={"deployment_id": "dep1"},
            subject_ids=subject_ids,
        )

    row = ins.call_args.args[0]
    assert row["deployment_id"] == "dep1"
    assert row["ingestion_version"] == meta_reg.SCENE_WRITER_VERSION
    assert row["content_hash"] == content_hash(meta_reg.session_etag_payload(session, subject_ids))
    assert ins.call_args.kwargs["replace"] is True


def test_upsert_session_row_meta_honors_writer_version_override():
    key = {"lab_id": "mlai", "session_id": "x" * 32}
    session = {**key, "session_name": "s", "session_date": date(2026, 1, 1)}
    with patch.object(meta_reg.SessionRowMeta, "insert1") as ins:
        meta_reg.upsert_session_row_meta(
            key,
            session,
            deployment_key={"deployment_id": "dep1"},
            writer_version="9.9.9",
        )
    assert ins.call_args.args[0]["ingestion_version"] == "9.9.9"


def test_register_session_rejects_empty_name(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "local")
    with pytest.raises(ValueError, match="session_name"):
        session_reg.register_session(
            "  ",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )


def _register_mocks(**tables):
    """No-op transaction + mocked tables for register_session unit tests."""
    conn = MagicMock()
    conn.transaction = nullcontext()
    session_part = MagicMock()
    stack = ExitStack()
    stack.enter_context(patch.object(session_reg.Session, "_connection", conn))
    sess_ins = stack.enter_context(patch.object(session_reg.Session, "insert1"))
    stack.enter_context(patch.object(session_reg.Session, "Subject", session_part))
    upsert = stack.enter_context(patch.object(session_reg, "upsert_session_row_meta"))
    for name, table in tables.items():
        stack.enter_context(patch.object(session_reg, name, table))
    return stack, sess_ins, session_part, upsert


def test_register_session_uses_settings_deployment(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    lab = {"lab_id": "mlai"}
    subjects = [{"subject_id": "a" * 32}]
    dep_table = MagicMock()
    dep_table.primary_key = ["deployment_id"]
    session_key = {"lab_id": "mlai", "session_id": "abc" * 10 + "ab"}

    stack, sess_ins, session_part, upsert_meta = _register_mocks(Deployment=dep_table)
    with stack, patch.object(session_reg, "new_session_id", return_value=session_key["session_id"]):
        key = session_reg.register_session(
            " morning run ",
            date(2026, 5, 1),
            lab=lab,
            subjects=subjects,
        )

    assert key == session_key
    dep_table.insert1.assert_called_once_with(
        {"deployment_id": "from-env", "label": "Env"},
        skip_duplicates=True,
    )
    session_row = sess_ins.call_args.args[0]
    assert session_row == {
        "lab_id": "mlai",
        "session_id": session_key["session_id"],
        "session_name": "morning run",
        "session_date": date(2026, 5, 1),
    }
    session_part.insert.assert_called_once()
    upsert_meta.assert_called_once_with(
        key,
        session_row,
        deployment_key={"deployment_id": "from-env"},
        subject_ids=["a" * 32],
    )


def test_register_session_allows_zero_subjects(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    dep_table = MagicMock()
    dep_table.primary_key = ["deployment_id"]
    session_key = {"lab_id": "mlai", "session_id": "d" * 32}
    stack, _, session_part, upsert_meta = _register_mocks(Deployment=dep_table)
    with stack, patch.object(session_reg, "new_session_id", return_value=session_key["session_id"]):
        key = session_reg.register_session(
            "empty subjects",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )
    assert key == session_key
    session_part.insert.assert_not_called()
    assert upsert_meta.call_args.kwargs["subject_ids"] == []


def test_register_session_explicit_deployment_overrides_settings(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    lab = {"lab_id": "mlai"}
    subjects = [{"subject_id": "b" * 32}]
    deployment = {"deployment_id": "override", "label": "x"}
    dep_table = MagicMock()
    dep_table.primary_key = ["deployment_id"]
    stack, _, _, upsert_meta = _register_mocks(Deployment=dep_table)
    with stack, patch.object(session_reg, "new_session_id", return_value="x" * 32):
        session_reg.register_session(
            "s",
            date(2026, 1, 1),
            lab=lab,
            subjects=subjects,
            deployment=deployment,
        )
    dep_table.insert1.assert_called_once_with(deployment, skip_duplicates=True)
    assert upsert_meta.call_args.kwargs["deployment_key"] == {"deployment_id": "override"}


def test_register_session_writes_optional_lookup_fks(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    lab = {"lab_id": "mlai"}
    subjects = [
        {"subject_id": "a" * 32},
        {"subject_id": "b" * 32},
    ]
    task = {"task_name": "gaze_v1"}
    experimenter = {"experimenter_name": "alice"}
    dep_table = MagicMock()
    dep_table.primary_key = ["deployment_id"]
    session_key = {"lab_id": "mlai", "session_id": "c" * 32}

    stack, sess_ins, session_part, _ = _register_mocks(Deployment=dep_table)
    with stack, patch.object(session_reg, "new_session_id", return_value=session_key["session_id"]):
        session_reg.register_session(
            "rich session",
            date(2026, 6, 1),
            lab=lab,
            subjects=subjects,
            task=task,
            experimenter=experimenter,
        )

    session_row = sess_ins.call_args.args[0]
    assert session_row["task_name"] == "gaze_v1"
    assert session_row["experimenter_name"] == "alice"
    part_rows = session_part.insert.call_args.args[0]
    assert [r["subject_id"] for r in part_rows] == ["a" * 32, "b" * 32]


def test_new_subject_id_is_uuid4_hex():
    from base_schemas.ingestion.register import subject as subject_reg

    sid = subject_reg.new_subject_id()
    assert len(sid) == 32
    assert sid != subject_reg.new_subject_id()
    int(sid, 16)


def test_register_subject_inserts_and_returns_key():
    from base_schemas.ingestion.register import subject as subject_reg

    row = {"subject_id": "a" * 32, "subject_kind": "mouse"}
    table = MagicMock()
    table.primary_key = ["subject_id"]
    with patch.object(subject_reg, "Subject", table):
        key = subject_reg.register_subject(row)
    table.insert1.assert_called_once_with(row, skip_duplicates=True)
    assert key == {"subject_id": "a" * 32}


def test_register_session_with_new_subjects_rejects_empty(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    with pytest.raises(ValueError, match="subjects must be a non-empty"):
        session_reg.register_session_with_new_subjects(
            "s",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
            subjects=[],
        )


def test_register_session_with_new_subjects_inserts_then_session(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    lab = {"lab_id": "mlai"}
    subjects = [
        {"subject_id": "a" * 32, "subject_kind": "mouse"},
        {"subject_id": "b" * 32, "subject_kind": "mouse"},
    ]
    dep_table = MagicMock()
    dep_table.primary_key = ["deployment_id"]
    session_key = {"lab_id": "mlai", "session_id": "e" * 32}
    subject_keys = [{"subject_id": "a" * 32}, {"subject_id": "b" * 32}]

    stack, sess_ins, session_part, upsert_meta = _register_mocks(Deployment=dep_table)
    with stack, patch.object(
        session_reg, "new_session_id", return_value=session_key["session_id"]
    ), patch.object(session_reg, "register_subject", side_effect=subject_keys) as reg_sub:
        key = session_reg.register_session_with_new_subjects(
            "with new subjects",
            date(2026, 7, 1),
            lab=lab,
            subjects=subjects,
        )

    assert key == session_key
    assert reg_sub.call_count == 2
    reg_sub.assert_any_call(subjects[0], skip_duplicates=True)
    reg_sub.assert_any_call(subjects[1], skip_duplicates=True)
    part_rows = session_part.insert.call_args.args[0]
    assert [r["subject_id"] for r in part_rows] == ["a" * 32, "b" * 32]
    assert upsert_meta.call_args.kwargs["subject_ids"] == ["a" * 32, "b" * 32]
    assert sess_ins.call_args.args[0]["session_name"] == "with new subjects"
