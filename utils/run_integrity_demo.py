from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

from utils.tamper_audit_demo import apply_tamper, restore_tamper
from utils.verify_integrity import verify_audit_chain


def _banner(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


async def run_demo(
    *,
    tenant_id: Optional[str],
    record_id: Optional[str],
    keep_tampered: bool,
) -> int:
    _banner("SGS-Sentinel Integrity Demo: Start")
    print("Step 1/5: Baseline integrity verification")
    baseline_code = await verify_audit_chain(tenant_id=tenant_id)
    if baseline_code != 0:
        print("Baseline check failed. Resolve existing issues before running demo.")
        return 1

    tamper_applied = False
    try:
        _banner("Step 2/5: Apply Controlled Tamper")
        apply_code = await apply_tamper(tenant_id=tenant_id, record_id=record_id)
        if apply_code != 0:
            print("Unable to apply tamper. Aborting demo.")
            return 1
        tamper_applied = True

        _banner("Step 3/5: Verify Breach Detection")
        breach_code = await verify_audit_chain(tenant_id=tenant_id)
        if breach_code == 0:
            print("Expected breach detection did not occur.")
            return 1
        print("PASS: Integrity verifier detected the tamper event.")

        if keep_tampered:
            _banner("Step 4/5: Restore Skipped By Request")
            print("Tampered state intentionally preserved (--keep-tampered).")
            print("Run restore manually: python utils/tamper_audit_demo.py restore")
            return 0

        _banner("Step 4/5: Restore Original Record")
        restore_code = await restore_tamper()
        if restore_code != 0:
            print("Restore failed. Immediate manual action required.")
            return 1
        tamper_applied = False

        _banner("Step 5/5: Final Integrity Verification")
        final_code = await verify_audit_chain(tenant_id=tenant_id)
        if final_code != 0:
            print("Final verification failed after restore.")
            return 1

        _banner("Demo Result")
        print("SUCCESS: Baseline pass, breach detected, restore completed, final pass.")
        return 0

    finally:
        # Safety net: if any mid-run failure occurred after tamper, restore automatically.
        if tamper_applied and not keep_tampered:
            try:
                print("\nSafety restore: attempting automatic cleanup...")
                await restore_tamper()
            except Exception as exc:
                print(f"Safety restore failed: {exc}")
                print("Run manually: python utils/tamper_audit_demo.py restore")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run full integrity demo: verify, tamper, detect, restore, verify.",
    )
    parser.add_argument(
        "--tenant-id",
        help="Optional tenant UUID filter used by verifier and tamper selection.",
    )
    parser.add_argument(
        "--record-id",
        help="Optional explicit record UUID to tamper. Overrides tenant targeting.",
    )
    parser.add_argument(
        "--keep-tampered",
        action="store_true",
        help="Do not restore automatically (for forensic demos).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(
            run_demo(
                tenant_id=args.tenant_id,
                record_id=args.record_id,
                keep_tampered=args.keep_tampered,
            )
        )
    except Exception as exc:
        print(f"Demo failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
