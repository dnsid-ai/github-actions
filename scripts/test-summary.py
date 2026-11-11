#!/usr/bin/env python3
"""Run the actual Summary shell against missing, failed and intentionally skipped scans."""
import json
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PARTIAL = (ROOT / "security/src/partials/summary-steps.yml").read_text()
BLOCK = PARTIAL.split("- name: Summarize\n", 1)[1].split("  run: |\n", 1)[1]
# Stop at the next YAML step; execute the shell exactly as Actions does.
SCRIPT = "\n".join(line[4:] if line.startswith("    ") else line
                   for line in BLOCK.split("\n# Post the same summary", 1)[0].splitlines())


class SummaryTests(unittest.TestCase):
    def run_summary(self, result="skipped", required=False, selection="success", plan=True):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, RUNNER_TEMP=directory, GITHUB_STEP_SUMMARY=directory + "/step.md",
                       GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="test/repo",
                       GITHUB_RUN_ID="1", PREFIX="test", ENFORCE="true", REQUIRED_REPORTS="codeql")
            needs = {"selection": {"result": selection}, "codeql": {"result": result}}
            env["NEEDS"] = json.dumps(needs)
            env["PLAN"] = json.dumps({"codeql": {"run": required, "reason": "not applicable"}} if plan else {})
            proc = subprocess.run(["bash", "-euo", "pipefail", "-c", SCRIPT], env=env,
                                  text=True, capture_output=True)
            report = pathlib.Path(directory, "step.md")
            return proc.returncode, proc.stdout + proc.stderr + (report.read_text() if report.exists() else "")

    def test_intentional_skip_passes(self):
        self.assertEqual(self.run_summary()[0], 0)

    def test_required_skip_fails(self):
        code, output = self.run_summary(required=True)
        self.assertNotEqual(code, 0)
        self.assertIn("REQUIRED by selection", output)

    def test_success_without_report_fails(self):
        code, output = self.run_summary(result="success", required=True)
        self.assertNotEqual(code, 0)
        self.assertIn("NO REPORT", output)

    def test_failed_cancelled_and_skipped_planner_fail(self):
        for state in ("failure", "cancelled", "skipped"):
            self.assertNotEqual(self.run_summary(selection=state)[0], 0, state)

    def test_missing_decisions_fail(self):
        code, output = self.run_summary(plan=False)
        self.assertNotEqual(code, 0)
        self.assertIn("No selection decision", output)

    def test_scanner_failure_or_cancellation_fails(self):
        for state in ("failure", "cancelled"):
            self.assertNotEqual(self.run_summary(result=state, required=True)[0], 0, state)


if __name__ == "__main__":
    unittest.main()
