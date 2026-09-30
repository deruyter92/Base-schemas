"""Unit tests for register_session / register_subject writers (no MySQL)."""

from __future__ import annotations

from contextlib import ExitStack, nullcontext
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.hash import content_hash
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy
from base_schemas.ingestion.register import session as session_reg
from base_schemas.ingestion.register import subject as subject_reg


def test_new_session_id_is_uuid4_hex():
    sid = session_reg.new_session_id()
    assert len(sid) == 32
    assert sid != session_reg.new_session_id()
    int(sid, 16)


def test_build_deployment_row_from_settings_requires_env(monkeypatch):
    monkeypatch.delenv("SCENE_DEPLOYMENT_ID", raising=False)
    with pytest.raises(ValueError, match="SCENE_DEPLOYMENT_ID"):
        deployment_row_from_settings()


def test_build_deployment_row_from_settings(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env label")
    assert deployment_row_from_settings() == {
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
    payload = session_reg.session_etag_payload(session, subject_ids)
    assert payload == {
        "session_date": "2026-05-01",
        "session_name": "morning run",
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
        "subject_ids": subject_ids,
    }
    assert content_hash(payload) != content_hash({**payload, "session_name": "evening run"})


def test_register_session_rejects_empty_name(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "local")
    with pytest.raises(ValueError, match="session_name"):
        session_reg.register_session(
            "  ",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )


def _register_mocks(session_id: str):
    """No-op transaction, minted id, mocked Session.Subject and insert_tracked_row."""
    conn = MagicMock()
    conn.transaction = nullcontext()
    session_part = MagicMock()

    def _write(_meta, row, **_kwargs):
        return {"lab_id": row["lab_id"], "session_id": row["session_id"]}

    stack = ExitStack()
    stack.enter_context(patch.object(session_reg.Session, "_connection", conn))
    stack.enter_context(patch.object(session_reg.Session, "Subject", session_part))
    stack.enter_context(patch.object(session_reg, "new_session_id", return_value=session_id))
    write = stack.enter_context(patch.object(session_reg, "insert_tracked_row", side_effect=_write))
    return stack, session_part, write


def test_register_session_uses_settings_deployment(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    session_key = {"lab_id": "mlai", "session_id": "abc" * 10 + "ab"}
    subjects = [{"subject_id": "a" * 32}]

    stack, session_part, write = _register_mocks(session_key["session_id"])
    with stack:
        key = session_reg.register_session(
            " morning run ",
            date(2026, 5, 1),
            lab={"lab_id": "mlai"},
            subjects=subjects,
        )

    assert key == session_key
    session_row = {
        **session_key,
        "session_name": "morning run",
        "session_date": date(2026, 5, 1),
    }
    write.assert_called_once_with(
        session_reg.SessionRowMeta,
        session_row,
        payload=session_reg.session_etag_payload(session_row, ["a" * 32]),
        deployment={"deployment_id": "from-env", "label": "Env"},
        if_exists=DuplicatePolicy.REJECT,
    )
    session_part.insert.assert_called_once_with([{**session_key, "subject_id": "a" * 32}])


def test_register_session_allows_zero_subjects(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    session_key = {"lab_id": "mlai", "session_id": "d" * 32}
    stack, session_part, write = _register_mocks(session_key["session_id"])
    with stack:
        key = session_reg.register_session(
            "empty subjects",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )
    assert key == session_key
    session_part.insert.assert_not_called()
    assert write.call_args.kwargs["payload"]["subject_ids"] == []


def test_register_session_explicit_deployment_overrides_settings(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    deployment = {"deployment_id": "override", "label": "x"}
    stack, _, write = _register_mocks("x" * 32)
    with stack:
        session_reg.register_session(
            "s",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
            subjects=[{"subject_id": "b" * 32}],
            deployment=deployment,
        )
    assert write.call_args.kwargs["deployment"] == deployment


def test_register_session_writes_optional_lookup_fks(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    subjects = [{"subject_id": "a" * 32}, {"subject_id": "b" * 32}]
    stack, session_part, write = _register_mocks("c" * 32)
    with stack:
        session_reg.register_session(
            "rich session",
            date(2026, 6, 1),
            lab={"lab_id": "mlai"},
            subjects=subjects,
            task={"task_name": "gaze_v1"},
            experimenter={"experimenter_name": "alice"},
        )

    session_row = write.call_args.args[1]
    assert session_row["task_name"] == "gaze_v1"
    assert session_row["experimenter_name"] == "alice"
    part_rows = session_part.insert.call_args.args[0]
    assert [r["subject_id"] for r in part_rows] == ["a" * 32, "b" * 32]
    assert write.call_args.kwargs["payload"]["subject_ids"] == ["a" * 32, "b" * 32]


def test_new_subject_id_is_uuid4_hex():
    sid = subject_reg.new_subject_id()
    assert len(sid) == 32
    assert sid != subject_reg.new_subject_id()
    int(sid, 16)


def test_register_subject_delegates_to_insert_tracked_row(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    row = {"subject_id": "a" * 32, "subject_kind": "mouse"}
    with patch.object(
        subject_reg, "insert_tracked_row", return_value={"subject_id": "a" * 32}
    ) as write:
        key = subject_reg.register_subject(row)

    assert key == {"subject_id": "a" * 32}
    write.assert_called_once_with(
        subject_reg.SubjectRowMeta,
        row,
        payload={"subject_kind": "mouse"},
        deployment={"deployment_id": "from-env", "label": "Env"},
        if_exists=DuplicatePolicy.SKIP,
    )


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
    subjects = [
        {"subject_id": "a" * 32, "subject_kind": "mouse"},
        {"subject_id": "b" * 32, "subject_kind": "mouse"},
    ]
    session_key = {"lab_id": "mlai", "session_id": "e" * 32}
    subject_keys = [{"subject_id": "a" * 32}, {"subject_id": "b" * 32}]

    stack, session_part, write = _register_mocks(session_key["session_id"])
    with stack, patch.object(session_reg, "register_subject", side_effect=subject_keys) as reg_sub:
        key = session_reg.register_session_with_new_subjects(
            "with new subjects",
            date(2026, 7, 1),
            lab={"lab_id": "mlai"},
            subjects=subjects,
            if_exists=DuplicatePolicy.VERIFY,
        )

    assert key == session_key
    assert reg_sub.call_count == 2
    for subject in subjects:
        reg_sub.assert_any_call(
            subject,
            deployment={"deployment_id": "from-env", "label": ""},
            if_exists=DuplicatePolicy.VERIFY,
        )
    part_rows = session_part.insert.call_args.args[0]
    assert [r["subject_id"] for r in part_rows] == ["a" * 32, "b" * 32]
    assert write.call_args.kwargs["payload"]["subject_ids"] == ["a" * 32, "b" * 32]
    assert write.call_args.kwargs["if_exists"] is DuplicatePolicy.REJECT
    assert write.call_args.args[1]["session_name"] == "with new subjects"
