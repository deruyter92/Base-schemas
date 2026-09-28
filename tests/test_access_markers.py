"""Access-intent markers on schema tables (no DB required)."""

from base_schemas.core.access_markers import AccessRole
from base_schemas.schemas.scene.lab import Lab
from base_schemas.schemas.scene.session import Session
from base_schemas.schemas.scene.subject import Subject
from base_schemas.schemas.scene.task import Task


def test_lab_and_task_marked_admin_write():
    assert Lab._access_role is AccessRole.ADMIN_WRITE
    assert Task._access_role is AccessRole.ADMIN_WRITE


def test_subject_and_session_marked_pipeline_write():
    assert Subject._access_role is AccessRole.PIPELINE_WRITE
    assert Session._access_role is AccessRole.PIPELINE_WRITE
