#!/usr/bin/env python3
"""Assert generated jobs use selection, retain fast feedback and fail closed."""
import pathlib
import re
import sys

ALWAYS_RUN = {
    "go": {"lint", "test"},
    "python": {"lint", "test"},
    "typescript": {"lint", "test"},
    "iac": {"terraform", "kubernetes", "shell"},
    "container": set(),
}


def job_blocks(text):
    jobs = text.split("\njobs:\n", 1)[1]
    matches = list(re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.M))
    return {m[1]: jobs[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(jobs)]
            for i, m in enumerate(matches)}


def main():
    errors = []
    for kind, fast in ALWAYS_RUN.items():
        path = pathlib.Path(f".github/workflows/security-{kind}.yml")
        text = path.read_text()
        jobs = job_blocks(text)
        if "selection" not in jobs:
            errors.append(f"{path}: missing selection job")
        for job, block in jobs.items():
            cond = re.search(r"^    if: (.*)$", block, re.M)
            cond = cond[1] if cond else ""
            if job == "selection":
                if cond:
                    errors.append(f"{path}: selection must always run")
            elif job == "summary":
                if cond != "always()" or "needs: [selection," not in block:
                    errors.append(f"{path}: Summary must always run and depend on selection")
            elif job in fast:
                if "selection" in cond or "scan-every-push" in cond:
                    errors.append(f"{path}: {job} must retain every-push feedback")
            elif f"fromJSON(needs.selection.outputs.plan)['{job}'].run" not in cond or not re.search(r"^    needs: (selection|\[selection,.*\])$", block, re.M):
                errors.append(f"{path}: {job} must use its own selection decision")
        for guard in ('skipped, but REQUIRED by selection', 'No selection decision for $job',
                      'Check selection did not complete successfully', 'success, but NO REPORT'):
            if guard not in jobs["summary"]:
                errors.append(f"{path}: missing gate guard: {guard}")
        if 'fetch-depth: 0' not in jobs["selection"] or '--no-renames' not in jobs["selection"]:
            errors.append(f"{path}: selection needs a complete merge-base diff including renames")
    # DAST has no repository-path selector: preserve its existing event gate.
    dast = pathlib.Path(".github/workflows/security-dast.yml").read_text()
    for name in ("zap", "nuclei"):
        if "inputs.scan-every-push || github.event_name != 'pull_request'" not in job_blocks(dast)[name]:
            errors.append(f"DAST: {name} lost its event gate")
    if "fromJSON(toJSON(needs)).selection.result == '' && !inputs.scan-every-push" not in dast:
        errors.append("DAST: missing unscanned-commit guard")
    for error in errors:
        print(f"::error::{error}")
    print("gate invariants: FAILED" if errors else "gate invariants: OK")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
