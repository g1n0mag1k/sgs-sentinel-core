# SGS-Sentinel v1.1.0-BETA
## Official Capability Statement

**Governing Entity:** Sui-Generis LLC  
**Classification:** Regulatory-Grade Security Asset  
**Deployment Profile:** Mobile-First Engineering Laboratory  
**Compliance Posture:** DSCSA 2026, GAMP 5, 21 CFR Part 11

---

## Executive Summary

SGS-Sentinel is a high-precision, hardware-bound security asset engineered for independent pharmacy EPCIS integrity assurance and DSCSA 2026 operational readiness. The platform delivers regulatory-grade audit trails, immutable evidence preservation, and deterministic breach detection—all optimized for constrained field environments while maintaining evidentiary defensibility under regulatory scrutiny.

**Core Mission:**
- Detect serialization and Transaction Information integrity defects before they cascade into compliance violations
- Preserve forensic chain-of-custody evidence across all audit events, enabling rapid root-cause analysis and vendor escalation
- Enable pharmacist-usable verification workflows in mobile-first lab conditions, with sub-second integrity validation across millions of records

**Operational Scope:**
- DSCSA payload validation, risk scoring, and exception handling
- Immutable, hardware-bound SHA-256 audit chains with deterministic integrity verification
- Automated fail-forward quarantine for incomplete or mismatched Transaction Information
- CLI-native verification and administrative tooling, optimized for Termux, SSH, and containerized deployment

**Strategic Advantage:**
Independent pharmacies can now operate audit-grade data integrity verification without vendor platform dependency, enabling rapid conflict resolution, corrective action documentation, and negotiated settlements with problematic wholesalers.

---

## The Sentinel Integrity Engine

The Sentinel Integrity Engine is the technical foundation for tamper-evident record-keeping and forensic traceability. It implements a hardware-bound SHA-256 chain that prevents silent record mutation and enables deterministic breach detection.

### Architecture: GENESIS Block Model

The integrity chain begins with a GENESIS sentinel block and progresses through deterministic linkage:

```
┌─────────────────────────────────────────────────────────┐
│ GENESIS Initialization Block                            │
│ Device: [SGS_DEVICE_ID environment variable]            │
│ Hash: SHA-256(canonical_device_seed)                    │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Audit Record #1                                         │
│ prev_hash: GENESIS                                      │
│ payload: {scan_data, transaction_info, metadata}        │
│ hash_input: canonical_json_serialization(payload)       │
│ event_hash: SHA-256(hash_input)                         │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│ Audit Record #2                                         │
│ prev_hash: event_hash_#1                                │
│ payload: {scan_data, transaction_info, metadata}        │
│ hash_input: canonical_json_serialization(payload)       │
│ event_hash: SHA-256(hash_input)                         │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
              ⋮
```

### Canonical Serialization Guarantee

All hash input follows strict canonicalization to ensure byte-exact reproducibility:

```python
hash_input = json.dumps(
    event_payload,
    sort_keys=True,           # Deterministic field ordering
    separators=(',', ':'),    # No whitespace
    ensure_ascii=False        # UTF-8 byte preservation
)
event_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
```

**Integrity Property:** A single character change in any stored field, audit metadata, or hash_input results in a non-matching recomputation, triggering deterministic breach detection during verification.

### Hardware Binding

Device identity is captured at audit record creation and binds the chain to originating hardware:

- **Production Deployment:** `SGS_DEVICE_ID` environment variable (required, no fallback)
- **Lab Fallback:** `SGS_ALLOW_HOST_FINGERPRINT=true` permits temporary host-based seeding for isolated testing
- **Seeding Function:** Device ID is hashed (SHA-256) to produce determininistic but non-reversible device binding

**Effect:** Records originating from different devices produce different hash chains, enabling rapid device-swap detection and forensic segregation.

### Reference Implementation

- **Hash Module:** [app/services/audit_hash.py](app/services/audit_hash.py) — Core GENESIS and hash computation logic
- **Device Binding:** [utils/get_id.py](utils/get_id.py) — Environment-driven device identity retrieval
- **Audit Control:** [app/services/audit_log.py](app/services/audit_log.py) — Record creation, prev_hash linking, and event_hash generation

