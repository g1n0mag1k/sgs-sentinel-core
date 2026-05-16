"""Scoring and assessment functions for DSCSA compliance."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Facility
from app.schemas import ScoreResponse, DualScoreResponse, M1M6Attestation, AttestationAnswer


def _extract_gln(payload: dict[str, Any]) -> str:
    """Extract GLN (Global Location Number) from EPCIS payload."""
    # Try common EPCIS payload locations for GLN
    if "bizLocation" in payload:
        biz_loc = payload["bizLocation"]
        if isinstance(biz_loc, dict):
            if "gln" in biz_loc:
                return str(biz_loc["gln"])
            if "id" in biz_loc:
                gln = biz_loc["id"]
                # Extract numeric GLN from URN (e.g., "urn:epc:id:sgln:0614141.00000.0")
                if "sgln:" in gln:
                    parts = gln.split("sgln:")[-1].split(".")
                    if len(parts) >= 2:
                        return parts[0] + parts[1]
                return gln

    if "metadata" in payload:
        meta = payload.get("metadata", {})
        if isinstance(meta, dict):
            root = meta.get("root", {})
            if isinstance(root, dict) and "gln" in root:
                return str(root["gln"])

    if "events" in payload:
        events = payload.get("events", [])
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                biz_loc = event.get("bizLocation")
                if isinstance(biz_loc, dict):
                    if "gln" in biz_loc:
                        return str(biz_loc["gln"])
                    if "id" in biz_loc:
                        return str(biz_loc["id"])
                read_point = event.get("readPoint")
                if isinstance(read_point, dict) and "id" in read_point:
                    gln = str(read_point["id"])
                    if "sgln:" in gln:
                        parts = gln.split("sgln:")[-1].split(".")
                        if len(parts) >= 2:
                            return parts[0] + parts[1]
                    return gln
    
    if "sensorElementList" in payload:
        sensors = payload.get("sensorElementList", [])
        if sensors and isinstance(sensors, list):
            for sensor in sensors:
                if "sensorElement" in sensor:
                    for elem in sensor["sensorElement"]:
                        if "id" in elem:
                            return elem["id"]
    
    return ""


def _extract_event_times(payload: dict[str, Any]) -> list[int]:
    """Extract and convert event timestamps to sortable format."""
    times = []
    
    # Check for eventTime in payload
    if "eventTime" in payload:
        try:
            # Convert ISO timestamp to integer for comparison
            event_time = payload["eventTime"]
            if isinstance(event_time, str):
                # Simple conversion: count digits to create comparable int
                times.append(int(event_time.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")[:12]))
        except (ValueError, TypeError):
            pass
    
    # Check for event list
    if "eventList" in payload:
        for event in payload["eventList"]:
            if "eventTime" in event:
                try:
                    event_time = event["eventTime"]
                    if isinstance(event_time, str):
                        times.append(int(event_time.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")[:12]))
                except (ValueError, TypeError):
                    pass
    
    return times


def _validate_gln_check_digit(gln: str) -> bool:
    """GS1 standard: weighted sum mod 10 == 0."""
    if not gln or not gln.isdigit() or len(gln) != 13:
        return False
    weights = [3 if i % 2 else 1 for i in range(12)]
    total = sum(int(d) * w for d, w in zip(gln[:12], weights))
    check = (10 - (total % 10)) % 10
    return check == int(gln[12])


async def evaluate_dscsa_risk(
    payload: dict[str, Any],
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> ScoreResponse:
    """Evaluate DSCSA compliance risk from EPCIS payload.
    
    Returns technical score (0-100), risk tier, and flags explaining the assessment.
    """
    score = 0
    flags: list[str] = []

    gln = _extract_gln(payload)

    # Check digit validity (20 pts)
    if gln and _validate_gln_check_digit(gln):
        score += 20
    else:
        flags.append("GLN_CHECK_DIGIT_FAIL")

    # GLN registered in Facility table for this tenant (30 pts)
    if gln:
        result = await db.execute(
            select(Facility).where(
                Facility.gln == gln,
                Facility.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none():
            score += 30
        else:
            flags.append("GLN_NOT_IN_FACILITY_REGISTRY")

    # Event timestamps present and chronological (25 pts)
    event_times = _extract_event_times(payload)
    if event_times:
        score += 15
        if event_times == sorted(event_times):
            score += 10

    # EPCIS 2.0 context header present (25 pts)
    ctx = payload.get("@context", "")
    if "epcis/2.0" in str(ctx).lower():
        score += 25
    else:
        flags.append("EPCIS_VERSION_MISSING_OR_1X")

    if score >= 80:
        risk_tier = "LOW"
    elif score >= 50:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "HIGH"

    return ScoreResponse(score=score, risk_tier=risk_tier, flags=flags)


def score_attestation(attestation: M1M6Attestation) -> tuple[float, str, list[str]]:
    """Score self-attestation responses.
    
    Returns:
        - self_attested_score: float 0.0-1.0
        - self_attested_grade: letter grade A-F
        - gaps: list of question IDs where answer was not 'yes'
    """
    answers = attestation.answers
    if not answers:
        return 0.0, "F", list(answers.keys())
    
    gaps: list[str] = []
    yes_count = 0
    
    for question_id, answer in answers.items():
        if answer == "yes":
            yes_count += 1
        else:
            gaps.append(question_id)
    
    # Calculate score as proportion of "yes" answers
    score = yes_count / len(answers)
    
    # Determine grade
    if score >= 0.9:
        grade = "A"
    elif score >= 0.8:
        grade = "B"
    elif score >= 0.7:
        grade = "C"
    elif score >= 0.6:
        grade = "D"
    else:
        grade = "F"
    
    return score, grade, gaps


def calculate_dual_score(
    technical_score: ScoreResponse,
    attestation_score: float,
    attestation_grade: str,
    flags: list[str],
    gaps: list[str],
) -> DualScoreResponse:
    """Combine technical and attestation scores into final response.
    
    Args:
        technical_score: ScoreResponse from EPCIS evaluation
        attestation_score: 0.0-1.0 float from attestation
        attestation_grade: Letter grade from attestation
        flags: Flag list from technical evaluation
        gaps: Gap list from attestation evaluation
    
    Returns:
        DualScoreResponse with combined scores, verdict, and audit info
    """
    # Calculate score delta (technical vs attested, scaled to 0-100)
    attested_scaled = int(attestation_score * 100)
    score_delta = technical_score.score - attested_scaled
    
    # Determine verdict based on alignment and grades
    if technical_score.risk_tier == "CRITICAL" or attestation_grade == "F":
        attestation_verdict = "CRITICAL_FAILURE"
    elif technical_score.risk_tier == "HIGH" or gaps:
        attestation_verdict = "NON_COMPLIANT"
    else:
        attestation_verdict = "COMPLIANT"
    
    # Determine overall risk tier (worse of the two)
    if technical_score.risk_tier == "HIGH" or attestation_grade in ["F", "D"]:
        overall_risk = "CRITICAL" if attestation_grade == "F" else "HIGH"
    else:
        overall_risk = technical_score.risk_tier
    
    return DualScoreResponse(
        deterministic_technical_score=technical_score.score,
        self_attested_score=attestation_score,
        self_attested_grade=attestation_grade,  # type: ignore
        risk_tier=overall_risk,  # type: ignore
        attestation_verdict=attestation_verdict,  # type: ignore
        score_delta=score_delta,
        flags=flags,
        gaps=gaps,
    )


def compute_score(
    answers: dict[str, AttestationAnswer],
    profile: str | None = None,
) -> dict[str, Any]:
    """Compute deterministic server-side score from attestation answers and profile.
    
    This is the AUTHORITATIVE SOURCE OF TRUTH for score calculation.
    No client-submitted score data is trusted. Only answers and profile matter.
    
    Args:
        answers: Attestation answers dict (e.g., {"M1-Q1": "yes", "M2-Q3": "no", ...})
        profile: Profile type ('manufacturer', 'distributor', etc). Defaults to 'manufacturer'.
    
    Returns:
        Dictionary with keys:
            - overall_pct: 0-100 integer percentage of "yes" answers
            - grade: Letter grade A-F based on percentage
            - verdict: Compliance verdict (COMPLIANT, NON_COMPLIANT, CRITICAL_FAILURE)
            - risk_tier: Risk tier (LOW, MEDIUM, HIGH, CRITICAL)
            - gaps: List of question IDs where answer was not "yes"
    """
    # Default profile if not provided
    if profile is None:
        profile = "manufacturer"
    
    # Handle empty answers
    if not answers:
        return {
            "overall_pct": 0,
            "grade": "F",
            "verdict": "CRITICAL_FAILURE",
            "risk_tier": "CRITICAL",
            "gaps": [],
        }
    
    gaps: list[str] = []
    yes_count = 0
    
    # Count "yes" answers and collect gaps
    for question_id, answer in answers.items():
        if answer == "yes":
            yes_count += 1
        else:
            gaps.append(question_id)
    
    # Calculate percentage score
    overall_pct = int((yes_count / len(answers)) * 100)
    
    # Determine grade (A-F) based on percentage
    if overall_pct >= 90:
        grade = "A"
    elif overall_pct >= 80:
        grade = "B"
    elif overall_pct >= 70:
        grade = "C"
    elif overall_pct >= 60:
        grade = "D"
    else:
        grade = "F"
    
    # Determine verdict based on grade
    if grade == "F":
        verdict = "CRITICAL_FAILURE"
    elif grade in ["D", "C"]:
        verdict = "NON_COMPLIANT"
    else:
        verdict = "COMPLIANT"
    
    # Determine risk tier (inverse of grade quality)
    if grade == "F":
        risk_tier = "CRITICAL"
    elif grade in ["D", "C"]:
        risk_tier = "HIGH"
    elif grade == "B":
        risk_tier = "MEDIUM"
    else:
        risk_tier = "LOW"
    
    return {
        "overall_pct": overall_pct,
        "grade": grade,
        "verdict": verdict,
        "risk_tier": risk_tier,
        "gaps": gaps,
    }