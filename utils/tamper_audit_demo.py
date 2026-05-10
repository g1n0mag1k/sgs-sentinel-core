from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import AsyncSessionLocal
from app.models import AuditLog

BACKUP_PATH = ROOT_DIR / ".tamper_backup.json"


def _flip_hex_char(value: str) -> str:
    if not value:
        raise ValueError("Cannot tamper with an empty hash value.")
    first = value[0].lower()
    replacement = "f" if first != "f" else "e"
    return replacement + value[1:]


def _load_backup() -> dict[str, Any]:
    if not BACKUP_PATH.exists():
        raise FileNotFoundError(
            f"Backup file not found at {BACKUP_PATH}. Run apply first."
        )
    return json.loads(BACKUP_PATH.read_text(encoding="utf-8"))


def _save_backup(payload: dict[str, Any]) -> None:
    BACKUP_PATH.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


async def _find_target_record(
    *,
    tenant_id: str | None,
    record_id: str | None,
) -> AuditLog:
    async with AsyncSessionLocal() as session:
        stmt = select(AuditLog)
        if record_id:
            stmt = stmt.where(AuditLog.id == record_id)
        elif tenant_id:
            tenant_uuid = UUID(tenant_id)
            stmt = stmt.where(AuditLog.tenant_id == tenant_uuid).order_by(
                AuditLog.timestamp.desc(),
                AuditLog.id.desc(),
            )
        else:
            stmt = stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())

        result = await session.execute(stmt.limit(1))
        row = result.scalar_one_or_none()

    if row is None:
        raise ValueError("No matching audit record found.")
    return row


async def apply_tamper(*, tenant_id: str | None, record_id: str | None) -> int:
    if BACKUP_PATH.exists():
        raise ValueError(
            "Existing backup file found. Restore first or remove .tamper_backup.json explicitly."
        )

    target = await _find_target_record(tenant_id=tenant_id, record_id=record_id)
    if not isinstance(target.payload, dict):
        raise ValueError("Target record payload is not a JSON object.")

    old_hash = target.payload.get("event_hash")
    if not isinstance(old_hash, str) or not old_hash:
        raise ValueError("Target record does not contain payload.event_hash.")

    new_hash = _flip_hex_char(old_hash)

    updated_payload = dict(target.payload)
    updated_payload["event_hash"] = new_hash

    async with AsyncSessionLocal() as session:
        db_row = await session.get(AuditLog, target.id)
        if db_row is None:
            raise ValueError("Target record disappeared before tamper write.")
        db_row.payload = updated_payload
        await session.commit()

    _save_backup(
        {
            "record_id": str(target.id),
            "tenant_id": str(target.tenant_id),
            "old_event_hash": old_hash,
            "new_event_hash": new_hash,
            "tampered_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }
    )

    print("Tamper applied successfully.")
    print(f"  record_id: {target.id}")
    print(f"  tenant_id: {target.tenant_id}")
    print(f"  old_hash : {old_hash}")
    print(f"  new_hash : {new_hash}")
    print("Next: run python utils/verify_integrity.py")
    return 0


async def restore_tamper() -> int:
    backup = _load_backup()

    record_id = backup.get("record_id")
    old_event_hash = backup.get("old_event_hash")
    if not isinstance(record_id, str) or not isinstance(old_event_hash, str):
        raise ValueError("Backup file is invalid.")

    async with AsyncSessionLocal() as session:
        row = await session.get(AuditLog, record_id)
        if row is None:
            raise ValueError(f"Audit record {record_id} not found for restore.")
        if not isinstance(row.payload, dict):
            raise ValueError("Target record payload is not a JSON object.")

        payload = dict(row.payload)
        payload["event_hash"] = old_event_hash
        row.payload = payload
        await session.commit()

    BACKUP_PATH.unlink(missing_ok=True)

    print("Tamper restored successfully.")
    print(f"  record_id: {record_id}")
    print(f"  restored_event_hash: {old_event_hash}")
    print("Next: run python utils/verify_integrity.py")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Controlled tamper demo for audit integrity verification.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    apply_cmd = sub.add_parser("apply", help="Tamper with one record by flipping one hash character.")
    apply_cmd.add_argument(
        "--tenant-id",
        help="Optional tenant UUID. If omitted, latest record across all tenants is used.",
    )
    apply_cmd.add_argument(
        "--record-id",
        help="Optional explicit audit record UUID. Overrides --tenant-id when provided.",
    )

    sub.add_parser("restore", help="Restore the previously tampered record from backup.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "apply":
            return asyncio.run(apply_tamper(tenant_id=args.tenant_id, record_id=args.record_id))
        if args.command == "restore":
            return asyncio.run(restore_tamper())
        raise ValueError(f"Unsupported command: {args.command}")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
