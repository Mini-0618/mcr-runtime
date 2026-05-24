# Releases

This page provides a human-readable release guide for users who are not familiar with GitHub Releases.


## v0.9.7

- Version: v0.9.7
- Date: tagged if available in Git
- Type: Metadata consistency hotfix
- What changed:
  - Synced pyproject.toml version (was 0.9.5, now 0.9.7)
  - No runtime logic changes
  - Preserved all v0.9.6 build/CI hardening behavior
- Recommended for users? Yes — use this for clean version metadata.

## v0.9.6

- Version: v0.9.6 (metadata version was 0.9.5 — use v0.9.7 instead)
- Date: tagged if available in Git
- Type: Build and CI hardening
- What changed:
  - GitHub Actions Python 3.10/3.11/3.12 matrix
  - scripts/build_check.sh for wheel verification
  - docs/PACKAGING.md
  - LICENSE (MIT)
  - Updated .gitignore
- Recommended for users? Use v0.9.7 instead (v0.9.6 wheel metadata was inconsistent).

## v0.9.3

- Version: v0.9.3
- Date: tagged if available in Git
- Type: External onboarding hotfix
- What changed:
  - HTTPS clone path for external users
  - clearer quickstart
  - requirements and troubleshooting documentation
  - clarification that pytest is only needed for full verification
- Recommended for users? Yes. This is the recommended entry point for external users.
- Known limitations:
  - research artifact, not production-ready
  - no real external LLM required or integrated by default
  - focused on replay verification, not full agent orchestration

## v0.9.2

- Version: v0.9.2
- Date: tagged if available in Git
- Type: Regression-protected engineering artifact
- What changed:
  - tests added
  - full verification script added
  - GitHub Actions workflow added
  - token leak regression test added
- Recommended for users? Useful for reviewing test coverage and regression protection.
- Known limitations:
  - developer-oriented release
  - documentation less complete than v0.9.3

## v0.9.1

- Version: v0.9.1
- Date: tagged if available in Git
- Type: Demo-ready release
- What changed:
  - minimal demo added
  - demo matrix added
  - four demos pass
- Recommended for users? Useful for reviewing the demo path.
- Known limitations:
  - less onboarding documentation than v0.9.3

## v0.9.0

- Version: v0.9.0
- Date: tagged if available in Git
- Type: Initial runtime snapshot
- What changed:
  - event-sourced runtime kernel
  - WAL / reducer / replay verifier
  - Hermes Bridge v0.1
  - initial replay verification demos
- Recommended for users? Historical baseline only.
- Known limitations:
  - early snapshot
  - not intended as the current external entry point
