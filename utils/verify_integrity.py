from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import AsyncSessionLocal
from app.models import AuditLog
from app.services.audit_hash import build_audit_event_hash_clean


def _short_hash(value: str | None) -> str:
    if not value:
        return "<none>"
    if len(value) <= 16:
        return value
    return f"{value[:8]}...{value[-8:]}"


def _extract_event_hash(payload: dict[str, Any]) -> str | None:
    value = payload.get("event_hash")
    if isinstance(value, str) and value:
        return value
    return None


def _extract_hash_input(payload: dict[str, Any]) -> dict[str, Any] | None:
    value = payload.get("hash_input")
    if isinstance(value, dict):
        return value
    return None


async def verify_audit_chain(tenant_id: str | None = None) -> int:
    async with AsyncSessionLocal() as session:
        stmt = select(AuditLog).order_by(
            AuditLog.tenant_id.asc(),
            AuditLog.timestamp.asc(),
            AuditLog.id.asc(),
        )
        if tenant_id:
            stmt = stmt.where(AuditLog.tenant_id == tenant_id)

        result = await session.execute(stmt)
        rows = list(result.scalars().all())

    if not rows:
        print("No audit records found.")
        return 0

    print(f"Scanning {len(rows)} audit records for integrity...")

    previous_event_hash_by_tenant: dict[str, str | None] = {}

    for index, row in enumerate(rows, start=1):
        row_tenant = str(row.tenant_id)
        payload = row.payload if isinstance(row.payload, dict) else {}

        event_hash = _extract_event_hash(payload)
        hash_input = _extract_hash_input(payload)

        if event_hash is None or hash_input is None:
            print("CRITICAL: INTEGRITY BREACH DETECTED")
            print(f"Reason: Missing event_hash or hash_input at record #{index}")
            print(f"Record ID: {row.id}")
            print(f"Tenant: {row_tenant}")
            return 1

        recomputed_hash = build_audit_event_hash_clean(hash_input)
        if recomputed_hash != event_hash:
            print("CRITICAL: INTEGRITY BREACH DETECTED")
            print(f"Reason: Hash mismatch at record #{index}")
            print(f"Record ID: {row.id}")
            print(f"Tenant: {row_tenant}")
            print(f"Stored hash:    {event_hash}")
            print(f"Recomputed hash:{recomputed_hash}")
            return 1

        expected_prev = previous_event_hash_by_tenant.get(row_tenant)
        if expected_prev is None:
            expected_prev = "GENESIS"

        if row.prev_hash != expected_prev:
            print("CRITICAL: INTEGRITY BREACH DETECTED")
            print(f"Reason: Chain break at record #{index}")
            print(f"Record ID: {row.id}")
            print(f"Tenant: {row_tenant}")
            print(f"Expected prev_hash: {expected_prev}")
            print(f"Actual prev_hash:   {row.prev_hash}")
            print(
                "Previous event_hash: "
                f"{_short_hash(previous_event_hash_by_tenant.get(row_tenant))}"
            )
            print(f"Current event_hash:  {_short_hash(event_hash)}")
            return 1

        hash_input_prev = hash_input.get("prev_event_hash")
        if hash_input_prev != row.prev_hash:
            print("CRITICAL: INTEGRITY BREACH DETECTED")
            print(f"Reason: hash_input.prev_event_hash mismatch at record #{index}")
            print(f"Record ID: {row.id}")
            print(f"Tenant: {row_tenant}")
            print(f"row.prev_hash:               {row.prev_hash}")
            print(f"hash_input.prev_event_hash:  {hash_input_prev}")
            return 1

        previous_event_hash_by_tenant[row_tenant] = event_hash

    print("Integrity check PASSED: no chain breaks detected.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify audit log hash and chain integrity.",
    )
    parser.add_argument(
        "--tenant-id",
        help="Optional tenant UUID filter. If omitted, all tenants are verified.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(verify_audit_chain(tenant_id=args.tenant_id))
    except Exception as exc:
        print("CRITICAL: INTEGRITY BREACH DETECTED")
        print(f"Reason: verifier failed with error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
