# TRACEABILITY MATRIX

Lead Engineer: Andrew C. Rogers (Sui-Generis)
Date: 2026-05-10
Classification: Validated Engineering Specification

## Purpose

This matrix provides bidirectional traceability between User Requirements Specifications (URS) and the implementation modules intended for Pillar 03 deployment at `docs/03_Logic_Core/app/`.

## Scope

- System: SGS-Sentinel Intelligence Base (SG-IB)
- Regulatory Frame: GAMP 5, ALCOA+, DSCSA 2026
- Logical Baseline: FastAPI backend, DSCSA parsing, dual-score assessment, quarantine controls, tamper-evident audit chain

## URS to Design Traceability

| URS ID | User Requirement Statement | Primary Module(s) (Target Pillar 03 Path) | Compliance/Validation Intent | Verification Reference |
|---|---|---|---|---|
| URS-001 | System shall expose a service health and readiness interface for validated operations. | `docs/03_Logic_Core/app/main.py` | Operational visibility and controlled startup/shutdown behavior. | API `/health` execution record; deployment smoke test evidence. |
| URS-002 | System shall enforce authenticated access and role-based authorization for protected workflows. | `docs/03_Logic_Core/app/auth.py`, `docs/03_Logic_Core/app/routers/auth.py`, `docs/03_Logic_Core/app/models.py` | Attributable access control consistent with 21 CFR Part 11 principles. | Token issuance/validation test and RBAC negative-path test output. |
| URS-003 | System shall normalize database connectivity through environment-controlled configuration. | `docs/03_Logic_Core/app/database.py` | Controlled configuration, deterministic fallback, and deploy portability. | Environment matrix test (valid URL, invalid URL, fallback behavior). |
| URS-004 | System shall parse DSCSA payloads and detect missing TI when scan data exists. | `docs/03_Logic_Core/app/parsers/dscsa.py` | Contemporaneous defect detection and quarantine triggering for data integrity failures. | Parser unit test for `QuarantineMissingDataError` and nominal parse path. |
| URS-005 | System shall persist quarantine artifacts for manual SOP review without data loss. | `docs/03_Logic_Core/app/services/quarantine.py`, `docs/03_Logic_Core/app/routers/assessments.py` | Original evidence preservation and chain-of-custody continuity (ALCOA+). | Quarantine artifact creation evidence in Pillar 04; quarantine flow test. |
| URS-006 | System shall compute deterministic SHA-256 hashes for audit events. | `docs/03_Logic_Core/app/services/audit_hash.py` | Accurate and reproducible event integrity control via canonical serialization. | Hash recomputation parity evidence and tamper detection demonstration. |
| URS-007 | System shall maintain prev-hash linkage for tamper-evident audit chaining. | `docs/03_Logic_Core/app/services/audit_hash.py`, `docs/03_Logic_Core/app/routers/assessments.py`, `docs/03_Logic_Core/app/models.py` | Enduring integrity chain supporting forensic reconstruction and mutation detection. | Integrity verification output proving GENESIS-first linkage and continuity. |
| URS-008 | System shall evaluate DSCSA technical risk from EPCIS payload characteristics. | `docs/03_Logic_Core/app/services/scoring.py` | Risk-tier derivation for compliance triage and defect escalation workflows. | Score calculation tests with known payload fixtures and expected flags. |
| URS-009 | System shall support dual-score output combining technical and attestation dimensions. | `docs/03_Logic_Core/app/services/scoring.py`, `docs/03_Logic_Core/app/routers/assessments.py`, `docs/03_Logic_Core/app/schemas.py` | Transparent compliance posture reporting and actionable verdicting. | `/api/v1/assessment/dual-score` response validation and schema checks. |
| URS-010 | System shall store audit records with immutable evidence fields. | `docs/03_Logic_Core/app/models.py`, `docs/03_Logic_Core/app/routers/assessments.py` | Accurate and attributable audit event persistence aligned to ALCOA+. | Database inspection evidence and integrity verification runbook output. |
| URS-011 | System shall expose validated API schema contracts for regulated exchanges. | `docs/03_Logic_Core/app/schemas.py` | Legible and consistent contract enforcement for input/output records. | Pydantic model validation tests and OpenAPI review snapshot. |
| URS-012 | System shall provide tenant/facility governance endpoints for DSCSA operations. | `docs/03_Logic_Core/app/routers/tenants.py`, `docs/03_Logic_Core/app/routers/facilities.py` | Controlled master-data governance for tenant-bounded compliance workflows. | Endpoint permission and CRUD validation evidence. |

## Traceability Control Notes

- This matrix is maintained as a controlled specification artifact.
- Any change to URS scope or module responsibility requires matrix revision and evidence update.
- Verification outputs are to be archived in `docs/04_Evidence/` with contemporaneous timestamps.
