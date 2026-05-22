#!/usr/bin/env python3
"""
WAL Replay Verifier
====================
Validates WAL integrity: seq continuity, checksum correctness, no corruption.

Usage:
  python3 wal_replay_verify.py <root_path> [instance_id]
"""

import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "stable"))
from wal_manager import WALManager


def verify_instance(root: str, instance_id: str = None) -> dict:
    wal = WALManager(root=root, instance_id=instance_id)
    return wal.verify()


def main():
    if len(sys.argv) < 2:
        print("Usage: wal_replay_verify.py <root_path> [instance_id]")
        sys.exit(1)

    root = sys.argv[1]
    instance_id = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"[VERIFY] root={root} instance_id={instance_id}")

    report = verify_instance(root, instance_id)

    print(f"\n{'='*60}")
    print(f"WAL VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"  instance_id:      {report['instance_id']}")
    print(f"  wal_dir:         {report['wal_dir']}")
    print(f"  wal_files:        {report['wal_files']}")
    print(f"  total_entries:    {report['total_entries']}")
    print(f"  checksum_errors:  {report['checksum_errors']}")
    print(f"  seq_gaps:         {len(report['seq_gaps'])}")
    print(f"  corrupted_lines:   {len(report['corrupted_lines'])}")
    print(f"  verified:          {report['verified']}")

    if report["seq_gaps"]:
        print(f"\nSEQ GAPS:")
        for gap in report["seq_gaps"][:5]:
            print(f"  {gap}")

    if report["corrupted_lines"]:
        print(f"\nCORRUPTED LINES:")
        for corr in report["corrupted_lines"][:5]:
            print(f"  {corr}")

    # Save report
    out_path = os.path.join(root, "runtime_logs", "replay",
                           report["instance_id"],
                           f"verification_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[SAVED] {out_path}")

    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
