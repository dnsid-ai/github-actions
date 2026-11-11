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
- fails if a required scan was skipped, or if selection failed; intentional skips include a reason;
- writes one table of results and findings to the run page;
- publishes every report, bundled, as the `<prefix>.sonar-reports` artifact.

### When the scans run

Go, Python, TypeScript, IaC and container workflows select scans on **every PR
update**, using the complete merge-base-to-PR-head diff, including deletions and
both sides of renames. The selector is embedded in the pinned reusable workflow;
it never executes selector code from the caller's checkout.

Selection is deliberately conservative:

- **Lint/tests and fast IaC checks** keep their existing every-push behaviour and
  caller switches. Python's ruff `S` security lint still runs with `lint: false`.
- **gitleaks** scans full reachable history on every PR update, including docs-only
  changes, unless the caller explicitly disables it.
- **Documentation-only PRs** can skip project scans. Only Markdown, reStructuredText
  and text under `docs/`, plus conventional root documentation files (README,
  CHANGELOG, CONTRIBUTING, LICENSE, AUTHORS, CODE_OF_CONDUCT, SECURITY), qualify.
  Other paths, including unknown file types, select project scans. This assumes
  those documentation files are not executable/build inputs; callers that use them
  that way should set `scan-every-push: true`.
- **Configuration and workflows** select project scans and workflow audits.
  Ordinary source changes skip zizmor and Actions-only CodeQL. Custom IaC CodeQL
  language sets conservatively follow project changes.
- **Dependencies:** Go's reachability-sensitive govulncheck and Python's potentially
  dynamic package metadata follow project changes. TypeScript's lockfile-only
  osv-scanner skips source-only changes; lockfile/manifests/configuration changes
  select it. SBOM and dependency review conservatively follow project changes.
- **Custom Semgrep rules**, local or non-default registry rulesets, run on every
  PR update, including their rule tests: their input scope cannot be inferred.
- **Container scans** consider every file in the build context (including docs),
  the Dockerfile and configuration. Unknown/remote contexts always scan. Files
  outside the context and Dockerfile can skip the image job.
- **Missing or empty diffs** select all enabled scans. Selection failures, missing
  decisions, required-but-skipped scans and successful scanners without reports
  fail Summary. Intentional skips publish their reasons.

Non-PR events (push, schedule, dispatch) run all enabled scans. Keep a default-branch
push trigger and add a regular scheduled full scan in callers: vulnerability feeds
and remote rules change even when source files do not. This library does not add
caller schedules automatically.

`scan-every-push: true` bypasses selection and forces all enabled scans. The
`rerun-security` PR label does the same on the next triggered run (push/reopen);
adding the label alone does not trigger the default caller templates.

DAST keeps its existing event gate and is intended for dispatch/schedule, not PR
path selection. No scan results are reused across commits.

### Dependency caching

Go already caches module downloads and build products through setup-go. Node
caches the npm/pnpm download store using the project's lockfile; Python caches pip
downloads using package metadata/requirements and uv's cache using uv.lock and
pyproject.toml. The setup actions scope caches to their runtime/platform as
applicable. Installs still run with the existing locked/frozen and lifecycle-script
restrictions; node_modules, project virtualenvs and scanner pass/fail results are
not cached. Scanner tools, vulnerability databases and Docker layers are outside
this change.

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
this suite, turn `codeql` on and the other jobs off:

```yaml
with:
  codeql: true          # scans codeql-languages (default: actions)
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

### CodeQL on Actions workflows in a Go/Python/TypeScript repo

The language workflows scan their own language with `codeql`. To also scan the
repo's GitHub Actions workflows — and retire a per-repo `codeql.yml` or CodeQL
default setup that covered `actions` — set `codeql-actions: true`:

```yaml
with:
  codeql-actions: true   # second CodeQL scan over .github/workflows, from repo root
```

It's a **separate job** (`SAST (CodeQL: actions)`) rather than another language
in the `codeql` job because `actions` only supports build-mode `none`, which
can't share one database with a compiled language's build (Go autobuild), and
because it scans from the repo root — the `.github/workflows` a scan rooted at a
`working-directory` subdir would miss. Then remove the repo's own CodeQL for
Actions so it is not scanned twice.

Its results reach the **Security tab** only where this upload is accepted — the
same rule as the `codeql` job (step 5 above): default setup rejects advanced-setup
uploads **for the whole repo, not per language**. So `codeql-actions` replaces
default setup for Actions only once default setup is switched **off for the repo**
(or the repo is on advanced setup). While default setup stays on for the repo's
own language, turn `codeql-actions` on if you like, but its results stay in the
reports artifact until default setup is disabled — don't disable only the `actions`
language and expect the advanced upload to land.

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