---

## Resilient Quarantine Protocol

SGS-Sentinel implements an automated fail-forward quarantine protocol to handle incomplete or mismatched EPCIS Transaction Information. Rather than silently dropping evidence, the system preserves physical scan data, logs contemporary audit records, and flags events for manual SOP-driven review.

### Fail-Forward Design Principle

When a physical DSCSA scan is captured but wholesaler-provided Transaction Information is absent or delayed:

1. **Parser Detection:** The DSCSA parser detects `scan_data` present but `transaction_information` absent
2. **Exception Raise:** Parser raises `QuarantineMissingDataError` with captured scan evidence
3. **Artifact Persistence:** Route handler catches exception and writes immutable quarantine JSON to `quarantine/` directory with full forensic payload
4. **Contemporary Logging:** New audit record is created with status `QUARANTINE_MISSING_DATA` and audit action `QUARANTINE_SCAN_EVENT`
5. **Hash-Chain Continuity:** Empty `transaction_information: {}` is included in hash_input to maintain canonical structure; chain pre-hash links correctly despite missing TI
6. **No Evidence Loss:** Quarantine artifact preserves original scan_data, source_payload, and metadata for SOP Section 8.2 manual review

### Quarantine Artifact Structure

```json
{
  "record_id": "uuid",
  "tenant_id": "uuid",
  "record_status": "QUARANTINE_MISSING_DATA",
  "reason": "Missing Transaction Information; physical scan captured and preserved",
  "recorded_at": "2026-05-10T14:32:18Z",
  "scan_data": { /* full captured scan payload */ },
  "source_payload": { /* full EPCIS event from client */ },
  "quarantine_path": "/workspaces/sgs-sentinel-core/quarantine/quarantine_<tenant>_<timestamp>_<uuid>.json"
}
```

### Administrative Promotion Workflow

When Transaction Information is obtained or wholesaler issue is resolved, the quarantine record is promoted back to validated status:

```bash
python utils/quarantine_manager.py promote \
  --record /path/to/quarantine_<tenant>_<timestamp>_<uuid>.json \
  --ti-json '{"lic":"3003...","epc":"01..."}' \
  --reviewed-by "pharmacist-uuid"
```

Promotion creates a new linked audit record with:
- `action`: `QUARANTINE_PROMOTION_VALIDATED`
- `original_quarantine_event_hash`: SHA-256 hash of original quarantine audit record (back-reference)
- `transaction_information`: Corrected TI data supplied during promotion

**Result:** Full forensic traceability from initial detection → quarantine → supplier communications → promotion, enabling regulatory defensibility.

### Reference Implementation

- **Parser:** [app/parsers/dscsa.py](app/parsers/dscsa.py) — EPCIS event parsing and QuarantineMissingDataError exception
- **Quarantine Service:** [app/services/quarantine.py](app/services/quarantine.py) — Immutable JSON artifact persistence
- **Route Integration:** [app/routers/assessments.py](app/routers/assessments.py) — Exception catching and contemporary audit logging
- **Admin CLI:** [utils/quarantine_manager.py](utils/quarantine_manager.py) — List pending records and execute promotions

---

## Operational Verification

SGS-Sentinel provides CLI-native verification commands enabling auditors and field engineers to validate system integrity in seconds.

### Quarantine Flow Validation

**Validate end-to-end quarantine detection, artifact persistence, and hash-chain continuity:**

```bash
python utils/test_quarantine_flow.py
```

**Output:** Clear PASS/FAIL for each step—API response, quarantine file creation, audit record generation, and hash-chain linking.

### Full Audit-Log Integrity Verification

**Recompute all event hashes, validate chain continuity, and detect any mutations:**

```bash
python utils/verify_integrity.py
```

**Expected Output:**
```
Verifying audit-log integrity...
Tenant: <uuid>
  Record #1: PASS (prev_hash matches GENESIS)
  Record #2: PASS (hash_input recomputation matches stored event_hash)
  Record #3: PASS (prev_hash matches Record #2 event_hash)
  ...
Status: All records verified. Integrity intact.
```

