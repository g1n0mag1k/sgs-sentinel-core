from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedDSCSAEvent:
    """Normalized subset used for DSCSA continuity and quarantine decisions."""

    scan_data: dict[str, Any]
    ti_data: dict[str, Any]


class QuarantineMissingDataError(ValueError):
    """Raised when physical scan data exists but EPCIS TI is absent."""

    def __init__(self, *, scan_data: dict[str, Any], message: str) -> None:
        super().__init__(message)
        self.scan_data = scan_data


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _extract_scan_data(payload: dict[str, Any]) -> dict[str, Any]:
    scan_keys = {
        "barcode",
        "serial_number",
        "lot_number",
        "eventTime",
        "eventTimeZoneOffset",
        "bizLocation",
        "readPoint",
        "sensorElementList",
        "scan",
        "scan_data",
        "events",
    }
    scan_data = {k: payload[k] for k in scan_keys if k in payload}

    if scan_data:
        return scan_data

    first_event = _first_dict(payload.get("events", []))
    if first_event:
        return {
            k: first_event[k]
            for k in scan_keys
            if k in first_event
        }

    return {}


def _extract_ti_data(payload: dict[str, Any]) -> dict[str, Any]:
    ti_keys = (
        "transaction_information",
        "transactionInformation",
        "transaction_info",
        "ti",
    )
    for key in ti_keys:
        candidate = payload.get(key)
        if isinstance(candidate, dict) and candidate:
            return candidate

    first_event = _first_dict(payload.get("events", []))
    for key in ti_keys:
        candidate = first_event.get(key)
        if isinstance(candidate, dict) and candidate:
            return candidate

    return {}


def parse_dscsa_event(payload: dict[str, Any]) -> ParsedDSCSAEvent:
    """Parse DSCSA payload and enforce quarantine criteria for missing TI."""
    scan_data = _extract_scan_data(payload)
    ti_data = _extract_ti_data(payload)

    if scan_data and not ti_data:
        raise QuarantineMissingDataError(
            scan_data=scan_data,
            message="Physical scan data present but EPCIS Transaction Information is missing.",
        )

    return ParsedDSCSAEvent(scan_data=scan_data, ti_data=ti_data)
