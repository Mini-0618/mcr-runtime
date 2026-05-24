# Changelog

This changelog summarizes the public release history. Tags currently present in the repository: v0.9.0, v0.9.1, v0.9.2, v0.9.3.


## v0.9.7 — Metadata consistency hotfix

- Synced pyproject.toml version with release tag (was 0.9.5, now 0.9.7)
- Ensured wheel filename reports 0.9.7
- Preserved v0.9.6 build/CI hardening behavior
- No runtime logic changes

## v0.9.6 — Build and CI hardening

- Added GitHub Actions Python 3.10/3.11/3.12 matrix
- Added scripts/build_check.sh for wheel verification
- Added docs/PACKAGING.md for install instructions
- Added LICENSE (MIT)
- Updated .gitignore (dist/, build/, .venv/, .pytest_cache/)
- Updated verify_all.sh to v0.9.6 header
- No runtime logic changes

## v0.9.3 — External onboarding hotfix

- README Quickstart switched to HTTPS clone
- Added External User Quickstart
- Added Requirements section
- Added Troubleshooting section
- Clarified pytest is only required for full verification

## v0.9.2 — Regression-protected engineering artifact

- Added tests/
- Added scripts/verify_all.sh
- Added GitHub Actions workflow
- Added token leak regression test
- All demos + pytest pass

## v0.9.1 — Demo-ready release

- Added minimal_mcr.py
- Added demo matrix
- All four demos pass

## v0.9.0 — Event-sourced runtime snapshot

- Event-sourced runtime kernel
- WAL / reducer / replay verifier
- Hermes Bridge v0.1
- Initial replay verification demos
