from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas import ScoreResponse


def _is_valid_gln(value: Any) -> bool:
    """Validate a 13-character GLN."""

    return isinstance(value, str) and value.isdigit() and len(value) == 13


def _extract_gln(payload: dict[str, Any]) -> str | None:
    """Extract a GLN from a common EPCIS payload location."""

    candidates = [
        payload.get("gln"),
        payload.get("bizLocation", {}).get("gln")
        if isinstance(payload.get("bizLocation"), dict)
        else None,
        payload.get("location", {}).get("gln")
        if isinstance(payload.get("location"), dict)
        else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, str):
            return candidate

    return None


def _extract_event_times(payload: dict[str, Any]) -> list[datetime]:
    """Extract event timestamps from an EPCIS payload."""

    raw_events: Any = payload.get("events") or payload.get("eventList") or []
    if not isinstance(raw_events, list):
        return []

    timestamps: list[datetime] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue

        raw_timestamp = event.get("timestamp") or event.get("eventTime")
        if not isinstance(raw_timestamp, str):
            continue

        try:
            timestamps.append(datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")))
        except ValueError:
            continue

    return timestamps


async def evaluate_dscsa_risk(payload: dict[str, Any]) -> ScoreResponse:
    """Evaluate DSCSA risk for an EPCIS JSON payload.

    Args:
        payload: EPCIS JSON document.

    Returns:
        ScoreResponse with a 0-100 score and risk tier.
    """

    score = 0

    gln = _extract_gln(payload)
    if _is_valid_gln(gln):
        score += 50

    event_times = _extract_event_times(payload)
    if event_times:
        score += 25
        if event_times == sorted(event_times):
            score += 25

    if score >= 80:
        risk_tier = "LOW"
    elif score >= 50:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "HIGH"

    return ScoreResponse(score=score, risk_tier=risk_tier)