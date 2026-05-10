from __future__ import annotations

import hashlib
import os
import platform
import uuid
from functools import lru_cache


def _read_first_existing(paths: list[str]) -> str | None:
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
            if value:
                return value
        except OSError:
            continue
    return None


def _host_fingerprint_seed() -> str:
    source = _read_first_existing(["/etc/machine-id", "/var/lib/dbus/machine-id"])
    if source:
        return source
    return platform.node().strip() or f"mac:{uuid.getnode():012x}"


@lru_cache(maxsize=1)
def get_device_id() -> str:
    """Return the device identifier used for hardware-bound audit hashing.

    Default behavior is environment-driven to keep repositories portable:
    1. SGS_DEVICE_ID (required in production)
    2. Optional host fingerprint fallback when SGS_ALLOW_HOST_FINGERPRINT=true
    """
    explicit_id = os.getenv("SGS_DEVICE_ID", "").strip()
    if explicit_id:
        return explicit_id

    allow_host_fingerprint = os.getenv("SGS_ALLOW_HOST_FINGERPRINT", "").lower() in {
        "1",
        "true",
        "yes",
    }
    if allow_host_fingerprint:
        return hashlib.sha256(_host_fingerprint_seed().encode("utf-8")).hexdigest()

    raise RuntimeError(
        "SGS_DEVICE_ID is not set. Set SGS_DEVICE_ID explicitly "
        "or enable SGS_ALLOW_HOST_FINGERPRINT=true for local lab-only fallback."
    )
