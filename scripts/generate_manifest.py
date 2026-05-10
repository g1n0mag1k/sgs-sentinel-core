#!/usr/bin/env python3
"""
Validated Engineering Utility
Lead Engineer: Andrew C. Rogers (Sui-Generis)
Date: 2026-05-10

Generate SHA-256 evidence manifest for all files under docs/.
Output: docs/04_Evidence/HASH_MANIFEST.txt
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ManifestRecord:
    sha256: str
    file_path: str
    contemporaneous_timestamp_utc: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def compute_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_docs_files(docs_root: Path, manifest_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(docs_root.rglob("*")):
        if not path.is_file():
            continue
        # Exclude output to avoid self-referential hash drift.
        if path.resolve() == manifest_path.resolve():
            continue
        files.append(path)
    return files


def build_records(repo_root: Path, docs_root: Path, manifest_path: Path) -> list[ManifestRecord]:
    records: list[ManifestRecord] = []
    for file_path in collect_docs_files(docs_root, manifest_path):
        records.append(
            ManifestRecord(
                sha256=compute_sha256(file_path),
                file_path=file_path.relative_to(repo_root).as_posix(),
                contemporaneous_timestamp_utc=utc_now_iso(),
            )
        )
    return records


def write_manifest(manifest_path: Path, records: list[ManifestRecord]) -> None:
    header_lines = [
        "# HASH MANIFEST",
        "Lead Engineer: Andrew C. Rogers (Sui-Generis)",
        "Date: 2026-05-10",
        f"Generated At (UTC): {utc_now_iso()}",
        "Scope: All files under docs/",
        "",
        "SHA256 | FILE_PATH | CONTEMPORANEOUS_TIMESTAMP_UTC",
        "--- | --- | ---",
    ]

    body_lines = [
        f"{record.sha256} | {record.file_path} | {record.contemporaneous_timestamp_utc}"
        for record in records
    ]

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(header_lines + body_lines) + "\n", encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docs_root = repo_root / "docs"
    manifest_path = docs_root / "04_Evidence" / "HASH_MANIFEST.txt"

    if not docs_root.exists() or not docs_root.is_dir():
        raise FileNotFoundError("docs/ directory not found. Run from repository context.")

    records = build_records(repo_root, docs_root, manifest_path)
    write_manifest(manifest_path, records)

    print(f"Manifest generated: {manifest_path.relative_to(repo_root).as_posix()}")
    print(f"Files hashed: {len(records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