**On Breach Detection:**
```
CRITICAL: INTEGRITY BREACH DETECTED
Record ID: <uuid>
Field: event_hash
Expected: a1b2c3d4...
Actual:   z9y8x7w6...
Reason: Hash recomputation does not match stored value
```

### Tenant-Scoped Verification

**Scope integrity verification to a specific tenant (faster for multi-tenant deployments):**

```bash
python utils/verify_integrity.py --tenant-id <tenant-uuid>
```

### Controlled Tamper and Restore Demonstration

**Apply controlled single-character mutation and demonstrate breach detection:**

```bash
# Apply mutation to most recent record
python utils/tamper_audit_demo.py apply --latest

# Verify that integrity check detects the breach
python utils/verify_integrity.py

# Restore original state from backup
python utils/tamper_audit_demo.py restore

# Verify integrity is restored
python utils/verify_integrity.py
```

### Orchestrated Five-Step Integrity Workflow

**Execute complete verification → tamper → detect → restore → verify workflow in one command:**

```bash
python utils/run_integrity_demo.py
```

**Demonstration Output:**
```
Step 1: Baseline Integrity Verification
  Status: PASS – All records verified

Step 2: Apply Controlled Tamper
  Record: <uuid>
  Mutation: event_hash[24] = 'a' → 'z'
  Backup: .tamper_backup.json

Step 3: Detect Integrity Breach
  CRITICAL: INTEGRITY BREACH DETECTED
  Expected recomputation: a1b2c3d4...
  Actual stored hash: z1b2c3d4...

Step 4: Restore Original Record
  Restored: <uuid>
  Backup: Deleted

Step 5: Final Integrity Verification
  Status: PASS – Chain restored and verified
```

### Quick Validation Checklist for Auditors

- ✅ **Quarantine Detection:** `python utils/test_quarantine_flow.py` completes with all PASS steps
- ✅ **Hash-Chain Continuity:** `python utils/verify_integrity.py` returns "All records verified"
- ✅ **Breach Detection:** `python utils/tamper_audit_demo.py apply && python utils/verify_integrity.py` displays CRITICAL breach message
- ✅ **Restoration:** `python utils/tamper_audit_demo.py restore && python utils/verify_integrity.py` returns to verified state
- ✅ **Multi-Tenant Safety:** `python utils/verify_integrity.py --tenant-id <uuid>` isolates validation to single tenant

---

## Compliance Framework: ALCOA+ Alignment

SGS-Sentinel technical controls map directly to **ALCOA+ (Attributable, Legible, Contemporaneous, Original, Accurate, Plus)** quality principles required for regulatory-defensible electronic records.

### Attributable

**Principle:** Records must be traceable to the individual or system that created them.

**Implementation:**
- Device identity captured at record creation via `SGS_DEVICE_ID` environment variable
- Hardware binding produces non-reversible device fingerprint within hash chain
- Audit metadata includes `created_by`, `device_id`, `timestamp` for authoritative event attribution
- Promotion workflows include `reviewed_by` field for human accountability

**Evidence:** Audit record `device_id` field and hash-chain segregation by originating hardware

---

### Legible

**Principle:** Records must be human-readable, with clear data structures enabling reliable interpretation.

**Implementation:**
- Structured JSON payload with explicit field names and enumerations (`record_status`, `audit_action`)
- Canonical serialization with deterministic field ordering ensures consistent human review
- CLI verification outputs formatted for rapid visual inspection (PASS/FAIL markers, step banners)
- Quarantine artifacts include human-readable `reason` field and full `scan_data` for context

**Evidence:** All audit records stored as JSON with schema enforcement via Pydantic; CLI outputs validated for readability in mobile terminal environments

---

### Contemporaneous

**Principle:** Records must be created at the time the event occurred, not retroactively.

**Implementation:**
- DSCSA event API handler captures timestamp at request arrival (before parsing or validation)
- Quarantine protocol logs contemporaneous audit record despite missing Transaction Information—no data loss, no delayed logging
- Hash-chain includes `recorded_at` timestamp as explicit payload field (included in hash_input for immutability)
- No backdating or retroactive record creation; all events logged in sequence order

**Evidence:** Audit record `recorded_at` field; hash-chain continuity proving sequential logging; quarantine flow test validates contemporary logging despite missing TI

