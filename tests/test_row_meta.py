"""Unit tests for provenance row-meta table definitions (no MySQL)."""

from __future__ import annotations

import pytest
from base_schemas.schemas.provenance.row_meta import (
    LabRowMeta,
    RowMetaBase,
    SessionRowMeta,
    SubjectRowMeta,
    TaskRowMeta,
)

_STAMP_COLUMNS = (
    "-> Deployment",
    "ingestion_version: varchar(32)",
    "content_hash: char(64)",
    "updated_at: datetime",
)


def test_row_meta_tracked_tables() -> None:
    for row_meta_table in RowMetaBase.__subclasses__():
        expected_parent = f"-> {row_meta_table.tracked_table.__name__}"

        assert row_meta_table.definition.lstrip().startswith(expected_parent), (
            f"{row_meta_table.__name__} tracks "
            f"{row_meta_table.tracked_table.__name__}, but its definition is "
            f"{row_meta_table.definition!r}"
        )


def test_row_meta_subclasses_match_tracked_masters() -> None:
    assert set(RowMetaBase.__subclasses__()) == {
        LabRowMeta,
        SubjectRowMeta,
        TaskRowMeta,
        SessionRowMeta,
    }
    assert LabRowMeta.tracked_table.__name__ == "Lab"
    assert SubjectRowMeta.tracked_table.__name__ == "Subject"
    assert TaskRowMeta.tracked_table.__name__ == "Task"
    assert SessionRowMeta.tracked_table.__name__ == "Session"


def test_definition_is_built_from_tracked_table_and_shared_attrs() -> None:
    for column in _STAMP_COLUMNS:
        assert column in RowMetaBase.ROW_META_ATTRS
    for row_meta_table in RowMetaBase.__subclasses__():
        assert row_meta_table.definition == RowMetaBase.build_definition(
            row_meta_table.tracked_table
        )


def test_tracked_key_returns_only_primary_key_fields() -> None:
    class _Tracked:
        primary_key = ["lab_id", "session_id"]

    class _Meta:
        tracked_table = _Tracked

    tracked_key = RowMetaBase.tracked_key.__func__
    row = {
        "lab_id": "mlai",
        "session_id": "abc",
        "session_code": "morning",
    }
    assert tracked_key(_Meta, row) == {"lab_id": "mlai", "session_id": "abc"}


def test_tracked_key_requires_primary_key_fields() -> None:
    class _Tracked:
        primary_key = ["subject_id"]

    class _Meta:
        tracked_table = _Tracked

    with pytest.raises(KeyError):
        RowMetaBase.tracked_key.__func__(_Meta, {"subject_kind": "mouse"})
