"""Unit tests for register_session / register_subject writers (no MySQL)."""

from __future__ import annotations

from contextlib import ExitStack, nullcontext
from datetime import date
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from base_schemas.core.config import deployment_row_from_settings
from base_schemas.core.db import new_id
from base_schemas.core.hash import content_hash
from base_schemas.ingestion.provenance.row_meta import DuplicatePolicy
from base_schemas.ingestion.register import session as session_reg
from base_schemas.ingestion.register import subject as subject_reg


def test_new_id_is_uuid4_hex():
    minted = new_id()
    assert len(minted) == 32
    assert minted != new_id()
    int(minted, 16)


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


def test_session_meta_payload_includes_lookups_and_subjects():
    session = {
        "lab_id": "mlai",
        "session_id": "deadbeef" * 4,
        "session_code": "morning-run",
        "session_date": date(2026, 5, 1),
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
    }
    subject_ids = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
    payload = session_reg.session_meta_payload(session, subject_ids)
    assert payload == {
        "session_date": "2026-05-01",
        "session_code": "morning-run",
        "task_name": "gaze_v1",
        "experimenter_name": "alice",
        "subject_ids": subject_ids,
    }
    assert content_hash(payload) != content_hash({**payload, "session_code": "evening-run"})


def test_register_session_rejects_empty_name(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "local")
    with pytest.raises(ValueError, match="session_code"):
        session_reg.register_session(
            "  ",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )


def _fake_connection():
    conn = MagicMock()
    conn.in_transaction = False
    conn.transaction = nullcontext()
    return conn


def _register_mocks(session_id: str, *, existing: dict | None = None):
    """No-op transaction, minted id, mocked lookup, Session.Subject and insert_tracked_row."""
    session_part = MagicMock()

    def _write(_meta, row, **_kwargs):
        return {"lab_id": row["lab_id"], "session_id": row["session_id"]}

    stack = ExitStack()
    stack.enter_context(patch.object(session_reg.Session, "_connection", _fake_connection()))
    stack.enter_context(patch.object(session_reg.Session, "Subject", session_part))
    stack.enter_context(patch.object(session_reg, "new_id", return_value=session_id))
    stack.enter_context(patch.object(session_reg, "lookup_key", return_value=existing))
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
            " morning-run ",
            date(2026, 5, 1),
            lab={"lab_id": "mlai"},
            subjects=subjects,
        )

    assert key == session_key
    session_row = {
        **session_key,
        "session_code": "morning-run",
        "session_date": date(2026, 5, 1),
    }
    write.assert_called_once_with(
        session_reg.SessionRowMeta,
        session_row,
        payload=session_reg.session_meta_payload(session_row, ["a" * 32]),
        deployment={"deployment_id": "from-env", "label": "Env"},
        if_exists=DuplicatePolicy.VERIFY,
        parts={session_part: [{"subject_id": "a" * 32}]},
    )


def test_register_session_allows_zero_subjects(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    session_key = {"lab_id": "mlai", "session_id": "d" * 32}
    stack, session_part, write = _register_mocks(session_key["session_id"])
    with stack:
        key = session_reg.register_session(
            "empty-subjects",
            date(2026, 1, 1),
            lab={"lab_id": "mlai"},
        )
    assert key == session_key
    assert write.call_args.kwargs["parts"] == {session_part: []}
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
            "rich-session",
            date(2026, 6, 1),
            lab={"lab_id": "mlai"},
            subjects=subjects,
            task={"task_name": "gaze_v1"},
            experimenter={"experimenter_name": "alice"},
        )

    session_row = write.call_args.args[1]
    assert session_row["task_name"] == "gaze_v1"
    assert session_row["experimenter_name"] == "alice"
    part_rows = write.call_args.kwargs["parts"][session_part]
    assert [r["subject_id"] for r in part_rows] == ["a" * 32, "b" * 32]
    assert write.call_args.kwargs["payload"]["subject_ids"] == ["a" * 32, "b" * 32]


@pytest.mark.parametrize("policy", list(DuplicatePolicy))
def test_register_session_existing_code_reuses_id(monkeypatch, policy):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    existing = {"lab_id": "mlai", "session_id": "0" * 32}
    stack, _, write = _register_mocks("1" * 32, existing=existing)
    with stack:
        key = session_reg.register_session(
            "morning-run",
            date(2026, 5, 1),
            lab={"lab_id": "mlai"},
            subjects=[{"subject_id": "a" * 32}],
            if_exists=policy,
        )
    assert key == existing
    assert write.call_args.args[1]["session_id"] == "0" * 32
    assert write.call_args.kwargs["if_exists"] is policy


def test_register_session_joins_open_transaction(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    conn = MagicMock()
    conn.in_transaction = True
    type(conn).transaction = PropertyMock(side_effect=AssertionError("nested transaction"))
    stack, _, write = _register_mocks("f" * 32)
    with stack, patch.object(session_reg.Session, "_connection", conn):
        session_reg.register_session("s", date(2026, 1, 1), lab={"lab_id": "mlai"})
    write.assert_called_once()


def _subject_mocks(*, existing: dict | None = None, minted: str = "a" * 32):
    stack = ExitStack()
    stack.enter_context(patch.object(subject_reg.Subject, "_connection", _fake_connection()))
    stack.enter_context(patch.object(subject_reg, "new_id", return_value=minted))
    lookup = stack.enter_context(patch.object(subject_reg, "lookup_key", return_value=existing))
    write = stack.enter_context(
        patch.object(
            subject_reg,
            "insert_tracked_row",
            side_effect=lambda _meta, row, **_: {"subject_id": row["subject_id"]},
        )
    )
    return stack, lookup, write


def test_register_subject_mints_id_for_new_name(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    stack, lookup, write = _subject_mocks()
    with stack:
        key = subject_reg.register_subject(" P012 ", "mouse", lab={"lab_id": "mlai"})

    assert key == {"subject_id": "a" * 32}
    lookup.assert_called_once_with(subject_reg.Subject, {"lab_id": "mlai", "subject_code": "P012"})
    row = {
        "subject_id": "a" * 32,
        "lab_id": "mlai",
        "subject_code": "P012",
        "subject_kind": "mouse",
    }
    write.assert_called_once_with(
        subject_reg.SubjectRowMeta,
        row,
        payload={"lab_id": "mlai", "subject_code": "P012", "subject_kind": "mouse"},
        deployment={"deployment_id": "from-env", "label": "Env"},
        if_exists=DuplicatePolicy.VERIFY,
    )


def test_register_subject_existing_name_reuses_id(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    stack, _, write = _subject_mocks(existing={"subject_id": "0" * 32})
    with stack:
        key = subject_reg.register_subject(
            "P012", {"subject_kind": "mouse"}, lab={"lab_id": "mlai"}
        )
    assert key == {"subject_id": "0" * 32}
    assert write.call_args.args[1]["subject_kind"] == "mouse"


def test_register_subject_rejects_empty_name(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    with pytest.raises(ValueError, match="subject_code"):
        subject_reg.register_subject("  ", "mouse", lab={"lab_id": "mlai"})