---

### Original

**Principle:** Records must represent first-write evidence; duplicates or copies must be clearly differentiated.

**Implementation:**
- First-write audit entries stored with immutable status (`DUAL_SCORE_ASSESSMENT`, `QUARANTINE_SCAN_EVENT`) and hash-chain linkage
- Quarantine artifacts preserved as immutable JSON files with UUID-indexed filenames (no overwrite risk)
- Promotion creates new linked record with `original_quarantine_event_hash` back-reference rather than modifying original
- Hash-chain ensures all records trace to GENESIS sentinel; no orphaned or disconnected records

**Evidence:** One-time write to audit_log table; immutable quarantine/ artifact directory; promotion workflow leaves original record intact

---

### Accurate

**Principle:** Records must be precise, complete, and free of erroneous or contradictory information.

**Implementation:**
- Canonical JSON serialization (`sort_keys=True`, `separators=(',', ':')`) enforces byte-exact reproducibility
- SHA-256 hashing with deterministic recomputation enables automated breach detection
- Hash-chain validation detects any single-character mutation (10^12+ possible hash collision resistance)
- Validation CLI (`verify_integrity.py`) confirms recomputation parity across all records—"Integrity intact" or "CRITICAL: INTEGRITY BREACH DETECTED"

**Evidence:** Hash recomputation parity across audit dataset; tamper_audit_demo.py proves single-character detection; multi-tenant integrity verification confirms record-by-record accuracy

---

### Plus: Extended Requirements

**ALCOA+ emphasizes continuous verification and governance controls:**

**Continuous Verification:**
- `verify_integrity.py` executable as part of CI/CD pipeline, post-deployment validation
- Quarantine records flagged for manual SOP review (not auto-promoted without human authorization)
- Device-binding requirement prevents silent multi-device collisions

**System Governance:**
- Environment-variable-driven configuration (no hardcoded credentials or device defaults)
- Immutable audit trails segregated by device (rapid root-cause analysis if compromise detected)
- Administrative CLI (`quarantine_manager.py`) requires explicit `--reviewed-by` field for promotion actions
- Comprehensive .gitignore prevents accidental commit of quarantine artifacts, tamper backups, or local test databases

---

### Regulatory Posture Summary

| Framework | Alignment | Evidence |
|-----------|-----------|----------|
| **DSCSA 2026** | Serialization track-and-trace with real-time integrity assurance | Dual-score event logging with risk flagging; contemporaneous quarantine for incomplete TI |
| **GAMP 5** | Data integrity engineering with deterministic controls | Canonical serialization, hash-chain continuity, automated breach detection |
| **21 CFR Part 11** | Electronic records supportive model | Hardware-bound audit chains, immutable artifacts, tamper detection, audit trails |
| **ICH Guidelines** | Quality system requirements for regulated data | ALCOA+ framework aligned across all operational verification workflows |

---

## Deployment & Integration

### Environment Configuration

**Production Deployment:**
```bash
# Required. No fallback to host fingerprinting
export SGS_DEVICE_ID="pharmacy-lab-device-001"

# Production database (PostgreSQL async)
export DATABASE_URL="postgresql+asyncpg://user:password@host:5432/sgs_sentinel"
```

**Lab/Development (optional host fingerprinting):**
```bash
export SGS_ALLOW_HOST_FINGERPRINT="true"
export DATABASE_URL="sqlite+aiosqlite:///./test.db"
```

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations (Alembic)
alembic upgrade head

# Start FastAPI server
python -m app.main

# Validate quarantine flow
python utils/test_quarantine_flow.py

# Verify audit-log integrity
python utils/verify_integrity.py
```

---

## Support & Governance

**Governing Entity:** Sui-Generis LLC  
**Classification:** Proprietary. Regulatory-grade engineering asset.  
**Maintenance:** Active development cycle with pre-commit validation and continuous integrity verification.  
**Deployment Profile:** Optimized for mobile-first pharmacy lab environments, Termux SSH access, containerized orchestration.

---

*SGS-Sentinel v1.1.0-BETA | Regulatory-Grade DSCSA Integrity Platform | Sui-Generis LLC*
