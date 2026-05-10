from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog
from app.parsers import QuarantineMissingDataError, parse_dscsa_event
from app.schemas import DualScoreRequest, DualScoreResponse
from app.services.audit_hash import build_audit_event_hash_hardened
from app.services.quarantine import persist_quarantine_event
from app.services.scoring import calculate_dual_score, evaluate_dscsa_risk, score_attestation

router = APIRouter(prefix="/api/v1/assessment", tags=["assessment"])


@router.post("/dual-score", response_model=DualScoreResponse)
async def dual_score_assessment(
    payload: DualScoreRequest,
    db: AsyncSession = Depends(get_db),
) -> DualScoreResponse:
    """Evaluate dual-score assessment from EPCIS payload and attestation."""
    try:
        # Demo-friendly: use a stable tenant id unless auth is wired.
        tenant_id = uuid.UUID(int=0)
        record_status = "CONTEMPORARY_RECORD"
        quarantine_path: str | None = None

        parsed_scan_data: dict[str, object] = {}
        parsed_ti_data: dict[str, object] = {}
        try:
            parsed_event = parse_dscsa_event(payload.epcis_payload)
            parsed_scan_data = parsed_event.scan_data
            parsed_ti_data = parsed_event.ti_data
        except QuarantineMissingDataError as quarantine_exc:
            record_status = "QUARANTINE_MISSING_DATA"
            parsed_scan_data = quarantine_exc.scan_data
            parsed_ti_data = {}
            quarantine_path = persist_quarantine_event(
                tenant_id=tenant_id,
                reason="EPCIS TI missing while physical scan data exists",
                scan_data=parsed_scan_data,
                source_payload=payload.epcis_payload,
            )

        technical = await evaluate_dscsa_risk(payload.epcis_payload, db, tenant_id)
        if record_status == "QUARANTINE_MISSING_DATA":
            technical.flags.append("QUARANTINE_MISSING_DATA")
        attested_score, attested_grade, gaps = score_attestation(payload.attestation)
        combined = calculate_dual_score(
            technical,
            attested_score,
            attested_grade,
            technical.flags,
            gaps,
        )

        # Resolve previous event hash; first record in chain uses GENESIS.
        latest_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .limit(1)
        )
        latest_event = latest_result.scalar_one_or_none()
        prev_event_hash: str | None = None
        if latest_event is not None and isinstance(latest_event.payload, dict):
            prev_value = latest_event.payload.get("event_hash")
            if isinstance(prev_value, str) and prev_value:
                prev_event_hash = prev_value

        event_timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        event_payload = {
            "attestation": payload.attestation.model_dump(),
            "combined": combined.model_dump(),
            "epcis_payload": payload.epcis_payload,
            "facility_name": payload.facility_name,
            "record_status": record_status,
            "scan_data": parsed_scan_data,
            "transaction_information": parsed_ti_data,
        }
        if quarantine_path:
            event_payload["quarantine_path"] = quarantine_path

        audit_action = "DUAL_SCORE_ASSESSMENT"
        if record_status == "QUARANTINE_MISSING_DATA":
            audit_action = "QUARANTINE_SCAN_EVENT"

        event_hash, chain_prev_hash, hash_input = build_audit_event_hash_hardened(
            tenant_id=tenant_id,
            action=audit_action,
            resource="assessment",
            payload=event_payload,
            event_timestamp=event_timestamp,
            prev_event_hash=prev_event_hash,
        )

        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=None,
            action=audit_action,
            resource="assessment",
            prev_hash=chain_prev_hash,
            payload={
                "event_hash": event_hash,
                "hash_input": hash_input,
                "record_status": record_status,
            },
        )
        db.add(audit_log)
        await db.commit()
        await db.refresh(audit_log)

        return DualScoreResponse(
            **combined.model_dump(),
            audit_log_id=str(audit_log.id),
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=str(exc))
