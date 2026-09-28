"""SCENE-shared subject identity."""

import datajoint as dj

from base_schemas.core.access_markers import AccessRole, mark_access_role
from base_schemas.schemas.scene._schema import schema


@schema
class SubjectKind(dj.Lookup):
    """Extensible vocabulary for ``Subject.kind`` — insert a row to add a kind."""

    definition = """
    subject_kind: varchar(32)  # e.g. human, mouse, other
    ---
    kind_description='': varchar(255)
    """

    contents = [
        {"subject_kind": "human", "kind_description": "human participant"},
        {"subject_kind": "mouse", "kind_description": "mouse model"},
        {"subject_kind": "bat", "kind_description": "bat model"},
        {"subject_kind": "rl-agent", "kind_description": "reinforcement learning agent"},
        {"subject_kind": "other", "kind_description": "other / unspecified"},
    ]


@mark_access_role(AccessRole.PIPELINE_WRITE)
@schema
class Subject(dj.Manual):
    """Lab-agnostic individual identity (human, mouse, other)."""

    definition = """
    subject_id: varchar(64)  # opaque stable token; never renamed
    ---
    -> SubjectKind
    """
