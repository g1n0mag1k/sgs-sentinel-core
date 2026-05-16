from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import weasyprint
from fastapi import status
from sqlalchemy import select

from app.main import app
from app.models import Assessment
from app.routers.assessments import _build_report_html


def _assessment_fixture() -> Assessment:
    return Assessment(
        audit_log_id=uuid4(),
        tenant_id=uuid4(),
        facility_name="Sui-Generis Test Lab",
        attestor_name="Andrew C. Rogers",
        attestor_title="Lead Engineer",
        assessment_date=datetime(2026, 5, 10, 12, 30, 45, tzinfo=timezone.utc),
        profile="manufacturer",
        paid=False,
        overall_pct=90,
        grade="A",
        risk_tier="LOW",
        verdict="COMPLIANT",
        gaps=["Q03", "Q07", "Q09", "Q10"],
    )


def test_report_html_includes_governed_content() -> None:
    assessment = _assessment_fixture()

    html, signature = _build_report_html(assessment)

    assert len(signature) == 64
    assert "Sui-Generis LLC" in html
    assert "ALCOA+ Data Integrity Anchor" in html
    assert str(assessment.audit_log_id) in html
    assert "§582(g) Manufacturer" in html
    assert "Sui-Generis Test Lab" in html
    assert "Andrew C. Rogers" in html
    assert "Missing affirmative attestation for control Q03." in html
    assert "Missing affirmative attestation for control Q07." in html
    assert "Missing affirmative attestation for control Q09." in html
    assert "Q10" not in html


def test_cors_policy_includes_validated_origins() -> None:
    cors_middleware = next(middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")

    assert "https://sentinel1.tech" in cors_middleware.kwargs["allow_origins"]
    assert "https://docs.sui-g3n3ri.me" in cors_middleware.kwargs["allow_origins"]


@pytest.mark.asyncio
async def test_assessment_and_pdf_report_lifecycle(async_client, db_session, monkeypatch) -> None:
    payload = {
        "epcis_payload": {
            "scan_data": {
                "barcode": "00312345000012",
                "eventTime": "2026-05-10T12:30:45Z",
                "lot_number": "LOT-2026-05",
                "serial_number": "SN-998877",
            },
            "transaction_information": {
                "transaction_id": "TX-2026-05-10",
            },
        },
        "attestation": {
            "answers": {
                "Q01": "yes",
                "Q02": "yes",
                "Q03": "no",
                "Q04": "yes",
                "Q05": "yes",
                "Q06": "yes",
                "Q07": "yes",
                "Q08": "yes",
                "Q09": "yes",
                "Q10": "yes",
            },
            "submitted_glns": ["0614141000006"],
        },
        "facility_name": "Sui-Generis Test Lab",
        "profile": "manufacturer",
        "attestor_name": "Andrew C. Rogers",
        "attestor_title": "Lead Engineer",
        "paid": False,
    }

    score_response = await async_client.post("/api/v1/assessment/dual-score", json=payload)

    assert score_response.status_code == status.HTTP_200_OK
    score_data = score_response.json()
    assert score_data["audit_log_id"]
    assert score_data["deterministic_technical_score"] == 90
    assert score_data["self_attested_grade"] == "A"
    assert score_data["risk_tier"] == "LOW"
    assert score_data["attestation_verdict"] == "COMPLIANT"
    assert score_data["gaps"] == ["Q03"]

    audit_log_id = score_data["audit_log_id"]
    report_url = f"/api/v1/assessment/{audit_log_id}/report"

    unpaid_response = await async_client.get(report_url)
    assert unpaid_response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert unpaid_response.json()["detail"] == "Payment required for report access"

    result = await db_session.execute(
        select(Assessment).where(Assessment.audit_log_id == audit_log_id)
    )
    assessment = result.scalar_one_or_none()
    assert assessment is not None
    assert assessment.paid is False

    assessment.paid = True
    await db_session.commit()

    captured: dict[str, str] = {}

    class FakeHTML:
        def __init__(self, string: str) -> None:
            captured["html"] = string

        def write_pdf(self) -> bytes:
            return b"%PDF-1.4\n%pytest\n%%EOF"

    monkeypatch.setattr(weasyprint, "HTML", FakeHTML)

    paid_response = await async_client.get(report_url)

    assert paid_response.status_code == status.HTTP_200_OK
    assert paid_response.headers["content-type"] == "application/pdf"
    assert paid_response.headers["content-disposition"] == (
        f"attachment; filename=SGS_Sentinel_Report_{audit_log_id}.pdf"
    )
    assert paid_response.content.startswith(b"%PDF")
    assert captured["html"]
    assert str(audit_log_id) in captured["html"]
    assert "Sui-Generis LLC" in captured["html"]
    assert "ALCOA+ Data Integrity Anchor" in captured["html"]