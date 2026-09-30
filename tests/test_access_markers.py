"""Sync authority and write role markers (no DB required)."""

from __future__ import annotations

import pytest
from base_schemas.core.access_markers import (
    SyncAuthority,
    WriteRole,
    sync_authority_of,
    write_role_of,
)
from base_schemas.schemas.provenance.deployment import Deployment
from base_schemas.schemas.provenance.row_meta import RowMetaBase
from base_schemas.schemas.scene.lab import Lab
from base_schemas.schemas.scene.session import Experimenter, Session
from base_schemas.schemas.scene.subject import Subject, SubjectKind
from base_schemas.schemas.scene.task import Task


def test_catalogs_are_central_and_admin_only():
    for table in (Lab, Task):
        assert sync_authority_of(table) is SyncAuthority.CENTRAL
        assert write_role_of(table) is WriteRole.ADMIN


def test_acquired_rows_are_acquisition_only_and_origin_by_default():
    for table in (Subject, Session):
        assert not hasattr(table, "_sync_authority")
        assert sync_authority_of(table) is SyncAuthority.ORIGIN
        assert write_role_of(table) is WriteRole.ACQUISITION


def test_unmarked_tables_are_unrestricted():
    for table in (Experimenter, SubjectKind):
        assert write_role_of(table) is None
        assert sync_authority_of(table) is SyncAuthority.ORIGIN


def test_deployment_is_shared_and_unrestricted():
    assert sync_authority_of(Deployment) is SyncAuthority.SHARED
    assert write_role_of(Deployment) is None


def test_part_follows_its_master():
    assert not hasattr(Session.Subject, "_write_role")
    assert write_role_of(Session.Subject) is WriteRole.ACQUISITION
    assert sync_authority_of(Session.Subject) is SyncAuthority.ORIGIN


@pytest.mark.parametrize("table", list(RowMetaBase.__subclasses__()))
def test_row_meta_follows_tracked_table(table):
    assert not hasattr(table, "_sync_authority")
    assert not hasattr(table, "_write_role")
    assert sync_authority_of(table) is sync_authority_of(table.tracked_table)
    assert write_role_of(table) is write_role_of(table.tracked_table)


def test_unmarked_class_defaults():
    class LabSpecificLookup:
        """Stands in for a table a lab defines for its own analysis."""

    assert sync_authority_of(LabSpecificLookup) is SyncAuthority.ORIGIN
    assert write_role_of(LabSpecificLookup) is None
