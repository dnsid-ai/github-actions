# github-actions

Reusable GitHub Actions workflows, grouped by area. Nothing in here is specific to one
organization: fork or copy it into any org and call it from that org's repos.

| Area | What it is | Docs |
|---|---|---|
| [`security/`](security/) | Lint, test and security scanning for Go, Python, TypeScript, IaC, containers and live sites (DAST) | [security/README.md](security/README.md) |

Calling one from another repo:

```yaml
jobs:
  go:
    uses: <org>/github-actions/.github/workflows/security-go.yml@<SHA> # v1.0.0
    permissions:
      contents: read # check out the code
      security-events: write # upload SARIF to code scanning
      actions: read # code scanning reads run metadata on private repos
```

Pin the commit SHA of a release, not a branch or tag. Copy-in callers are in each area's
`templates/`.

## Layout

GitHub loads workflows only from `.github/workflows/` itself, never from a subdirectory.
So each area keeps its sources in its own folder, and the callable files are generated
into `.github/workflows/` with the area as a filename prefix:

```
<area>/src/<name>.yml          ->  .github/workflows/<area>-<name>.yml
<area>/src/partials/*.yml      shared jobs and steps, spliced in by `# @include <file>`
<area>/templates/              files for calling repos to copy
<area>/tests/                  fixtures for the area's self-test
.github/workflows/<area>-self-test.yml   runs the area's workflows against its fixtures
```

Never edit a generated `.github/workflows/<area>-*.yml` by hand. Edit `<area>/src/` and run:

```bash
python3 scripts/build.py          # regenerate
python3 scripts/build.py --check  # what CI runs: fails if anything is stale
```

## Adding an area

To add an area (say `release/`):

1. Create `release/src/` and add workflows there.
2. Run `python3 scripts/build.py`.
3. Add a `release/README.md` and a row to the table above.

An area can also skip `src/` and put hand-written workflows straight into
`.github/workflows/release-*.yml`. Use `src/` once several workflows share jobs.

Every workflow in the repo, generated or not, must pass `lint.yml`: the generated files
must be up to date, and actionlint (which includes shellcheck) and zizmor must be clean.

## Access

If this repo is private, other repos can call it only when both of these hold:

- An admin has set Settings → Actions → General → Access to "Accessible from repositories
  in the organization".
- The calling repo is itself **private** and in the same organization. Public repos can
  never call a private repo's workflows.

To share it across several organizations, or with public repos, keep a copy in each org
or publish a public copy.
