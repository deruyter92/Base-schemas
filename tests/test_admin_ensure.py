"""Unit tests for admin ensure_* helpers (no MySQL)."""

from unittest.mock import MagicMock, patch

from base_schemas.ingestion.admin import lab as lab_admin
from base_schemas.ingestion.admin import task as task_admin


def test_ensure_lab_inserts_and_returns_key(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    row = {"lab_id": "mlai", "lab_name": "Mathis Lab"}
    table = MagicMock()
    table.primary_key = ["lab_id"]
    deployment = MagicMock()
    deployment.primary_key = ["deployment_id"]
    with patch.object(lab_admin, "Lab", table), patch.object(
        lab_admin, "Deployment", deployment
    ), patch.object(lab_admin, "insert_row_meta") as meta:
        meta.return_value = {"lab_id": "mlai"}
        key = lab_admin.ensure_lab(row)
    table.insert1.assert_called_once_with(row, skip_duplicates=True)
    meta.assert_called_once()
    assert meta.call_args.kwargs["row_key"] == {"lab_id": "mlai"}
    assert meta.call_args.kwargs["skip_duplicates"] is True
    assert key == {"lab_id": "mlai"}


def test_ensure_task_inserts_and_returns_key(monkeypatch):
    monkeypatch.setenv("SCENE_DEPLOYMENT_ID", "from-env")
    monkeypatch.setenv("SCENE_DEPLOYMENT_LABEL", "Env")
    row = {"task_name": "gaze_v1", "task_title": "Gaze"}
    table = MagicMock()
    table.primary_key = ["task_name"]
    deployment = MagicMock()
    deployment.primary_key = ["deployment_id"]
    with patch.object(task_admin, "Task", table), patch.object(
        task_admin, "Deployment", deployment
    ), patch.object(task_admin, "insert_row_meta") as meta:
        meta.return_value = {"task_name": "gaze_v1"}
        key = task_admin.ensure_task(row)
    table.insert1.assert_called_once_with(row, skip_duplicates=True)
    meta.assert_called_once()
    assert meta.call_args.kwargs["row_key"] == {"task_name": "gaze_v1"}
    assert meta.call_args.kwargs["skip_duplicates"] is True
    assert key == {"task_name": "gaze_v1"}
