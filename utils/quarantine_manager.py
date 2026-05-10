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
from app.services.audit_hash import build_audit_event_hash_hardened

QUARANTINE_DIR = ROOT_DIR / "quarantine"
PENDING_STATUS = "QUARANTINE_MISSING_DATA"
VALIDATED_STATUS = "VALIDATED"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


def list_pending_records() -> list[dict[str, Any]]:
    if not QUARANTINE_DIR.exists():
        return []

    pending: list[dict[str, Any]] = []
    for file_path in sorted(QUARANTINE_DIR.glob("*.json")):
        try:
            data = _read_json(file_path)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("record_status") != PENDING_STATUS:
            continue
        pending.append(
            {
                "path": str(file_path),
                "tenant_id": data.get("tenant_id", ""),
                "recorded_at": data.get("recorded_at", ""),
                "reason": data.get("reason", ""),
            }
        )
    return pending


def _print_pending(records: list[dict[str, Any]]) -> None:
    if not records:
        print("No pending quarantine records found.")
        return

    print("Pending quarantine records:")
    for index, record in enumerate(records, start=1):
        print(f"[{index}] {record['path']}")
        print(f"    tenant_id : {record['tenant_id']}")
        print(f"    recorded  : {record['recorded_at']}")
        print(f"    reason    : {record['reason']}")


def _parse_ti_data(ti_json: str | None, ti_file: str | None) -> dict[str, Any]:
    if ti_json and ti_file:
        raise ValueError("Use either --ti-json or --ti-file, not both.")

    if ti_json:
        parsed = json.loads(ti_json)
    elif ti_file:
        parsed = _read_json(Path(ti_file))
    else:
        raise ValueError("Missing TI data. Provide --ti-json or --ti-file.")

    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("TI data must be a non-empty JSON object.")

    return parsed


def _extract_event_hash(audit_payload: dict[str, Any]) -> str | None:
    value = audit_payload.get("event_hash")
    if isinstance(value, str) and value:
        return value
    return None


def _extract_quarantine_path(audit_payload: dict[str, Any]) -> str | None:
    hash_input = audit_payload.get("hash_input")
    if not isinstance(hash_input, dict):
        return None

    payload = hash_input.get("payload")
    if not isinstance(payload, dict):
        return None

    value = payload.get("quarantine_path")
    if isinstance(value, str) and value:
        return value
    return None


async def _find_original_quarantine_log(
    record_path: Path,
    tenant_id: UUID,
) -> tuple[AuditLog | None, str | None]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        )
        entries = list(result.scalars().all())

    expected_paths = {str(record_path), str(record_path.resolve())}
    for entry in entries:
        payload = entry.payload if isinstance(entry.payload, dict) else {}
        quarantine_path = _extract_quarantine_path(payload)
        if not quarantine_path:
            continue
        if quarantine_path in expected_paths or str(Path(quarantine_path).resolve()) in expected_paths:
            return entry, _extract_event_hash(payload)

    return None, None


async def _latest_event_hash(tenant_id: UUID) -> str | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

    if latest is None or not isinstance(latest.payload, dict):
        return None
    return _extract_event_hash(latest.payload)


async def promote_quarantine_record(
    *,
    record_path: str,
    ti_data: dict[str, Any],
    reviewed_by: str,
) -> dict[str, str]:
    target = Path(record_path)
    if not target.exists():
        raise FileNotFoundError(f"Quarantine record not found: {target}")

    record = _read_json(target)
    if record.get("record_status") != PENDING_STATUS:
        raise ValueError(
            f"Record is not pending quarantine. Current status: {record.get('record_status')}"
        )

    tenant_raw = record.get("tenant_id")
    if not isinstance(tenant_raw, str) or not tenant_raw:
        raise ValueError("Quarantine record is missing tenant_id.")
    tenant_id = UUID(tenant_raw)

    original_log, original_quarantine_event_hash = await _find_original_quarantine_log(
        target,
        tenant_id,
    )
    if original_log is None or not original_quarantine_event_hash:
        raise ValueError(
            "Unable to locate original quarantine audit event for this record."
        )

    previous_event_hash = await _latest_event_hash(tenant_id)
    event_timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    correction_payload = {
        "record_status": VALIDATED_STATUS,
        "sop_section": "8.2",
        "reviewed_by": reviewed_by,
        "quarantine_record_path": str(target.resolve()),
        "original_quarantine_event_hash": original_quarantine_event_hash,
        "scan_data": record.get("scan_data", {}),
        "transaction_information": ti_data,
    }

    promoted_event_hash, chain_prev_hash, hash_input = build_audit_event_hash_hardened(
        tenant_id=tenant_id,
        action="QUARANTINE_PROMOTION_VALIDATED",
        resource="quarantine",
        payload=correction_payload,
        event_timestamp=event_timestamp,
        prev_event_hash=previous_event_hash,
    )

    async with AsyncSessionLocal() as session:
        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=None,
            action="QUARANTINE_PROMOTION_VALIDATED",
            resource="quarantine",
            prev_hash=chain_prev_hash,
            payload={
                "event_hash": promoted_event_hash,
                "hash_input": hash_input,
                "record_status": VALIDATED_STATUS,
                "original_quarantine_event_hash": original_quarantine_event_hash,
            },
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(audit_log)

    record["record_status"] = VALIDATED_STATUS
    record["validated_at"] = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    record["reviewed_by"] = reviewed_by
    record["transaction_information"] = ti_data
    record["promotion_audit_log_id"] = str(audit_log.id)
    record["promotion_event_hash"] = promoted_event_hash
    record["original_quarantine_event_hash"] = original_quarantine_event_hash
    _write_json(target, record)

    return {
        "record_path": str(target.resolve()),
        "promotion_audit_log_id": str(audit_log.id),
        "original_quarantine_event_hash": original_quarantine_event_hash,
        "promotion_event_hash": promoted_event_hash,
        "record_status": VALIDATED_STATUS,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage DSCSA quarantine records (SOP 8.2).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List pending quarantine records.")

    promote = sub.add_parser("promote", help="Promote one record to VALIDATED.")
    promote.add_argument("--record", required=True, help="Path to quarantine record JSON.")
    promote.add_argument("--ti-json", help="TI JSON object string.")
    promote.add_argument("--ti-file", help="Path to JSON file containing TI data.")
    promote.add_argument(
        "--reviewed-by",
        default="PHARMACIST_REVIEW",
        help="Reviewer identifier for the correction record.",
    )

    return parser


async def _run_async(args: argparse.Namespace) -> int:
    if args.command == "list":
        _print_pending(list_pending_records())
        return 0

    if args.command == "promote":
        ti_data = _parse_ti_data(args.ti_json, args.ti_file)
        result = await promote_quarantine_record(
            record_path=args.record,
            ti_data=ti_data,
            reviewed_by=args.reviewed_by,
        )
        print("Promotion complete.")
        print(f"  Record: {result['record_path']}")
        print(f"  Status: {result['record_status']}")
        print(f"  Original quarantine hash: {result['original_quarantine_event_hash']}")
        print(f"  Promotion event hash:    {result['promotion_event_hash']}")
        print(f"  Promotion audit log id:  {result['promotion_audit_log_id']}")
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run_async(args))
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
