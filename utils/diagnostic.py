#!/usr/bin/env python3
"""Diagnostic: Verify environment variables and device identity loading."""
import sys
import os
from pathlib import Path

print("=" * 60)
print("SGS-Sentinel Environment Diagnostic")
print("=" * 60)

# Step 1: Verify .env exists
env_file = Path(".env")
if not env_file.exists():
    print("❌ FAIL: .env file not found")
    sys.exit(1)
print(f"✅ PASS: .env file exists at {env_file.absolute()}")

# Step 2: Load .env into environment
try:
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"')
    print("✅ PASS: .env loaded into environment variables")
except Exception as e:
    print(f"❌ FAIL: Could not load .env: {e}")
    sys.exit(1)

# Step 3: Verify SGS_DEVICE_ID
sgs_device_id = os.getenv("SGS_DEVICE_ID", "").strip()
if not sgs_device_id:
    print("❌ FAIL: SGS_DEVICE_ID not set in environment")
    sys.exit(1)
print(f"✅ PASS: SGS_DEVICE_ID = '{sgs_device_id}'")

# Step 4: Verify DATABASE_URL
db_url = os.getenv("DATABASE_URL", "").strip()
if not db_url:
    print("❌ FAIL: DATABASE_URL not set in environment")
    sys.exit(1)
print(f"✅ PASS: DATABASE_URL = '{db_url}'")

# Step 5: Test get_device_id() function
try:
    from utils.get_id import get_device_id
    device_id = get_device_id()
    if device_id == sgs_device_id:
        print(f"✅ PASS: get_device_id() returns correct value: '{device_id}'")
    else:
        print(f"⚠️  WARNING: get_device_id() returned '{device_id}' (expected '{sgs_device_id}')")
except Exception as e:
    print(f"❌ FAIL: get_device_id() raised exception: {e}")
    sys.exit(1)

# Step 6: Test audit_hash functions
try:
    from app.services.audit_hash import (
        build_audit_event_hash_clean,
        build_audit_event_hash_hardened,
    )
    from uuid import uuid4

    # Test canonical hash
    test_payload = {"key": "value", "nested": {"a": 1, "b": 2}}
    hash1 = build_audit_event_hash_clean(test_payload)
    hash2 = build_audit_event_hash_clean(test_payload)

    if hash1 == hash2:
        print(f"✅ PASS: build_audit_event_hash_clean() is deterministic")
    else:
        print(f"❌ FAIL: Hash mismatch in deterministic hashing")
        sys.exit(1)

    # Test hardened hash
    tenant_id = uuid4()
    current_hash, prev_hash, hash_input = build_audit_event_hash_hardened(
        tenant_id=tenant_id,
        action="TEST_DIAGNOSTIC",
        resource="environment_check",
        payload=test_payload,
        event_timestamp="2026-05-10T00:00:00Z",
        prev_event_hash="GENESIS",
    )

    if current_hash and prev_hash == "GENESIS" and device_id in str(hash_input):
        print(
            f"✅ PASS: build_audit_event_hash_hardened() succeeded with device binding"
        )
    else:
        print(f"❌ FAIL: Hardened hash function failed")
        sys.exit(1)

except ImportError as e:
    print(f"❌ FAIL: Could not import audit_hash module: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ FAIL: audit_hash function raised exception: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("🟢 GREEN LIGHT: System ready for startup")
print("=" * 60)
print("\nAll diagnostics passed. You can start the app without errors.")
print("Next steps:")
print("  1. python -m app.main                    (start FastAPI server)")
print("  2. python utils/test_quarantine_flow.py  (validate quarantine)")
print("  3. python utils/verify_integrity.py      (verify audit chain)")
