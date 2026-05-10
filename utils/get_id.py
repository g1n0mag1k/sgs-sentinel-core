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


@lru_cache(maxsize=1)
def get_device_id() -> str:
    """Return a stable device identifier for hardware-bound audit hashing.

    Resolution order:
    1. SGS_DEVICE_ID env var (explicit override)
    2. Linux machine-id files
    3. Hostname
    4. MAC address from uuid.getnode()
    """
    explicit_id = os.getenv("SGS_DEVICE_ID", "").strip()
    if explicit_id:
        return explicit_id

    source = _read_first_existing(["/etc/machine-id", "/var/lib/dbus/machine-id"])
    if not source:
        source = platform.node().strip() or f"mac:{uuid.getnode():012x}"

    # Avoid storing raw machine identifiers while keeping deterministic binding.
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
