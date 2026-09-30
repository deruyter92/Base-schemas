# SCENE Base-schemas

Shared [DataJoint](https://datajoint.com/) table definitions for SCENE pipelines.
Keeping them in one package keeps provenance and session structure aligned across labs.

Current package schemas (placeholders; definitions may change):

- `base_schemas.schemas.scene.lab` — `Lab`
- `base_schemas.schemas.scene.subject` — `SubjectKind`, `Subject`
- `base_schemas.schemas.scene.task` — `Task`
- `base_schemas.schemas.scene.session` — `Experimenter`, `Session`
- `base_schemas.schemas.provenance.deployment` — `Deployment`
- `base_schemas.schemas.provenance.row_meta` — `LabRowMeta`, `TaskRowMeta`,
  `SubjectRowMeta`, `SessionRowMeta` (one stamp per tracked row: deployment,
  writer version, content hash)

Also included:

- `base_schemas.scripts.sync` — copy table rows between servers
- `base_schemas.ingestion` — supported write path (`register_session`, …);
- `base_schemas.ingestion.admin` — catalog ensures (`ensure_lab`, `ensure_task`; admin DB role);

## Inserting rows

Write through the helpers in ``base_schemas.ingestion`` rather than calling
``insert1`` directly. Every helper writes the row and a row-meta stamp
(``LabRowMeta``, ``SessionRowMeta``, …) that records which deployment wrote
it, the ``SCENE_WRITER_VERSION``, and a ``content_hash`` of the row's content.
The stamps are what later lets rows be compared and synced between databases.

### Deployment id and label

Set ``SCENE_DEPLOYMENT_ID`` once per database (optional
``SCENE_DEPLOYMENT_LABEL``). The helpers read it when ``deployment`` is not
passed explicitly, and insert the matching ``Deployment`` row on first use.

The id is a stable, opaque token: pick a short slug that names the lab and the
role of the database, e.g. ``mlai-prod`` for the production database of the
Mathis Lab of Adaptive Intelligence, or ``mlai-dev-jaap`` for a private
development copy. Do not derive it from a hostname or the schema prefix; those
may change, the id must not. The label is free text for humans and may change.

### Admin catalog tables

``Lab`` and ``Task`` are catalog tables shared across the collaboration. They
are marked ``SyncAuthority.CENTRAL`` and ``WriteRole.ADMIN`` (acquisition
accounts SELECT only) and are created with the helpers in
``base_schemas.ingestion.admin``:

- ``ensure_lab`` — insert a lab row, return its key
- ``ensure_task`` — insert a task row, return its key

``Experimenter`` is still a plain shared lookup; seed it directly.

### Pipeline writes

``Subject`` and ``Session`` are everyday writes, marked ``WriteRole.ACQUISITION``
(acquisition accounts only). They are inserted locally by one team and later
shared with the consortium. Helpers live in ``base_schemas.ingestion``:

- ``register_subject`` — register a subject by code, return its key
- ``register_session`` — register a session by code, linking **existing**
  subject keys (may be empty)

Subjects and sessions are identified by a code the lab chooses
(``subject_code``, ``session_code``), unique within the lab. The globally
unique ``subject_id`` / ``session_id`` is minted by the helper (UUID4 hex) the
first time a code is registered. Registering the same code again reuses the
stored id, so re-running an ingestion does not create duplicates.

Codes are shared with the consortium, so they must be **pseudonyms**: never a
real name, initials, birth date or other identifying information. The helpers
accept only ASCII letters, digits, ``.``, ``_`` and ``-`` (no spaces), which
rejects free-text names but cannot catch every identifying code.

```python
from datetime import date
from base_schemas.ingestion import register_session, register_subject

lab = {"lab_id": "mlai"}
subject = register_subject("mouse-042", "mouse", lab=lab)
register_session(
    "mousear-session-015",
    date(2026, 5, 1),
    lab=lab,
    subjects=[subject],
    task={"task_name": "gaze_v1"},
)
```

Each helper is atomic and joins a transaction that is already open. To make
several registrations all-or-nothing, wrap them in ``atomic``:

```python
from base_schemas.core import atomic
from base_schemas.schemas.scene.session import Session

with atomic(Session.connection):
    subjects = [register_subject(code, "mouse", lab=lab) for code in ("mouse-043", "mouse-044")]
    register_session("mousear-session-016", date(2026, 5, 2), lab=lab, subjects=subjects)
```

### Registering an existing entry again

The helpers take ``if_exists: DuplicatePolicy`` to control what happens when
the entry already exists (same primary key for ``ensure_*``, same code within
the lab for ``register_*``). Unlike DataJoint's ``skip_duplicates`` /
``replace``, this policy compares the ``content_hash`` in the stored stamp,
detecting changed content:

| Policy | When the entry already exists |
|--------|-------------------------------|
| ``REJECT`` (default for ``ensure_*``) | raise ``ValueError`` |
| ``SKIP`` | leave row and stamp untouched |
| ``VERIFY`` (default for ``register_*``) | leave untouched when the stamp hash matches; raise when it differs or no stamp exists |
| ``UPDATE`` | ``update1`` the row and its stamp (sessions: also their subject links); warn when the hash changed |

```python
from base_schemas.ingestion.admin import ensure_lab
from base_schemas.ingestion.provenance import DuplicatePolicy

ensure_lab({"lab_id": "mlai", "lab_name": "Mathis Lab"}, if_exists=DuplicatePolicy.VERIFY)
```

## Table markers

Two optional markers record intent; they enforce nothing. Read them with
``sync_authority_of`` and ``write_role_of``.

``SyncAuthority`` names which database holds the truth: ``CENTRAL`` (consortium
catalogs; central wins a conflict), ``ORIGIN`` (the deployment in the row's
stamp wins), ``SHARED`` (append-only, either direction inserts and never
overwrites; ``Deployment``). Unmarked means ``ORIGIN``. ``Deployment`` is
``SHARED``.

``WriteRole`` restricts INSERT: ``ADMIN`` or ``ACQUISITION``, and a marker
admits only that role. No marker means unrestricted. ``Lab`` and ``Task`` are
``ADMIN``; ``Subject`` and ``Session`` are ``ACQUISITION``. A part follows its
master and a row-meta table follows the table it tracks, so those need no
marker of their own. Lab-defined tables need none either.

## Schema activation

Schemas stay unbound by default (no DB needed on import). Set
``AUTO_ACTIVATE=1`` to bind eagerly, or activate explicitly:

```python
from base_schemas.core import SCENE_REGISTRY, activate_schema, load_settings

schema = SCENE_REGISTRY.make_schema("scene")  # unbound unless AUTO_ACTIVATE
# @schema class Lab ...
SCENE_REGISTRY.activate("scene")  # uses context stored at make_schema
SCENE_REGISTRY.activate_all()

# Or bind any dj.Schema without the registry:
activate_schema(schema, "scene")

# Repeated registration returns the same instance
SCENE_REGISTRY.make_schema("scene") is schema

# Accessing the registry content
"scene" in SCENE_REGISTRY.schemas  # dict[str, dj.Schema]
SCENE_REGISTRY.get("scene") is schema
```

| Variable | Meaning |
|----------|---------|
| `DJ_SCHEMA_PREFIX` | Prefix for DB names (include trailing `_`) |
| `AUTO_ACTIVATE` | If truthy, `make_schema` / Lab / Session bind on import |
| `SCENE_DEPLOYMENT_ID` | Stable id of this database; default `deployment` for all insertion helpers |
| `SCENE_DEPLOYMENT_LABEL` | Optional human label stored on `Deployment` with the env default |

## Installation

```bash
# development
pip install -e ".[dev]"

# usage
pip install .
```

From GitHub (`main` can be a commit hash or branch):

```bash
pip install "git+ssh://git@github.com/SCENE-Collaboration/Base-schemas.git@main"
pip install "git+https://github.com/SCENE-Collaboration/Base-schemas.git@main"
```

Build a wheel:

```bash
pip install build
python -m build .
pip install dist/base_schemas-*.whl
```

## Quickstart (Docker)

```bash
make init          # once: copy .env.example → .env, then edit as needed
make build_all
make up_all
make client_bash
```

Host port for MySQL is `MYSQL_PUBLISH_PORT` in `.env` (default `3306`).
Schema names use `DJ_SCHEMA_PREFIX`.

## Tests

```bash
make test          # unit tests: pytest tests/ -m "not db"
make test-db       # MySQL via compose, then pytest tests/ -m db
```

Mark live-DB tests with `@pytest.mark.db` (registered in `pyproject.toml`).

## Acknowledgments

We thank Prof. Mackenzie Mathis, Dr. Tanmay Nath, Dr. Gary Kane, and Dr. Mariia Popova for their early contributions to this codebase, which helped establish the foundation of the shared schemas used across pipelines.
