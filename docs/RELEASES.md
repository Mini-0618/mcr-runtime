# Releases

## v0.9.3 — External onboarding hotfix

| Field | Value |
|-------|-------|
| **Version** | v0.9.3 |
| **Date** | 2025 |
| **Type** | Documentation / onboarding hotfix |
| **Tag** | `v0.9.3` |

### What changed

- README: HTTPS clone, Quickstart for External Users, Recommended Demo Order, Troubleshooting
- scripts/verify_all.sh: pytest version check with install hint

### Recommended for

**All external users.** This is the recommended starting point for anyone discovering MCR for the first time.

### Known limitations

- Still a research runtime artifact, not production-ready
- External user trial feedback not yet collected

---

## v0.9.2 — Regression-protected engineering artifact

| Field | Value |
|-------|-------|
| **Version** | v0.9.2 |
| **Date** | 2025 |
| **Type** | Engineering / test infrastructure |
| **Tag** | `v0.9.2` |

### What changed

- Added `tests/` regression suite (8 tests, all pass)
- Added `scripts/verify_all.sh` verification script
- Added `.github/workflows/python-tests.yml` CI
- Added `tests/test_no_token_leak.py` token leak regression test
- Fixed pytest return-value warning

### Recommended for

Contributors and CI verification. External users should prefer v0.9.3.

### Known limitations

- README onboarding was incomplete (SSH clone was default, pytest requirement unclear)
- Fixed in v0.9.3

---

## v0.9.1 — Demo-ready release

| Field | Value |
|-------|-------|
| **Version** | v0.9.1 |
| **Date** | 2025 |
| **Type** | Demo hardening |
| **Tag** | `v0.9.1` |

### What changed

- Added `examples/minimal_mcr.py` (~200 lines, self-contained concept demo)
- WAL residue bug fixed across all demos
- README: 4-demo matrix added

### Recommended for

Users who want to understand MCR core concept in a minimal, self-contained file before exploring modular code.

### Known limitations

- README used SSH clone as default (external users without SSH key failed)
- pytest requirement not clearly documented
- Fixed in v0.9.3

---

## v0.9.0 — Event-sourced runtime snapshot

| Field | Value |
|-------|-------|
| **Version** | v0.9.0 |
| **Date** | 2025 |
| **Type** | Initial release / runtime snapshot |
| **Tag** | `v0.9.0` |

### What changed

- Event-sourced runtime kernel (WAL / reducer / replay verifier / event gate)
- Hermes Bridge v0.1 integration adapter
- 4 initial replay verification demos
- 5-hour autonomous loop run with G2 assertions
- Initial GitHub release

### Recommended for

Understanding the origin and architecture of the event-sourced kernel.

### Known limitations

- No regression tests
- No CI
- README onboarding incomplete
- Fixed in subsequent releases