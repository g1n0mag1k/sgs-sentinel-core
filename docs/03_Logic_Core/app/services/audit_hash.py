from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from utils.get_id import get_device_id


def build_audit_event_hash_clean(event_data: dict[str, Any]) -> str:
    """Build deterministic SHA-256 from canonical JSON."""
    canonical_payload = json.dumps(
        event_data,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical_payload.encode('utf-8')).hexdigest()


def build_audit_event_hash_hardened(
    *,
    tenant_id: UUID,
    action: str,
    resource: str,
    payload: dict[str, Any],
    event_timestamp: str,
    prev_event_hash: str | None,
    device_id: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """Create canonical chain input and return (current_hash, prev_hash, hash_input)."""
    chain_prev_hash = prev_event_hash or "GENESIS"
    resolved_device_id = (device_id or get_device_id()).strip()
    if not resolved_device_id:
        raise ValueError("device_id is required for hardened audit hashing")

    hash_input = {
        "action": action,
        "device_id": resolved_device_id,
        "event_timestamp": event_timestamp,
        "payload": payload,
        "prev_event_hash": chain_prev_hash,
        "resource": resource,
        "tenant_id": str(tenant_id),
    }
    current_event_hash = build_audit_event_hash_clean(hash_input)
    return current_event_hash, chain_prev_hash, hash_input
