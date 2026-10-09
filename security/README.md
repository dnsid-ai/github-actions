# Security workflows

Reusable GitHub Actions workflows for linting, testing and security scanning. A repo adds
one short workflow file that calls one of these, and gets the whole set of checks, plus a
single **Summary** check to make required.

| Workflow | For | Jobs |
|---|---|---|
| [`security-go.yml`](../.github/workflows/security-go.yml) | Go modules | lint (gofmt, go vet, golangci-lint) · test (race, coverage) · govulncheck · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-python.yml`](../.github/workflows/security-python.yml) | Python packages | lint (ruff, ruff format, mypy) + security lint (ruff S) · test (pytest + coverage) · pip-audit · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-typescript.yml`](../.github/workflows/security-typescript.yml) | npm / pnpm projects | lint, format, typecheck · test · osv-scanner + install-script check · CodeQL · Semgrep · gitleaks · Trivy · zizmor · dependency review · SBOM · Sonar |
| [`security-iac.yml`](../.github/workflows/security-iac.yml) | Terraform, Kubernetes, shell | tflint · kube-linter + conftest (OPA/Rego) · shellcheck · Semgrep · gitleaks · Trivy · zizmor |
| [`security-container.yml`](../.github/workflows/security-container.yml) | Dockerfiles | build locally (no push) · Trivy image scan · SBOM of the image |
| [`security-dast.yml`](../.github/workflows/security-dast.yml) | A running site | OWASP ZAP baseline (+ optional API scan) · Nuclei |

Every workflow ends in a **Summary** job, which:

- fails if any job failed;
- fails if a scanner job "succeeded" without writing a report (a gate that is green over nothing);
- writes one table of results and findings to the run page;
- publishes every report, bundled, as the `<prefix>.sonar-reports` artifact.

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
