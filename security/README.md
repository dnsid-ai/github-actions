# Security workflows

Reusable GitHub Actions workflows for linting, testing and security scanning. A repo adds
one short workflow file that calls one of these, and gets the whole set of checks, plus a
single **Summary** check to make required.

| Workflow | For | Jobs |
|---|---|---|
| [`security-go.yml`](../.github/workflows/security-go.yml) | Go modules | lint (gofmt, go vet, golangci-lint) · test (race, coverage) · govulncheck · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-python.yml`](../.github/workflows/security-python.yml) | Python packages | lint (ruff, ruff format, mypy) + security lint (ruff S) · test (pytest + coverage) · pip-audit · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-typescript.yml`](../.github/workflows/security-typescript.yml) | npm / pnpm projects | lint, format, typecheck · test · osv-scanner + install-script check · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-iac.yml`](../.github/workflows/security-iac.yml) | Terraform, Kubernetes, shell | tflint · kube-linter + conftest (OPA/Rego) · shellcheck · Semgrep · gitleaks · Trivy · zizmor · CodeQL (actions) |
| [`security-container.yml`](../.github/workflows/security-container.yml) | Dockerfiles | build locally (no push) · Trivy image scan · SBOM of the image |
| [`security-dast.yml`](../.github/workflows/security-dast.yml) | A running site | OWASP ZAP baseline (+ optional API scan) · Nuclei |

Every workflow ends in a **Summary** job, which:

- fails if any job failed;
- fails if a scanner job "succeeded" without writing a report (a gate that is green over nothing);
- **fails on a push that wasn't scanned** — the security scans don't re-run on every push (see below), so this keeps an unscanned commit from merging green;
- writes one table of results and findings to the run page;
- publishes every report, bundled, as the `<prefix>.sonar-reports` artifact.

### When the scans run

The scan jobs run when a PR is **opened or reopened** (and on any non-`pull_request`
trigger the caller uses, e.g. push to a branch or schedule). They **do not re-run
on every push to an open PR** — that would re-run CodeQL, Trivy, Semgrep and the
rest on each commit for no added signal.

What keeps running on every push depends on the workflow:

- **go / python / typescript** — `lint` and `test` run on every push (unless
  turned off with `lint: false` / `test: false`); the scanners (dependency
  checks, CodeQL, Semgrep, gitleaks, Trivy, zizmor, SBOM, dependency review,
  Sonar) are throttled. In Python the ruff `S` security lint runs regardless of
  `lint`.
- **iac** — the fast checks run on every push: `tflint`, `shellcheck`, and
  `kube-linter` + conftest (including the `*_test.rego` policy tests); the
  scanners shared with the other workflows (Semgrep, gitleaks, Trivy, zizmor,
  CodeQL, Sonar) are throttled.
- **container** — scan-only. Its one job builds the image and scans it, so on a
  `synchronize` push it skips entirely and re-runs on open/reopen (or with the
  label). There is no separate build-only check.
- **dast** — triggered on dispatch/schedule, so none of this applies.

Custom Semgrep rules run inside the (throttled) Semgrep job, so their
`tests/semgrep/` tests run on open/reopen, not on every push.

So the gate stays honest, the **Summary** check **fails on a push that wasn't
scanned** (it does not go green over an unscanned commit). A commit cannot be
merged until it has been scanned.

To scan the current commit — e.g. before merging after a round of pushes — add
the **`rerun-security`** label to the PR and push again (or reopen the PR); the
whole suite runs and Summary goes green. Removing the label returns to the
open-only behaviour.

A caller that genuinely wants every commit scanned can set **`scan-every-push:
true`**. Then the scans run on every push and the Summary never fails for an
unscanned commit. This is for callers whose whole purpose is to run the scanners
— this repo's own `security-self-test` sets it — not for ordinary consumers,
who get cheaper, open-only scanning by leaving it at its `false` default.

**Heads-up for Dependabot and "Update branch".** Both push to the PR head, which
fires `synchronize`. On a PR without the `rerun-security` label the Summary check
then goes red until the current commit is scanned — add the label and push again,
or reopen the PR. In a repo that requires branches to be up to date, or that
auto-merges Dependabot PRs, expect a base-branch update to stall the PR this way;
set `scan-every-push: true` if that trade-off isn't worth it for your repo.

## What the tools are

| Kind | Plain English | Tools here |
|---|---|---|
| **Lint** | Style and correctness mistakes in your own code | golangci-lint, go vet, ruff, mypy, your ESLint/tsc scripts, tflint, shellcheck |
| **SAST** (static application security testing) | Reads source code for insecure patterns: injection, weak crypto, unsafe calls | CodeQL, Semgrep, ruff `S` (bandit rules) |
| **SCA** (software composition analysis) | Checks your third-party libraries against lists of known vulnerabilities | govulncheck, pip-audit, osv-scanner, Trivy, dependency review |
| **Secret scanning** | Finds passwords and keys committed to git, including ones later deleted | gitleaks (full history), Trivy (current tree) |
| **IaC / posture** | Risky settings in Terraform, Kubernetes and Dockerfiles | Trivy (misconfig), kube-linter, conftest, tflint |
| **Workflow security** | Unsafe GitHub Actions: unpinned actions, script injection, over-broad tokens | zizmor |
| **Image scanning** | Vulnerable OS packages and secrets inside a built container image | Trivy (image) |
| **SBOM** | An ingredient list of everything in a build | Syft (via anchore/sbom-action) |
| **DAST** (dynamic application security testing) | Attacks the running site from outside, the way an attacker would | OWASP ZAP, Nuclei |

**CodeQL vs Semgrep.** Both are SAST. CodeQL follows data from where it enters to where
it's used; Semgrep matches patterns and makes repo-specific rules easy to write. They
overlap, so either can be switched off with `codeql: false` or `semgrep: false`.

## Adopting it in a repo

1. **Copy a caller** from [`templates/callers/`](templates/callers/) into the repo's
   `.github/workflows/`, and replace `<SHA>` with a release commit of this repo.
2. **Grant the permissions shown in the template**: `contents: read`,
   `security-events: write`, `actions: read`, and `pull-requests: write`. A called
   workflow can never have more than its caller grants, and GitHub rejects the whole
   run if it asks for more. `pull-requests: write` is **required**: the
   Summary job declares it to post its result as a single sticky PR comment, and a
   reusable workflow whose called job requests a permission the caller did not grant
   fails to start. Grant all four.
3. **Start warn-only.** `enforce-security: false` (the default) reports every finding
   but fails only on lint, test and tool errors. Triage the first run's findings into
   the tools' ignore files (below), then set `enforce-security: true`.
4. **Make `<job> / Summary` a required status check** on `main`. That one check covers
   every job. A scanner that isn't required can't block anything.
5. **CodeQL "default setup".** If it's turned on for the repo, either set
   `codeql: false`, or have an admin switch the repo to advanced setup. Otherwise the
   upload is rejected. The job still passes, and its results stay in the artifact.
6. **Don't run what the repo already runs.** Every job is on by default, so a repo
   adopting the suite fresh gets the whole set. If the repo's own CI already lints or
   tests, switch off the duplicate here with `lint: false` and/or `test: false` (Go,
   Python and TypeScript), the same way `codeql: false` hands CodeQL to default setup.
   Turn off only the jobs another workflow already owns — and note `test: false` also
   drops this suite's coverage report, so keep coverage running somewhere. In Python,
   `lint: false` drops the style checks only; the ruff `S` (bandit) security lint keeps
   running, since it is SAST rather than a duplicate of your own linter.

### CodeQL on an infra/deploy repo (CodeQL-only)

`security-iac.yml` has a `codeql` job (on by default) that scans the
`codeql-languages` you give it — `actions` by default, i.e. the repo's GitHub
workflow files (Terraform/HCL has no CodeQL analyzer). To replace a repo's
per-repo CodeQL (a `codeql.yml` workflow or default setup) with one scan owned by
this suite, keep `codeql` on and turn the other jobs off:

```yaml
with:
  codeql: true
  upload-sarif: true     # send results to the Security tab (needs code scanning)
  tflint: false
  shellcheck: false
  semgrep: false
  gitleaks: false
  trivy: false
  workflow-audit: false
