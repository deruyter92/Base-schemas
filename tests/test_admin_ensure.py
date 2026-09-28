"""Unit tests for admin ensure_* helpers (no MySQL)."""

from unittest.mock import MagicMock, patch

from base_schemas.ingestion.admin import lab as lab_admin
from base_schemas.ingestion.admin import task as task_admin


def test_ensure_lab_inserts_and_returns_key():
    row = {"lab_id": "mlai", "lab_name": "Mathis Lab"}
    table = MagicMock()
    table.primary_key = ["lab_id"]
    with patch.object(lab_admin, "Lab", table):
        key = lab_admin.ensure_lab(row)
    table.insert1.assert_called_once_with(row, skip_duplicates=True)
    assert key == {"lab_id": "mlai"}


def test_ensure_task_inserts_and_returns_key():
    row = {"task_name": "gaze_v1", "task_title": "Gaze"}
    table = MagicMock()
    table.primary_key = ["task_name"]
    with patch.object(task_admin, "Task", table):
        key = task_admin.ensure_task(row)
    table.insert1.assert_called_once_with(row, skip_duplicates=True)
    assert key == {"task_name": "gaze_v1"}
