#!/usr/bin/env python3
import sys, subprocess
from pathlib import Path

def validate(snapshot):
    s = Path(snapshot)
    if not s.exists():
        print(f"[FAIL] {snapshot}"); return False
    for f in ['snapshot.yaml','SHA256SUMS.txt']:
        if not (s/f).exists():
            print(f"[FAIL] Missing: {f}"); return False
    print('[PASS] Metadata')
    r = subprocess.run(['python3','-m','pytest','integration/test_cases/test_bounded_property.py','-v'],
        capture_output=True, text=True, timeout=60, cwd='.')
    if r.returncode != 0:
        print('[FAIL] Bounded test'); return False
    print('[PASS] Bounded test'); print('[PASS] All checks'); return True

if __name__ == '__main__':
    sys.exit(0 if len(sys.argv)>1 and validate(sys.argv[1]) else 1)
