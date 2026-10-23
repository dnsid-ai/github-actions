#!/usr/bin/env python3
# Assert the scan-gate invariants across the generated security-*.yml workflows:
#
#   - every scanner job is gated with the exact `scan-every-push` gate;
#   - the jobs that must always give feedback on a push stay UNGATED
#     (go/python/typescript `lint` and `test`; iac's `terraform`, `kubernetes`
#     and `shell` — tflint, kube-linter + conftest, shellcheck);
#   - the Summary "Require a scan" step condition is the gate's exact boolean
#     negation.
#
# The self-test's own runs can't catch a mistake here: every caller sets
# `scan-every-push: true`, so the skip path, the require-scan failure and the
# ungated-lint promise are never exercised at runtime. This static check is the
# guard — a dropped "!" (which would let an unscanned commit merge green) or a
# re-gated lint job fails it.
import re
import sys
import pathlib

GATE = (
    "inputs.scan-every-push || github.event_name != 'pull_request' || "
    "github.event.action != 'synchronize' || "
    "contains(github.event.pull_request.labels.*.name, 'rerun-security')"
)
REQ = (
    "!inputs.scan-every-push && github.event_name == 'pull_request' && "
    "github.event.action == 'synchronize' && "
    "!contains(github.event.pull_request.labels.*.name, 'rerun-security')"
)

# Jobs that must stay ungated (run on every push), per workflow. Everything else
# (bar the always()-gated `summary`) is a scanner and must carry the gate.
ALWAYS_RUN = {
    "go": {"lint", "test"},
    "python": {"lint", "test"},
    "typescript": {"lint", "test"},
    "iac": {"terraform", "kubernetes", "shell"},
    "container": set(),
    "dast": set(),
}
WF_DIR = pathlib.Path(".github/workflows")


def job_ifs(text):
    """Top-level job name -> its job-level `if:` string ("" if the job has none)."""
    out, cur, in_jobs = {}, None, False
    for ln in text.split("\n"):
        if re.match(r"^jobs:\s*$", ln):
            in_jobs = True
            continue
        if not in_jobs:
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", ln)
        if m:
            cur = m.group(1)
            out.setdefault(cur, "")
            continue
        m = re.match(r"^    if:\s*(.*)$", ln)
        if m and cur is not None and out.get(cur) == "":
            out[cur] = m.group(1)
    return out


def main():
    fail = 0

    def err(msg):
        nonlocal fail
        print(f"::error::{msg}")
        fail = 1

    for w, always in ALWAYS_RUN.items():
        f = WF_DIR / f"security-{w}.yml"
        text = f.read_text()
        jobs = job_ifs(text)
        if not jobs:
            err(f"{f}: no jobs parsed")
            continue
        for name, cond in jobs.items():
            if name == "summary":
                continue  # always() — neither a scanner nor an always-run feedback job
            gated = "scan-every-push" in cond
            if name in always:
                if gated:
                    err(f"{f}: job '{name}' must run on every push but is gated: {cond}")
            elif not gated:
                err(f"{f}: scanner job '{name}' is not gated: {cond or '<no if>'}")
            if gated and GATE not in cond:
                err(f"{f}: job '{name}' is gated but not with the exact gate: {cond}")
        if REQ not in text:
            err(f"{f}: Summary 'Require a scan' condition is not the gate's exact negation")

    print("gate invariants: OK" if not fail else "gate invariants: FAILED")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
