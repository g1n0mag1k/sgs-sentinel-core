from __future__ import annotations

import hashlib
import json
import uuid
from html import escape
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Assessment, AuditLog
from app.parsers import QuarantineMissingDataError, parse_dscsa_event
from app.schemas import DualScoreRequest, DualScoreResponse
from app.services.audit_hash import build_audit_event_hash_hardened
from app.services.quarantine import persist_quarantine_event
from app.services.scoring import compute_score

router = APIRouter(prefix="/api/v1/assessment", tags=["assessment"])


def _profile_track_label(profile: str) -> str:
    normalized_profile = profile.strip().lower()
    if normalized_profile == "manufacturer":
        return "§582(g) Manufacturer"
    return "§582(g) Small Dispenser"


def _format_gap_finding(gap: str) -> tuple[str, str]:
    code = gap.strip() or "UNKNOWN"
    description = f"Missing affirmative attestation for control {code}."
    return description, code


def _build_report_html(assessment: Assessment) -> tuple[str, str]:
    assessment_date = assessment.assessment_date
    if assessment_date.tzinfo is None:
        assessment_date = assessment_date.replace(tzinfo=timezone.utc)
    assessment_date_utc = assessment_date.astimezone(timezone.utc)

    profile = assessment.profile or "manufacturer"
    profile_label = _profile_track_label(profile)
    gaps = list(assessment.gaps or [])[:3]
    findings = [_format_gap_finding(gap) for gap in gaps]

    report_context = {
        "audit_log_id": str(assessment.audit_log_id),
        "assessment_date": assessment_date_utc.isoformat(timespec="seconds"),
        "attestor_name": assessment.attestor_name or "Not provided",
        "attestor_title": assessment.attestor_title or "Not provided",
        "facility_name": assessment.facility_name,
        "gaps": gaps,
        "grade": assessment.grade,
        "overall_pct": assessment.overall_pct,
        "paid": assessment.paid,
        "profile": profile,
        "profile_label": profile_label,
        "risk_tier": assessment.risk_tier,
        "verdict": assessment.verdict,
    }
    signature = hashlib.sha256(
        json.dumps(report_context, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()

    if findings:
        finding_cards = "".join(
            f"""
            <div class=\"finding-card\">
                <div class=\"finding-index\">Finding {index}</div>
                <div class=\"finding-description\">Description: {escape(description)}</div>
                <div class=\"finding-action\">Action Code: {escape(action_code)}</div>
            </div>
            """
            for index, (description, action_code) in enumerate(findings, start=1)
        )
    else:
        finding_cards = "<div class='finding-card'><div class='finding-description'>No reportable gaps were recorded.</div></div>"

    html_content = f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <style>
            @page {{
                size: A4;
                margin: 18mm 15mm 18mm 15mm;
                @bottom-center {{
                    content: "Sui-Generis LLC | ALCOA+ Integrity Anchor: {signature}";
                    font-size: 8pt;
                    color: #5b6472;
                }}
            }}
            body {{
                font-family: Arial, Helvetica, sans-serif;
                color: #1f2937;
                line-height: 1.45;
                margin: 0;
            }}
            .shell {{
                border: 1px solid #d5dbe3;
                border-radius: 14px;
                padding: 22px;
            }}
            .brand {{
                font-size: 13pt;
                font-weight: 700;
                letter-spacing: 0.08em;
                color: #0f172a;
                text-transform: uppercase;
            }}
            .title {{
                font-size: 22pt;
                margin: 6px 0 8px 0;
                color: #0f172a;
            }}
            .subtitle {{
                font-size: 10.5pt;
                color: #475569;
                margin-bottom: 18px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 14px;
                margin-top: 16px;
            }}
            .card {{
                border: 1px solid #dbe3ea;
                border-radius: 12px;
                padding: 14px;
                background: #f8fafc;
            }}
            .label {{
                font-size: 8.5pt;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #64748b;
                margin-bottom: 4px;
            }}
            .value {{
                font-size: 11.5pt;
                font-weight: 700;
                color: #0f172a;
            }}
            .section-title {{
                margin-top: 22px;
                margin-bottom: 10px;
                font-size: 13pt;
                font-weight: 700;
                color: #111827;
            }}
            .finding-card {{
                border-left: 4px solid #0f766e;
                background: #ecfeff;
                padding: 12px 14px;
                margin-bottom: 10px;
                border-radius: 8px;
            }}
            .finding-index {{
                font-size: 9pt;
                font-weight: 700;
                color: #0f766e;
                margin-bottom: 4px;
            }}
            .finding-description, .finding-action {{
                font-size: 10.5pt;
                color: #0f172a;
            }}
            .footer-note {{
                margin-top: 22px;
                font-size: 8.5pt;
                color: #6b7280;
                border-top: 1px solid #e5e7eb;
                padding-top: 10px;
            }}
            .signature-box {{
                margin-top: 10px;
                font-size: 8.5pt;
                color: #111827;
                word-break: break-all;
            }}
        </style>
    </head>
    <body>
        <div class=\"shell\">
            <div class=\"brand\">Sui-Generis LLC</div>
            <div class=\"title\">DSCSA Compliance Assessment Report</div>
            <div class=\"subtitle\">Validated PDF output for regulated review and payment-controlled distribution.</div>

            <div class=\"grid\">
                <div class=\"card\">
                    <div class=\"label\">Facility Name</div>
                    <div class=\"value\">{escape(assessment.facility_name)}</div>
                </div>
                <div class=\"card\">
                    <div class=\"label\">Attestor Name</div>
                    <div class=\"value\">{escape(assessment.attestor_name or 'Not provided')}</div>
                </div>
                <div class=\"card\">
                    <div class=\"label\">Attestor Title</div>
                    <div class=\"value\">{escape(assessment.attestor_title or 'Not provided')}</div>
                </div>
                <div class=\"card\">
                    <div class=\"label\">Assessment Date (UTC)</div>
                    <div class=\"value\">{escape(assessment_date_utc.strftime('%Y-%m-%d %H:%M:%S UTC'))}</div>
                </div>
                <div class=\"card\">
                    <div class=\"label\">Regulatory Track</div>
                    <div class=\"value\">{escape(profile_label)}</div>
                </div>
                <div class=\"card\">
                    <div class=\"label\">Audit Log ID</div>
                    <div class=\"value\">{escape(str(assessment.audit_log_id))}</div>
                </div>
            </div>

            <div class=\"section-title\">Score Framework</div>
            <div class=\"grid\">
                <div class=\"card\"><div class=\"label\">Overall Score</div><div class=\"value\">{assessment.overall_pct}%</div></div>
                <div class=\"card\"><div class=\"label\">Grade</div><div class=\"value\">{escape(assessment.grade)}</div></div>
                <div class=\"card\"><div class=\"label\">Risk Tier</div><div class=\"value\">{escape(assessment.risk_tier)}</div></div>
                <div class=\"card\"><div class=\"label\">Verdict</div><div class=\"value\">{escape(assessment.verdict)}</div></div>
            </div>

            <div class=\"section-title\">Top Findings</div>
            {finding_cards}

            <div class=\"footer-note\">
                Official regulatory disclaimer: This report is generated from the system's validated server-side assessment controls and is provided for compliance support only. It does not constitute legal advice, a regulatory determination, or a substitute for professional review.
                <div class=\"signature-box\">ALCOA+ Data Integrity Anchor: {signature}</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content, signature


@router.post("/dual-score", response_model=DualScoreResponse)
async def dual_score_assessment(
    payload: DualScoreRequest,
    db: AsyncSession = Depends(get_db),
) -> DualScoreResponse:
    """Evaluate dual-score assessment from EPCIS payload and attestation."""
    try:
        # Demo-friendly: use a stable tenant id unless auth is wired.
        tenant_id = uuid.UUID(int=0)
        tenant_id_str = str(tenant_id)
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

        # AUTHORITATIVE SCORING: Server-side compute_score() is the sole source of truth
        # Extract answers from attestation and profile from request (default to 'manufacturer')
        answers = payload.attestation.answers
        profile = payload.profile if payload.profile else "manufacturer"
        
        # Compute deterministic score server-side - NO CLIENT DATA IS TRUSTED
        score_result = compute_score(answers, profile)
        
        # Build response using only server-computed values
        combined = DualScoreResponse(
            deterministic_technical_score=score_result["overall_pct"],
            self_attested_score=score_result["overall_pct"] / 100.0,  # Convert back to 0-1 range
            self_attested_grade=score_result["grade"],  # type: ignore
            risk_tier=score_result["risk_tier"],  # type: ignore
            attestation_verdict=score_result["verdict"],  # type: ignore
            score_delta=0,  # No delta needed since server is authoritative
            flags=[],  # Server-computed scores don't have EPCIS flags in this context
            gaps=score_result["gaps"],
        )

        # Resolve previous event hash; first record in chain uses GENESIS.
        latest_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id_str)
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
            tenant_id=tenant_id_str,
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
        await db.flush()
        assessment = Assessment(
            audit_log_id=audit_log.id,
            tenant_id=tenant_id_str,
            facility_name=payload.facility_name,
            attestor_name=payload.attestor_name,
            attestor_title=payload.attestor_title,
            assessment_date=datetime.now(timezone.utc),
            profile=profile,
            paid=payload.paid,
            overall_pct=score_result["overall_pct"],
            grade=score_result["grade"],
            risk_tier=score_result["risk_tier"],
            verdict=score_result["verdict"],
            gaps=score_result["gaps"],
        )
        db.add(assessment)
        await db.commit()
        await db.refresh(audit_log)
        await db.refresh(assessment)

        return DualScoreResponse(
            **combined.model_dump(exclude={"audit_log_id"}),
            audit_log_id=str(audit_log.id),
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{audit_log_id}/report")
async def get_assessment_report(
    audit_log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render a tamper-evident PDF assessment report for a paid assessment."""
    from weasyprint import HTML

    result = await db.execute(
        select(Assessment).where(Assessment.audit_log_id == audit_log_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if not assessment.paid:
        raise HTTPException(status_code=402, detail="Payment required for report access")

    html_content, signature = _build_report_html(assessment)
    pdf_bytes = HTML(string=html_content).write_pdf()

    headers = {
        "Content-Disposition": f'attachment; filename=SGS_Sentinel_Report_{audit_log_id}.pdf',
        "X-Integrity-Signature": signature,
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