```

Then remove the repo's own CodeQL so it is not scanned twice. Leave `upload-sarif`
at its default (`true`) only where code scanning is available (public repos, or
private repos with GitHub Advanced Security); otherwise results stay in the
reports artifact.

### Baselines: where each tool reads its ignores

All paths are at the repo root (or in `working-directory` where noted):

- `.gitleaks.toml`, `.gitleaksignore`
- `.trivyignore.yaml` (or `.trivyignore`)
- `.semgrepignore`
- `.semgrep/`: your own Semgrep rules. `tests/semgrep/` holds their tests, which always block.
- `osv-scanner.toml`
- `.kube-linter.yaml`
- `policy/*.rego`: conftest policies. `*_test.rego` holds their tests, which always block.
- `.tflint.hcl`: passed as an absolute path, so `--recursive` can't silently drop your plugins.

### SonarQube

Without a SonarQube server, leave `sonar-host-url` empty. Every run still
writes the `<prefix>.sonar-reports` artifact: coverage, golangci-lint, ruff, ESLint and
every SARIF. Once you have a server:

1. Set `sonar-host-url`.
2. Pass the `SONAR_TOKEN` secret.
3. Add [`templates/sonar-project.properties`](templates/sonar-project.properties) to the repo.

The Sonar job then imports those same reports.

### DeepSource

DeepSource is a GitHub App configured by a `.deepsource.toml` file, so no workflow can
run it. Templates and steps are in [`templates/deepsource/`](templates/deepsource/).

## Who can call these workflows

If this repo is **private**, an admin must set Settings → Actions → General → Access to
"Accessible from repositories in the organization". GitHub then allows:

- ✅ private repos in the same organization.
- ❌ **public** repos anywhere: GitHub never lets a public repo use a private repo's workflows.
- ❌ repos in other organizations.

To serve public repos, or several organizations, publish a **public** copy of this repo.
Any repo can call a public repo's workflows.

## Not covered

- **Signing images, and blocking unsigned ones at deploy time.** Only the SBOM is
  produced. Signing needs registry credentials and a release flow of its own.
- **Authenticated DAST.** `security-dast.yml` scans as an anonymous visitor. Scanning
  behind a login needs per-app credentials and test accounts.
- **Who triages findings, and a SECURITY.md.** These are process decisions, not workflows.

## Maintaining

- `.github/workflows/security-*.yml` (except `security-self-test.yml`) are
  **generated**. Edit `security/src/` and run `python3 scripts/build.py` from the repo root;
  CI fails if you forget. Jobs every workflow shares live once in `security/src/partials/`.
- Every action is pinned to a commit SHA. Every downloaded tool is pinned to a version
  and a SHA-256 (in `security/src/partials/install-*.yml`). Update both together.
- `security-self-test.yml` runs each workflow against `tests/fixtures/`, and each fixture plants a
  known finding (a canary). The self-test fails if any scanner misses its canary, or
  if a warn-only workflow goes red because of findings.
- GitHub's `$/` syntax (July 2026) lets a reusable workflow reference files in its own
  repo, which could replace the `security/src/partials/` generator with composite actions. Not
  used yet, because actionlint doesn't accept it (see `../.github/zizmor.yml`).
- Release by tagging (`v1.0.0`) and telling callers the tag's commit SHA.

Known limits:

- Linux x64 runners only.
- Python tools (Semgrep, zizmor, pip-audit) are pinned by version, not by hash.
- CodeQL for Go uses `autobuild`, which builds only the module at `working-directory`.
