#!/usr/bin/env python3
"""Exercise the exact selector embedded in the reusable workflows."""
import importlib.util
import json
import pathlib
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("selection", ROOT / "security/src/partials/select.py")
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class SelectionTests(unittest.TestCase):
    def plan(self, paths, kind="python", **inputs):
        return selection.plan(kind, inputs, paths)

    def test_docs_only_keep_secrets(self):
        p = self.plan(["docs/guide.md", "README.md"])
        self.assertTrue(p["secrets"]["run"])
        for job in ("deps", "codeql", "semgrep", "trivy", "workflow-audit"):
            self.assertFalse(p[job]["run"], job)

    def test_unknown_files_and_source_are_conservative(self):
        for path in ("src/main.py", "data/input.md", "build.sh", "uv.lock", "../odd", "docs/build.py"):
            p = self.plan([path])
            for job in ("deps", "codeql", "semgrep", "trivy"):
                self.assertTrue(p[job]["run"], (path, job))
            self.assertEqual(p["workflow-audit"]["run"], selection.configuration(path))

    def test_workflows_actions_and_configuration_force_scans(self):
        for path in (".github/workflows/ci.yml", ".github/actions/build/action.yml", "action.yml", ".semgrepignore", "pkg/.trivyignore", "pyproject.toml", ".github/zizmor.yml"):
            p = self.plan([path], **{"codeql-actions": True})
            self.assertTrue(p["deps"]["run"], path)
            self.assertTrue(p["workflow-audit"]["run"], path)
            self.assertTrue(p["codeql-actions"]["run"], path)

    def test_disabled_jobs_stay_disabled(self):
        p = self.plan(None, semgrep=False, gitleaks=False, codeql=False, test=False, lint=False)
        for job in ("semgrep", "secrets", "codeql", "test"):
            self.assertFalse(p[job]["run"])
        self.assertTrue(p["lint"]["run"])  # Python's security lint is mandatory.
        self.assertFalse(self.plan(None, kind="go", lint=False)["lint"]["run"])

    def test_full_scan_fallback_and_force(self):
        for paths in (None, []):
            p = self.plan(paths)
            self.assertTrue(p["deps"]["run"])
            self.assertTrue(p["workflow-audit"]["run"])
        p = self.plan(["README.md"], **{"scan-every-push": True})
        self.assertTrue(p["deps"]["run"])

    def test_iac_and_custom_rendering(self):
        p = self.plan(["README.md"], kind="iac")
        # Fast IaC checks keep their existing every-push contract.
        self.assertTrue(p["terraform"]["run"])
        self.assertTrue(p["shell"]["run"])
        self.assertFalse(p["kubernetes"]["run"])
        self.assertTrue(self.plan(["README.md"], kind="iac", **{"manifests-command": "render"})["kubernetes"]["run"])

    def test_iac_codeql_actions_only_and_custom_languages(self):
        for path in ("main.tf", "src/main.py"):
            self.assertFalse(self.plan([path], kind="iac")["codeql"]["run"])
            self.assertTrue(self.plan([path], kind="iac", **{"codeql-languages": "python"})["codeql"]["run"])
        self.assertTrue(self.plan([".github/workflows/ci.yml"], kind="iac")["codeql"]["run"])

    def test_python_caches_match_installer(self):
        setup = (ROOT / "security/src/partials/setup-python-project.yml").read_text()
        pip = next(line for line in setup.splitlines() if line.startswith("    cache:"))
        self.assertIn("hashFiles(format('{0}/uv.lock', inputs.working-directory)) == '' &&", pip)
        self.assertIn("enable-cache: true", setup)

    def test_caller_templates_have_distinct_concurrency_groups(self):
        groups = []
        for template in (ROOT / "security/templates/callers").glob("*.yml"):
            groups.extend(line.strip() for line in template.read_text().splitlines() if line.startswith("  group:"))
        self.assertEqual(len(groups), len(set(groups)))

    def test_container_includes_documents_in_context(self):
        opts = {"context": "app", "dockerfile": "docker/Dockerfile"}
        for path in ("app/README.md", "docker/Dockerfile", "app/.dockerignore"):
            self.assertTrue(self.plan([path], kind="container", **opts)["image"]["run"])
        self.assertFalse(self.plan(["docs/guide.md"], kind="container", **opts)["image"]["run"])
        self.assertTrue(self.plan(["docker/Dockerfile"], kind="container", **(opts | {"dockerfile": "./docker/Dockerfile"}))["image"]["run"])
        self.assertTrue(self.plan(["README.md"], kind="container")["image"]["run"])
        self.assertTrue(self.plan(["README.md"], kind="container", **{"context": "https://example.test/repo.git"})["image"]["run"])

    def test_typescript_lockfile_scan_skips_source_only_changes(self):
        self.assertFalse(self.plan(["src/index.ts"], kind="typescript")["deps"]["run"])
        for path in ("package-lock.json", "pnpm-lock.yaml", "package.json", "osv-scanner.toml"):
            self.assertTrue(self.plan([path], kind="typescript")["deps"]["run"])

    def test_embedded_selector_events_custom_rules_and_isolation(self):
        source = (ROOT / "security/src/partials/select.py").read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            # Isolated Python must not import caller-controlled modules.
            (root / "json.py").write_text("raise RuntimeError('caller code executed')\n")
            defaults = {"semgrep-rules": "p/python p/secrets"}
            for event, force, extra, semgrep in (
                ("push", "false", {}, True),
                ("pull_request", "false", {}, False),
                ("pull_request", "true", {}, True),
                ("pull_request", "false", {"semgrep-rules": "custom/rules"}, True),
            ):
                # Use a real git diff for a documentation-only PR.
                subprocess.run(["git", "init", "-q", directory], check=True)
                def git(*args):
                    return subprocess.check_output(["git", "-C", directory, *args], text=True).strip()
                git("config", "user.email", "test@example.test")
                git("config", "user.name", "Test")
                git("add", ".")
                git("commit", "--allow-empty", "-qm", "base")
                base = git("rev-parse", "HEAD")
                (root / "README.md").write_text(base)
                git("add", ".")
                git("commit", "-qm", "docs")
                env = dict(os.environ, INPUTS=json.dumps(defaults | extra),
                           KIND="python", EVENT=event, FORCE=force, BASE=base,
                           HEAD=git("rev-parse", "HEAD"), GITHUB_OUTPUT=str(root / "output"),
                           GITHUB_STEP_SUMMARY=str(root / "summary"))
                subprocess.run([sys.executable, "-I", "-"], input=source, text=True,
                               cwd=directory, env=env, check=True)
                last = (root / "output").read_text().splitlines()[-1]
                actual = json.loads(last.removeprefix("plan="))
                self.assertEqual(actual["semgrep"]["run"], semgrep, (event, force, extra))
                self.assertTrue(actual["secrets"]["run"])
                self.assertEqual(actual["dependency-review"]["run"], event == "pull_request" and force == "true")
            (root / ".semgrep").mkdir()
            env["INPUTS"] = json.dumps(defaults)
            subprocess.run([sys.executable, "-I", "-"], input=source, text=True,
                           cwd=directory, env=env, check=True)
            self.assertIn("custom Semgrep rules", (root / "output").read_text().splitlines()[-1])
            (root / "app").mkdir()
            (root / "context").symlink_to(root / "app", target_is_directory=True)
            env.update(KIND="container", INPUTS=json.dumps({"context": "context"}))
            subprocess.run([sys.executable, "-I", "-"], input=source, text=True,
                           cwd=directory, env=env, check=True)
            self.assertIn("symlinked build context", (root / "output").read_text().splitlines()[-1])

    def test_merge_base_diff_includes_deletions_and_both_rename_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], text=True).strip()
            git("init", "-q")
            git("config", "user.email", "test@example.test")
            git("config", "user.name", "Test")
            root = pathlib.Path(directory)
            (root / "source.py").write_text("print('hello')\n")
            (root / "deleted.py").write_text("print('gone')\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            git("mv", "source.py", "README.md")
            git("rm", "deleted.py")
            git("commit", "-qm", "rename and delete")
            paths = selection.changed_paths(base, git("rev-parse", "HEAD"), directory)
            self.assertEqual(set(paths), {"source.py", "README.md", "deleted.py"})
            self.assertTrue(self.plan(paths)["codeql"]["run"])
            self.assertIsNone(selection.changed_paths("0" * 40, "HEAD", directory))


if __name__ == "__main__":
    unittest.main()
