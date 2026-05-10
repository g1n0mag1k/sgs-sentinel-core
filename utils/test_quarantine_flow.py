from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import UUID

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import AsyncSessionLocal
from app.models import AuditLog

TENANT_ZERO = UUID(int=0)
QUARANTINE_STATUS = "QUARANTINE_MISSING_DATA"
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/v1/assessment/dual-score"
QUARANTINE_DIR = ROOT_DIR / "quarantine"


def _print_step(title: str) -> None:
    print(f"\n== {title} ==")


def _post_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    req = request.Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            parsed = json.loads(data) if data else {}
            return resp.getcode(), parsed
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


async def _fetch_audit_events() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == TENANT_ZERO)
            .order_by(AuditLog.timestamp.asc(), AuditLog.id.asc())
        )
        rows = list(result.scalars().all())

    events: list[dict[str, Any]] = []
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        events.append(
            {
                "id": str(row.id),
                "prev_hash": row.prev_hash,
                "payload": payload,
                "event_hash": payload.get("event_hash") if isinstance(payload, dict) else None,
            }
        )
    return events


def _quarantine_files() -> set[Path]:
    if not QUARANTINE_DIR.exists():
        return set()
    return set(QUARANTINE_DIR.glob("*.json"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_response_quarantine(response: dict[str, Any]) -> None:
    status = response.get("record_status")
    flags = response.get("flags", [])

    if status == QUARANTINE_STATUS:
        return
    if isinstance(flags, list) and QUARANTINE_STATUS in flags:
        return

    raise AssertionError(
        "Server response did not include QUARANTINE_MISSING_DATA "
        "(checked record_status and flags)."
    )


def _assert_quarantine_file_created(before: set[Path], after: set[Path]) -> Path:
    created = sorted(after - before)
    if not created:
        raise AssertionError("No new quarantine JSON file was created.")

    newest = created[-1]
    payload = _load_json(newest)
    if payload.get("record_status") != QUARANTINE_STATUS:
        raise AssertionError(
            "New quarantine file exists but status is not QUARANTINE_MISSING_DATA."
        )
    return newest


def _assert_audit_chain_continuity(
    before_events: list[dict[str, Any]],
    after_events: list[dict[str, Any]],
) -> dict[str, str]:
    before_ids = {event["id"] for event in before_events}
    new_events = [event for event in after_events if event["id"] not in before_ids]

    if not new_events:
        raise AssertionError("No new audit log record was created.")

    new_event = new_events[-1]
    payload = new_event.get("payload", {})
    if not isinstance(payload, dict):
        raise AssertionError("New audit event payload is invalid.")

    if payload.get("record_status") != QUARANTINE_STATUS:
        raise AssertionError("New audit log record is missing QUARANTINE_MISSING_DATA status.")

    new_event_hash = new_event.get("event_hash")
    if not isinstance(new_event_hash, str) or not new_event_hash:
        raise AssertionError("New audit log record is missing event_hash.")

    previous_hash = "GENESIS"
    if before_events:
        prior_event_hash = before_events[-1].get("event_hash")
        if isinstance(prior_event_hash, str) and prior_event_hash:
            previous_hash = prior_event_hash

    if new_event.get("prev_hash") != previous_hash:
        raise AssertionError(
            "Hash chain continuity failed: new record prev_hash does not match prior event hash."
        )

    hash_input = payload.get("hash_input", {})
    if not isinstance(hash_input, dict):
        raise AssertionError("New audit event missing hash_input.")

    hash_payload = hash_input.get("payload", {})
    if not isinstance(hash_payload, dict):
        raise AssertionError("New audit event hash_input missing payload.")

    tx_info = hash_payload.get("transaction_information")
    if tx_info != {}:
        raise AssertionError(
            "Expected empty transaction_information in hashed payload for quarantine event."
        )

    scan_data = hash_payload.get("scan_data")
    if not isinstance(scan_data, dict) or not scan_data:
        raise AssertionError("Expected scan_data in hashed payload for quarantine event.")

    return {
        "audit_log_id": str(new_event["id"]),
        "event_hash": new_event_hash,
        "prev_hash": str(new_event.get("prev_hash") or ""),
    }


def _build_payload() -> dict[str, Any]:
    return {
        "epcis_payload": {
            "scan_data": {
                "barcode": "00312345000012",
                "eventTime": "2026-05-10T12:30:45Z",
                "lot_number": "LOT-2026-05",
                "serial_number": "SN-998877",
            }
            # Intentionally missing: transaction_information
        },
        "attestation": {
            "answers": {
                "M1-Q1": "yes",
                "M2-Q3": "yes",
            },
            "submitted_glns": ["0614141000006"],
        },
        "facility_name": "Sentinel Mobile Lab",
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate quarantine flow for missing DSCSA TI: API response, quarantine file, and audit hash chain."
        )
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Assessment POST endpoint.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    return parser


async def _run(args: argparse.Namespace) -> int:
    _print_step("Snapshot Before Test")
    before_events = await _fetch_audit_events()
    before_quarantine_files = _quarantine_files()
    print(f"Audit events before: {len(before_events)}")
    print(f"Quarantine files before: {len(before_quarantine_files)}")

    _print_step("Send Missing-TI Request")
    payload = _build_payload()
    status_code, response_json = _post_json(args.endpoint, payload, args.timeout)
    print(f"HTTP status: {status_code}")
    print(f"Response: {json.dumps(response_json, ensure_ascii=False)}")
    if status_code >= 400:
        raise AssertionError("Server returned an error status for the test request.")

    _print_step("Verify Quarantine Status In Response")
    _assert_response_quarantine(response_json)
    print("PASS: Response indicates QUARANTINE_MISSING_DATA.")

    _print_step("Verify Quarantine File Creation")
    after_quarantine_files = _quarantine_files()
    new_quarantine_file = _assert_quarantine_file_created(before_quarantine_files, after_quarantine_files)
    print(f"PASS: New quarantine record created at {new_quarantine_file}")

    _print_step("Verify Audit Hash-Chain Continuity")
    after_events = await _fetch_audit_events()
    continuity = _assert_audit_chain_continuity(before_events, after_events)
    print("PASS: New hash-chained audit record created.")
    print(f"  audit_log_id: {continuity['audit_log_id']}")
    print(f"  prev_hash:    {continuity['prev_hash']}")
    print(f"  event_hash:   {continuity['event_hash']}")

    _print_step("Result")
    print("SUCCESS: Quarantine exception path and audit chain continuity verified.")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
