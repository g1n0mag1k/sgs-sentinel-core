# MIGRATION LOG

## Event Record: Structural System Hardening (Phase 2)

- Event ID: MIG-2026-05-10-001
- Event Type: Structural System Hardening
- System: SGS-Sentinel Core (SG-IB)
- Requested By: Andrew C. Rogers (Lead Engineer)
- Executed By: DevOps/GAMP 5 Migration Procedure
- Effective Date (UTC): 2026-05-10
- Scope: Relocation of executable logic assets into Pillar 03 (docs/03_Logic_Core)

## Change Intent

Relocate core logic and operational assets into a controlled GAMP 5 pillar structure while preserving runtime operability and migration traceability.

Moved assets (planned):
- app/
- alembic/
- alembic.ini
- utils/
- requirements.txt
- Procfile

Destination:
- docs/03_Logic_Core/

## Immediate Control Actions

1. Runtime bootstrap path updated to include docs/03_Logic_Core in PYTHONPATH.
2. ASGI module target retained as app.main:app to avoid invalid package import semantics.
3. Alembic config constrained to new location using:
   - script_location = %(here)s/alembic
   - prepend_sys_path = %(here)s
4. Deployment spec alignment required for app.yaml run_command.

## ALCOA+ Compliance Mapping

- Attributable: Change linked to named requestor, event ID, and repository history (git mv provenance).
- Legible: Change scope, moved artifacts, and control actions documented in Markdown with explicit paths.
- Contemporaneous: Event logged on execution date within controlled evidence pillar.
- Original: Source files moved with git mv to preserve file lineage and history continuity.
- Accurate: Path and runtime controls specified with exact executable commands and config keys.
- Complete: Includes intent, scope, controls, validation commands, and rollback instructions.
- Consistent: Uses standardized event structure and naming conventions.
- Enduring: Stored under docs/04_Evidence for immutable audit trail retention.
- Available: Accessible in repository for inspection, QA review, and regulatory audit.

## Verification Commands

Run after migration:

```bash
git status --short
PYTHONPATH=docs/03_Logic_Core python -m app.main
alembic -c docs/03_Logic_Core/alembic.ini current
```

## Rollback Procedure

If required before commit:

```bash
git restore --staged .
git restore .
```

If required after commit:

```bash
git revert <commit_sha>
```

## Approval Placeholder

- QA Validation Review: Pending
- Engineering Approval: Pending
- Release Approval: Pending

