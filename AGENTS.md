# AGENTS.md — shared security/CI workflows

Reusable GitHub Actions workflows (`security-go`, `security-python`, `security-typescript`, `security-iac`, `security-container`, `security-dast`) that caller repos invoke and pin by SHA.

## ⚠️ This repo has an identical twin — keep them in sync BOTH WAYS

There are **two copies** of this repo, one per GitHub org, and they are meant to be **byte-identical**:

- **`dnsid-ai/github-actions`** — called by the SDK repos (`dnsid-ai/dnsid-go`, `dnsid-ts`, `dnsid-py`, `agent-sdk-plugin`).
- **`Identity-Digital/github-actions`** — called by `Identity-Digital/dnsid` and `dnsid-deploy`.

**Any change to `security/src/**` (or anything that regenerates `.github/workflows/security-*.yml`) MUST be applied to BOTH repos and released under the SAME version tag.** Editing only one causes silent drift that is invisible to callers (they pin by SHA), and a fix or enhancement then reaches only half the fleet.

This rule exists because it already broke twice (found 2026-11-05): the gosec `-quiet` SARIF fix shipped to `dnsid-ai` but not `Identity-Digital`, and `Identity-Digital`'s Go dependency/build-caching enhancement (`setup-go` `cache: true`) was never mirrored back to `dnsid-ai`. Each repo had a change the other lacked.

When you change one, in the same unit of work: make the identical `security/src` edit in the other, regenerate, open a PR on each, and after both merge cut the **same** new version tag (`vX.Y.Z`) on both. Then bump the affected callers' pins to it. Before finishing, confirm the two repos are identical:

```sh
git diff --no-index <other-repo>/security/src           # expect empty
git diff --no-index <other-repo>/.github/workflows       # expect empty
```

## Editing workflows

- **Do not edit `.github/workflows/security-*.yml` directly** — they are GENERATED. Edit `security/src/**` (jobs in `security/src/<lang>.yml`, shared steps in `security/src/partials/`), then regenerate:
  ```sh
  python3 scripts/build.py
  ```
  Commit the source and the regenerated workflows together; a "generated files are up to date" CI check fails otherwise.
- Validate before pushing: `actionlint .github/workflows/security-*.yml` (runs shellcheck on embedded scripts) and `python3 scripts/check-gate-invariants.py`.

## Callers pin by SHA

Callers reference `…/security-<lang>.yml@<40-char-sha> # vX.Y.Z` — the SHA governs; the tag comment is cosmetic, and Dependabot bumps the SHA. A fix propagates only when each caller's pin is bumped, so: land in both twin repos → tag both → bump callers. Moving a tag does **not** reach SHA-pinned callers.

## Gotcha: gosec `-quiet` suppresses the SARIF

`gosec -quiet` means "only output when issues are found", so a **zero-findings** scan writes **no** `-out` SARIF. Never pass `-quiet` to a gosec invocation whose `-out` is consumed downstream; a report step must tolerate zero findings.
