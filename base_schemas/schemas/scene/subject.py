"""SCENE-shared subject identity."""

import datajoint as dj

from base_schemas.core.access_markers import WriteRole, mark_write_role
from base_schemas.schemas.scene._schema import schema
from base_schemas.schemas.scene.lab import Lab  # noqa: F401  # FK: Subject -> Lab


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


@mark_write_role(WriteRole.ACQUISITION)
@schema
class Subject(dj.Manual):
    """Individual identity (human, mouse, other), registered by one lab.

    ``subject_id`` is minted by ``register_subject``; the lab refers to the
    subject by ``subject_code``, which is unique within that lab. The code is
    a pseudonym: never a real name, initials, birth date or other identifying
    information (it is shared with the consortium).
    """

    definition = """
    subject_id: varchar(64)  # minted UUID4 hex; never renamed
    ---
    -> Lab
    subject_code: varchar(64)  # pseudonymous lab code, e.g. P012; never a real name
    -> SubjectKind
    unique index (lab_id, subject_code)
    """
