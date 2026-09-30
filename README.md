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

### Register subjects and sessions

``Lab`` / ``Task`` are admin catalog tables — create with ``ensure_lab`` /
``ensure_task`` (admin DB role). ``Experimenter`` is still a shared lookup;
seed it directly or via a future admin helper. Subjects are everyday writes:

- ``register_subject`` — insert a subject row, return its key
- ``register_session`` — link **existing** subject keys (may be empty)
- ``register_session_with_new_subjects`` — insert subject rows, then register
  the session (one transaction)

Set ``SCENE_DEPLOYMENT_ID`` once (optional ``SCENE_DEPLOYMENT_LABEL``).
``session_id`` is always minted (UUID4 hex).

```python
from datetime import date
from base_schemas.ingestion import (
    new_subject_id,
    register_session,
    register_session_with_new_subjects,
    register_subject,
)

# Existing subjects only:
register_session(
    "mousear-session-015",
    date(2026, 5, 1),
    lab={"lab_id": "mlai"},
    subjects=[{"subject_id": "a" * 32}],
    task={"task_name": "gaze_v1"},
)

# Create subjects + session together:
register_session_with_new_subjects(
    "mousear-session-016",
    date(2026, 5, 2),
    lab={"lab_id": "mlai"},
    subjects=[
        {"subject_id": new_subject_id(), "subject_kind": "mouse"},
    ],
)
```

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
| `SCENE_DEPLOYMENT_ID` | Default deployment stamp for `register_session` |
| `SCENE_DEPLOYMENT_LABEL` | Optional label when using the env default |

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
