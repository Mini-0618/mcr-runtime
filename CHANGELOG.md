# Changelog

All notable changes are documented here. Versions mirror git tags.

## v0.9.3 — External onboarding hotfix

**Date:** 2025
**Tag:** v0.9.3

- README: switched Quickstart clone URL from SSH to HTTPS
- README: added "Quickstart for External Users" section
- README: added Requirements (Python 3.10+, no API key, no database)
- README: added Recommended Demo Order
- README: added Troubleshooting section (4 common issues)
- README: added Developer Verification section with pytest install note
- scripts/verify_all.sh: added pytest version check with install hint

**Recommended for:** All external users. Start here.

---

## v0.9.2 — Regression-protected engineering artifact

**Date:** 2025
**Tag:** v0.9.2

- Added `tests/test_minimal_replay.py` — verify minimal_mcr.py replay hash
- Added `tests/test_runtime_replay.py` — verify modular runtime path replay
- Added `tests/test_hermes_bridge_mock.py` — verify Hermes Bridge mock integration
- Added `tests/test_no_token_leak.py` — grep for ghp_/github_pat_ token leaks
- Added `scripts/verify_all.sh` — run all 4 demos + pytest in sequence
- Added `.github/workflows/python-tests.yml` — CI on push/PR
- README: added Developer Verification section
- Fixed pytest return-value warning in test_g2_replay.py

**Recommended for:** Contributors and CI verification.

---

## v0.9.1 — Demo-ready release

**Date:** 2025
**Tag:** v0.9.1

- Added `examples/minimal_mcr.py` (~200 lines, self-contained concept demo)
- Fixed WAL residue bug across all demos
- README: updated Quickstart with 4-demo matrix and SSH clone URL
- README: clone URL switched to SSH (later changed to HTTPS in v0.9.3)
- Added demo walkthrough documentation

**Recommended for:** Users who want to understand MCR core concept before reading modular code.

---

## v0.9.0 — Event-sourced runtime snapshot

**Date:** 2025
**Tag:** v0.9.0

- Event-sourced runtime kernel (WAL / reducer / replay verifier)
- Hermes Bridge v0.1 integration adapter
- Initial replay verification demos
- 5-hour autonomous loop with G2 assertions throughout
- Initial GitHub release

**Recommended for:** Understanding the origin of the event-sourced architecture.

---

*Older releases (pre-v0.9.0) are experimental Phase I–VI artifacts and not tagged.*