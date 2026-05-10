from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

QUARANTINE_DIR = Path("quarantine")


def persist_quarantine_event(
    *,
    tenant_id: UUID,
    reason: str,
    scan_data: dict[str, Any],
    source_payload: dict[str, Any],
) -> str:
    """Persist quarantined payload for manual SOP 8.2 review."""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    file_name = f"quarantine_{tenant_id}_{timestamp}_{uuid4().hex}.json"
    target_path = QUARANTINE_DIR / file_name

    content = {
        "record_status": "QUARANTINE_MISSING_DATA",
        "reason": reason,
        "tenant_id": str(tenant_id),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "scan_data": scan_data,
        "source_payload": source_payload,
    }

    target_path.write_text(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return str(target_path)
