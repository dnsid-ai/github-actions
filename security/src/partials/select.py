"""Conservative PR selection; embedded into workflows, never loaded from caller code."""
import json
import os
from pathlib import PurePosixPath
import subprocess


def changed_paths(base, head, cwd=None):
    try:
        # --no-renames retains both the deleted and added path of a rename.
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}", "--"],
            cwd=cwd, stderr=subprocess.PIPE,
        )
        return diff.decode("utf-8").rstrip("\0").split("\0") if diff else []
    except (subprocess.CalledProcessError, UnicodeError, OSError):
        return None


def documentation(path):
    p = PurePosixPath(path)
    return (
        p.suffix.lower() in {".md", ".rst", ".txt"}
        and (path.startswith("docs/") or (len(p.parts) == 1 and p.stem.upper() in {
            "README", "CHANGELOG", "CONTRIBUTING", "LICENSE", "AUTHORS", "CODE_OF_CONDUCT", "SECURITY",
        }))
    )


def configuration(path):
    p = PurePosixPath(path)
    # Configuration and local actions can change scanner inputs or execution.
    return (path.startswith(".github/") or p.name.startswith(".")
            or p.name in {"action.yml", "action.yaml", "go.mod", "go.sum", "go.work", "go.work.sum", "Pipfile"}
            or "requirements" in p.name.lower()
            or p.suffix in {".toml", ".json", ".yaml", ".yml", ".ini", ".cfg", ".lock"})


def plan(kind, inputs, paths):
    full = paths is None or not paths or inputs.get("scan-every-push", False)
    config = full or any(configuration(p) for p in paths)
    project = full or config or any(not documentation(p) for p in paths)
    enabled = {
        "lint": kind == "python" or inputs.get("lint", True),
        "test": inputs.get("test", True),
        "deps": True,
        "gosec": True,
        "codeql": inputs.get("codeql", True),
        "codeql-actions": inputs.get("codeql-actions", False),
        "semgrep": inputs.get("semgrep", True),
        "secrets": inputs.get("gitleaks", True),
        "trivy": inputs.get("trivy", True),
        "workflow-audit": inputs.get("workflow-audit", True),
        "dependency-review": inputs.get("dependency-review", True),
        "sbom": inputs.get("sbom", False),
        "sonar": bool(inputs.get("sonar-host-url", "")),
        "terraform": inputs.get("tflint", True),
        "kubernetes": bool(inputs.get("manifests-command", "") or inputs.get("manifests-path", "")),
        "shell": inputs.get("shellcheck", True),
        "image": True,
    }
    affected = {job: project for job in enabled}
    for job in ("lint", "test", "terraform", "kubernetes", "shell", "secrets"):
        affected[job] = True  # Preserve fast feedback and full-history secret coverage.
    affected["workflow-audit"] = affected["codeql-actions"] = config
    if kind == "typescript":
        # osv-scanner consumes only the lockfile; source changes cannot alter its packages.
        affected["deps"] = config
    if kind == "iac":
        affected["codeql"] = config if inputs.get("codeql-languages", "actions") == "actions" else project
    if kind == "container":
        context = PurePosixPath(inputs.get("context", "."))
        dockerfile = PurePosixPath(inputs.get("dockerfile", "Dockerfile"))
        # Remote/out-of-tree contexts cannot be safely classified from a repo diff.
        unknown_context = ":" in str(context) or context.is_absolute() or ".." in context.parts
        affected["image"] = full or config or unknown_context or any(
            PurePosixPath(p) == dockerfile or PurePosixPath(p).is_relative_to(context) for p in paths
        )
    jobs = {
        "go": "lint test deps gosec codeql codeql-actions semgrep secrets trivy workflow-audit dependency-review sbom sonar",
        "python": "lint test deps codeql codeql-actions semgrep secrets trivy workflow-audit dependency-review sbom sonar",
        "typescript": "lint test deps codeql codeql-actions semgrep secrets trivy workflow-audit dependency-review sbom sonar",
        "iac": "terraform kubernetes shell codeql semgrep secrets trivy workflow-audit",
        "container": "image",
    }[kind].split()
    result = {}
    for job in jobs:
        run = enabled[job] and affected[job]
        reason = ("disabled by caller" if not enabled[job] else
                  "full scan (forced, non-PR, empty or unavailable diff)" if full else
                  "required for changed inputs or every-push coverage" if run else
                  "not applicable to changed paths")
        result[job] = {"run": run, "reason": reason}
    return result


def main():
    inputs = json.loads(os.environ["INPUTS"])
    paths = None
    if os.environ["EVENT"] == "pull_request" and os.environ["FORCE"] != "true":
        paths = changed_paths(os.environ["BASE"], os.environ["HEAD"])
    selected = plan(os.environ["KIND"], inputs, paths)
    if os.environ["KIND"] == "container":
        context = inputs.get("context", ".")
        if os.path.realpath(context) != os.path.abspath(context):
            selected["image"] = {"run": True, "reason": "symlinked build context has unknown input scope"}
    # Custom rules may deliberately scan documentation; never infer their scope.
    if "semgrep" in selected and inputs.get("semgrep", True):
        wd = inputs.get("working-directory", ".")
        rules = inputs.get("semgrep-rules", "")
        defaults = {
            "go": "p/golang p/gosec p/secrets",
            "python": "p/python p/secrets",
            "typescript": "p/typescript p/javascript p/nodejsscan p/secrets",
            "iac": "p/terraform p/kubernetes p/dockerfile p/secrets",
        }
        if os.path.isdir(os.path.join(wd, ".semgrep")) or rules != defaults[os.environ["KIND"]]:
            selected["semgrep"] = {"run": True, "reason": "custom Semgrep rules have unknown input scope"}
    # Dependency review only exists on PRs, even during a full scan.
    if "dependency-review" in selected and os.environ["EVENT"] != "pull_request":
        selected["dependency-review"] = {"run": False, "reason": "not a pull request"}
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("plan=" + json.dumps(selected, separators=(",", ":")) + "\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write("### Scan selection\n\n")
        summary.write("Unavailable or empty diffs run conservatively; secrets retain full-history coverage.\n\n")
        summary.write("| Check | Run | Reason |\n|---|---|---|\n")
        for job, decision in selected.items():
            summary.write(f"| {job} | {decision['run']} | {decision['reason']} |\n")


if __name__ == "__main__":
    main()
