"""Production-path T-007 regressions using isolated Git repos and injected boundaries."""
import importlib.util
import json
import hashlib
import urllib.error
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PS = shutil.which("powershell.exe") or shutil.which("pwsh")
SPEC = importlib.util.spec_from_file_location("upstream_ops", ROOT / "tools/upstream_ops.py")
OPS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPS)
DIGEST = "sha256:" + "a" * 64
PREVIOUS = "sha256:" + "b" * 64


def git(repo, *args):
    p = subprocess.run(["git", "-c", "safe.directory=*", *args], cwd=repo,
                       capture_output=True, text=True, encoding="utf-8", timeout=30)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


def quote(s):
    return "'" + str(s).replace("'", "''") + "'"


@unittest.skipUnless(PS, "PowerShell required for the production entrypoints")
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t007-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo with spaces"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "T007 fixture")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        (self.repo / ".gitignore").write_text(".ai/runtime/\n__pycache__/\n")
        (self.repo / "wb_proxy.py").write_text('server_version = "wb-proxy/1.7.2"\nmeta = {"version": "1.7.2"}\n')
        recipe = self.repo / "wrt/openwrt/workbuddy2api/Makefile"
        recipe.parent.mkdir(parents=True)
        recipe.write_text("PKG_VERSION:=1.7.2\nPKG_RELEASE:=1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "upstream baseline")
        self.base = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-b", "custom/main")
        (self.repo / "wb_proxy.py").write_text('server_version = "wb-proxy/1.7.2.1"\nmeta = {"version": "1.7.2.1"}\n')
        recipe.write_text("PKG_VERSION:=1.7.2.1\nPKG_RELEASE:=1\n")
        badge = next(line.strip() for line in (ROOT / "README.md").read_text(encoding="utf-8-sig").splitlines() if "Release-v" in line)
        (self.repo / "README.md").write_text(badge + "\n")
        shutil.copytree(ROOT / "tools", self.repo / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        for file in ("Check-Upstream.cmd", "Update-From-Upstream.cmd"):
            shutil.copy2(ROOT / file, self.repo / file)
        compose = self.repo / "deploy/nas"
        compose.mkdir(parents=True)
        shutil.copy2(ROOT / "deploy/nas/docker-compose.yml", compose / "docker-compose.yml")
        suite = self.repo / "tests"
        suite.mkdir()
        (suite / "_test_release_engineering.py").write_text(
            "from pathlib import Path\nPath('.ai/runtime/focused-called').write_text('focused')\nprint('Ran 1 test\\nOK')\n")
        (suite / "run_all.py").write_text(
            "import sys\nfrom pathlib import Path\nPath('.ai/runtime/full-called').write_text(' '.join(sys.argv))\nprint('1 passed, 0 failed, 0 skipped')\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "fork tooling")
        self.custom = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-b", "upstream-fixture", self.base)
        (self.repo / "delta.txt").write_text("new upstream behavior\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "safe upstream change")
        self.up = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "custom/main")
        git(self.repo, "remote", "add", "origin", str(self.repo))
        git(self.repo, "remote", "add", "upstream", str(self.repo))
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        git(self.repo, "update-ref", "refs/remotes/origin/custom/main", self.custom)
        git(self.repo, "update-ref", "refs/remotes/upstream/main", self.up)
        self.runtime = self.repo / ".ai/runtime"
        self.runtime.mkdir(parents=True)
        self.trace = self.runtime / "actions.jsonl"

    def ps(self, text):
        harness = self.runtime / "harness.ps1"
        harness.write_text("$ErrorActionPreference='Stop'\n" + text, encoding="utf-8-sig")
        p = subprocess.run([PS, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                           cwd=self.repo, capture_output=True, timeout=90)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")

    def wrapper(self, filename, *args):
        if os.name == "nt":
            argv = ["cmd.exe", "/d", "/c", filename, *args]
        else:
            argv = [PS, "-NoProfile", "-File", str(self.repo / "tools" / filename.replace(".cmd", ".ps1")), *args]
        p = subprocess.run(argv, cwd=self.repo, capture_output=True, timeout=90)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")

    def evidence(self, mode="update"):
        files = list(self.runtime.glob("sync-" + mode + "-*.json"))
        self.assertTrue(files)
        record = json.loads(max(files, key=lambda p: p.stat().st_mtime_ns).read_text(encoding="utf-8-sig"))
        sink = os.environ.get("WB_T007_EVIDENCE_DIR")
        if sink:
            import uuid
            dest = Path(sink)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (record["status"]+"-"+uuid.uuid4().hex+".json")).write_text(json.dumps(record, indent=2))
        return record

    def actions(self):
        return [json.loads(l) for l in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def update(self, failure="", mutate="", extra="", rollback=False, throws=False, review=True):
        # This boundary is injected into the actual updater. No substitute state machine.
        mock = """
$mock = {
 param($Action,$Context)
 Add-Content -LiteralPath TRACE -Value ($Action | ConvertTo-Json -Compress)
 if ($Action -eq 'NAS_ROLLBACK' -and RBFAIL) { throw 'rollback injected failure' }
 if ($Action -eq FAIL) {
   if (THROWS) { throw 'injected exception with sk-secret-canary' }
   return @{Success=$false}
 }
 $r = @{Success=$true;Draft=$true;AssetsVerified=$true;PreflightPassed=$true;Published=$true;MultiArch=$true;Digest=DIGEST;
       PreviousDigest=PREVIOUS;PreviousTag='v1.7.2.9';SnapshotPath='/fixture/snapshot';AccountsReady=3;
       Healthy=$true;NetworkOk=$true;SmokePassed=$true;RestoredTag='v1.7.2.9'}
 if ($Action -eq 'NAS_ROLLBACK') { $r.Digest=PREVIOUS }
 MUTATION
 return $r
}
& './tools/Update-From-Upstream.ps1' -RepoPath REPO -NoFetch -AuthorizeRelease -AuthorizeNas -StateCompatibilitySha UP -PythonExe PYTHON -ExternalExecutor $mock REVIEW EXTRA
"""
        replacements = {"TRACE": quote(self.trace), "RBFAIL": "$true" if rollback else "$false",
                        "FAIL": quote(failure), "THROWS": "$true" if throws else "$false",
                        "DIGEST": quote(DIGEST), "PREVIOUS": quote(PREVIOUS), "MUTATION": mutate,
                        "REPO": quote(self.repo), "UP": quote("unknown" if extra == "-StateCompatibilitySha unknown" else self.up), "PYTHON": quote(sys.executable), "EXTRA": "" if extra == "-StateCompatibilitySha unknown" else extra,
                        "REVIEW": "-ReviewedDraftTag "+quote("v1.7.2.2") if review else ""}
        for k, v in replacements.items():
            mock = mock.replace(k, v)
        return self.ps(mock)

    def commit_custom_change(self, path, content):
        (self.repo / path).write_text(content)
        git(self.repo, "add", path)
        git(self.repo, "commit", "-m", "fixture change")
        self.custom = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-ref", "refs/remotes/origin/custom/main", self.custom)

    def test_success_integrates_real_git_and_records_identity(self):
        before = git(self.repo, "status", "--porcelain")
        rc, out = self.update()
        self.assertEqual(rc, 0, out)
        e = self.evidence()
        self.assertEqual(e["status"], "SUCCESS")
        self.assertEqual(e["old_upstream_sha"], self.base)
        self.assertEqual(e["new_upstream_sha"], self.up)
        self.assertEqual(e["ghcr_digest"], DIGEST)
        self.assertEqual(e["previous_nas_tag"], "v1.7.2.9")
        self.assertEqual(e["new_nas_tag"], "v1.7.2.2")
        self.assertEqual(e["final_health"], "HEALTHY")
        integrated = Path(e["integration_path"])
        self.assertTrue((integrated / "delta.txt").exists())
        self.assertTrue((integrated / ".ai/runtime/focused-called").exists())
        self.assertIn("tests/run_all.py --jobs 4 --logs", (integrated / ".ai/runtime/full-called").read_text())
        self.assertIn('"version": "1.7.2.2"', (integrated / "wb_proxy.py").read_text())
        self.assertIn("PKG_VERSION:=1.7.2.2", (integrated / "wrt/openwrt/workbuddy2api/Makefile").read_text())
        git(integrated, "merge-base", "--is-ancestor", self.up, "HEAD")
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), self.custom)
        self.assertEqual(git(self.repo, "status", "--porcelain"), before)

    def test_check_then_update_does_not_create_dirty_blocker(self):
        self.assertEqual(self.wrapper("Check-Upstream.cmd", "-NoFetch")[0], 0)
        self.assertEqual(self.wrapper("Check-Upstream.cmd", "-NoFetch")[0], 0)
        self.assertEqual(git(self.repo, "status", "--porcelain"), "")
        rc, out = self.update()
        self.assertEqual(rc, 0, out)
        self.assertNotEqual(self.evidence()["last_gate"], "WORKSPACE")

    def test_dirty_stops_before_any_action(self):
        (self.repo / "uncommitted.txt").write_text("preserve")
        self.assertNotEqual(self.update()[0], 0)
        self.assertEqual(self.actions(), [])
        self.assertEqual(self.evidence()["last_gate"], "WORKSPACE")
        self.assertTrue((self.repo / "uncommitted.txt").exists())

    def test_divergence_stops(self):
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.custom)
        self.assertNotEqual(self.update()[0], 0)
        self.assertEqual(self.evidence()["last_gate"], "DELTA")
        self.assertEqual(self.actions(), [])

    def test_no_update_and_dry_run_are_read_only(self):
        rc, out = self.wrapper("Update-From-Upstream.cmd", "-NoFetch", "-DryRun")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.evidence("dry-run")["status"], "DRY_RUN_PLAN_ONLY")
        self.assertFalse(list(self.runtime.glob("integration-*")))
        git(self.repo, "update-ref", "refs/remotes/upstream/main", self.base)
        self.assertEqual(self.wrapper("Update-From-Upstream.cmd", "-NoFetch")[0], 0)
        self.assertEqual(self.evidence()["status"], "UP_TO_DATE")

    def test_conflict_stops_before_identity_tests_and_external(self):
        self.commit_custom_change("delta.txt", "local incompatible edit")
        self.assertNotEqual(self.update()[0], 0)
        e = self.evidence()
        self.assertEqual(e["last_gate"], "INTEGRATION")
        self.assertIn("AA delta.txt", git(e["integration_path"], "status", "--porcelain"))
        self.assertEqual(self.actions(), [])

    def test_high_risk_force_cannot_bypass(self):
        git(self.repo, "checkout", "upstream-fixture")
        (self.repo / "wb_settings.py").write_text("# schema changed")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "schema")
        self.up = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "custom/main")
        git(self.repo, "update-ref", "refs/remotes/upstream/main", self.up)
        self.assertNotEqual(self.update(extra="-Force")[0], 0)
        self.assertEqual(self.evidence()["last_gate"], "RISK")
        self.assertEqual(self.actions(), [])

    def test_full_failure_is_not_tolerated(self):
        self.commit_custom_change("tests/run_all.py", "print('141 passed, 1 failed, 0 skipped')\nraise SystemExit(1)\n")
        self.assertNotEqual(self.update()[0], 0)
        self.assertEqual(self.evidence()["full_exit"], 1)
        self.assertEqual(self.actions(), [])
        self.assertEqual(git(self.repo, "tag"), "")

    def test_focused_failure_still_records_full_suite(self):
        self.commit_custom_change("tests/_test_release_engineering.py", "raise SystemExit(1)\n")
        self.assertNotEqual(self.update()[0], 0)
        self.assertEqual(self.evidence()["focused_exit"], 1)
        self.assertEqual(self.evidence()["full_exit"], 0)
        self.assertEqual(self.actions(), [])

    def test_skipped_or_empty_full_tests_stop(self):
        for summary in ["1 passed, 0 failed, 1 skipped", "1 passed, 0 failed, 10 skipped", "0 passed, 0 failed, 0 skipped"]:
            with self.subTest(summary=summary):
                self.commit_custom_change("tests/run_all.py", "print("+repr(summary)+")\n")
                self.assertNotEqual(self.update()[0], 0)
                self.assertEqual(self.actions(), [])

    def test_t008_missing_service_membership_stops(self):
        path = "deploy/nas/docker-compose.yml"
        self.commit_custom_change(path, (self.repo / path).read_text().replace("      - sub2api", "      - other"))
        self.assertNotEqual(self.update()[0], 0)
        self.assertEqual(self.evidence()["last_gate"], "T008")

    def test_each_external_failure_blocks_later_effects_or_rolls_back(self):
        order = ["GIT_PUSH", "DRAFT_RELEASE_VERIFY", "GHCR_CAPABILITY_PREFLIGHT", "RELEASE_PUBLISH", "GHCR_VERIFY",
                 "NAS_PREFLIGHT_AND_SNAPSHOT", "NAS_DEPLOY_TAG", "NAS_VERIFY", "NAS_AUTHENTICATED_SMOKE"]
        # Each pass creates a new integration branch from the same untouched custom/main.
        for i, action in enumerate(order):
            with self.subTest(action=action):
                if self.trace.exists():
                    self.trace.unlink()
                rc, out = self.update(failure=action, throws=(i % 2 == 1))
                self.assertNotEqual(rc, 0, out)
                expected = order[:i+1] + (["NAS_ROLLBACK"] if i >= 6 else [])
                self.assertEqual(self.actions(), expected)
                e = self.evidence()
                self.assertEqual(e["rollback_status"], "VERIFIED" if i >= 6 else "NOT_NEEDED")
                self.assertNotIn("sk-secret-canary", json.dumps(e))

    def test_postdeploy_fields_are_enforced(self):
        for field, value in [("Healthy", "$false"), ("NetworkOk", "$false"),
                             ("AccountsReady", "2"), ("Digest", quote(PREVIOUS))]:
            with self.subTest(field=field):
                if self.trace.exists(): self.trace.unlink()
                rc, out = self.update(mutate=f"if ($Action -eq 'NAS_VERIFY') {{ $r.{field}={value} }}")
                self.assertNotEqual(rc, 0, out)
                self.assertEqual(self.actions()[-1], "NAS_ROLLBACK")
                self.assertEqual(self.evidence()["status"], "ROLLED_BACK")

    def test_invalid_ghcr_metadata_never_snapshots(self):
        for mutation in ["$r.MultiArch=$false", "$r.Digest='sha256:bad'"]:
            if self.trace.exists(): self.trace.unlink()
            self.assertNotEqual(self.update(mutate=f"if ($Action -eq 'GHCR_VERIFY') {{ {mutation} }}")[0], 0)
            self.assertNotIn("NAS_PREFLIGHT_AND_SNAPSHOT", self.actions())

    def test_rollback_failure_is_explicit(self):
        self.assertNotEqual(self.update(failure="NAS_VERIFY", rollback=True)[0], 0)
        self.assertEqual(self.evidence()["status"], "ROLLBACK_FAILED")
        self.assertEqual(self.evidence()["final_health"], "UNKNOWN")

    def test_unreviewed_data_format_never_mutates_nas(self):
        self.assertNotEqual(self.update(extra="-StateCompatibilitySha unknown")[0], 0)
        self.assertNotIn("NAS_PREFLIGHT_AND_SNAPSHOT", self.actions())
        self.assertEqual(self.actions()[-1], "GHCR_VERIFY")

    def test_release_only_has_complete_audit_and_no_nas_calls(self):
        rc, out = self.update(extra="-SkipNasDeploy")
        self.assertEqual(rc, 0, out)
        e = self.evidence()
        self.assertEqual(e["status"], "RELEASE_PUBLISHED_NAS_SKIPPED")
        self.assertEqual(e["ghcr_digest"], DIGEST)
        self.assertIsNone(e["previous_nas_tag"])
        self.assertFalse(any(a.startswith("NAS_") for a in self.actions()))

    def test_default_executor_requires_authorization(self):
        rc, out = self.wrapper("Update-From-Upstream.cmd", "-NoFetch", "-PythonExe", sys.executable)
        self.assertNotEqual(rc, 0, out)
        self.assertEqual(git(self.repo, "tag"), "")

    def test_version_resolution_errors_are_real_stops(self):
        for source in [None, "no version", 'server_version="wb-proxy/bad"\nmeta={"version":"bad"}',
                       'server_version="wb-proxy/1.7.2.2"\nmeta={"version":"1.7.2.2"}',
                       'server_version="wb-proxy/1.7.2"\nmeta={"version":"1.7.1"}',
                       'server_version="wb-proxy/1.7.2"\nserver_version="wb-proxy/1.7.2"\nmeta={"version":"1.7.2"}']:
            with self.subTest(source=source):
                git(self.repo, "checkout", "upstream-fixture")
                path = self.repo / "wb_proxy.py"
                if source is None: path.unlink()
                else: path.write_text(source)
                git(self.repo, "add", ".")
                git(self.repo, "commit", "-m", "malformed version")
                git(self.repo, "update-ref", "refs/remotes/upstream/main", git(self.repo, "rev-parse", "HEAD"))
                git(self.repo, "checkout", "custom/main")
                self.assertNotEqual(self.wrapper("Check-Upstream.cmd", "-NoFetch")[0], 0)
                self.assertEqual(self.evidence("check")["last_gate"], "VERSION")


    def test_draft_review_pause_and_exact_resume(self):
        rc, out = self.update(review=False)
        self.assertEqual(rc, 0, out)
        e = self.evidence()
        self.assertEqual(e["status"], "DRAFT_READY_AWAITING_REVIEW")
        self.assertEqual(self.actions(), ["GIT_PUSH", "DRAFT_RELEASE_VERIFY"])
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        git(self.repo, "tag", e["fork_tag"], e["integration_sha"])
        git(self.repo, "update-ref", "refs/remotes/origin/custom/main", e["integration_sha"])
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.up)
        rc, out = self.update(extra="-ResumeReleaseEvidence " + quote(path))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.evidence()["status"], "SUCCESS")
        self.assertEqual(self.actions().count("GIT_PUSH"), 1)
        self.assertEqual(self.evidence()["integration_sha"], e["integration_sha"])

    def test_resume_rejects_moved_identity_before_external(self):
        rc, out = self.update(review=False)
        self.assertEqual(rc, 0, out)
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        self.trace.unlink()
        self.assertNotEqual(self.update(extra="-ResumeReleaseEvidence " + quote(path))[0], 0)
        self.assertEqual(self.actions(), [])
        self.assertEqual(self.evidence()["last_gate"], "RESUME_RELEASE")


    def test_ahead_only_main_stops_check_and_update_before_effects(self):
        git(self.repo, "checkout", "main")
        (self.repo / "main-only.txt").write_text("unexpected fork commit")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "ahead-only drift")
        drift = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "custom/main")
        git(self.repo, "update-ref", "refs/remotes/origin/main", drift)
        git(self.repo, "update-ref", "refs/remotes/upstream/main", self.base)
        rc, out = self.ps(". ./tools/UpstreamSync.Common.ps1\n$d=Get-UpstreamDeltaSummary -Repo .\nif ($d.AheadCount -ne 1 -or $d.BehindCount -ne 0 -or $d.HasUpdate -or -not $d.IsDivergent) {throw 'bad delta'}")
        self.assertEqual(rc, 0, out)
        self.assertNotEqual(self.wrapper("Check-Upstream.cmd", "-NoFetch")[0], 0)
        self.assertEqual(self.evidence("check")["status"], "DIVERGENT_STOP")
        self.assertNotEqual(self.update()[0], 0)
        e = self.evidence()
        self.assertEqual(e["last_gate"], "DELTA")
        self.assertNotIn("integration_path", e)
        self.assertEqual(self.actions(), [])

    def test_release_badge_is_bumped_and_committed_with_source(self):
        rc, out = self.update()
        self.assertEqual(rc, 0, out)
        e = self.evidence()
        repo = Path(e["integration_path"])
        doc = git(repo, "show", "HEAD:README.md")
        self.assertNotIn("1.7.2.1", doc)
        self.assertIn("Release-v1.7.2.2", doc)
        self.assertIn('alt="Version 1.7.2.2"', doc)
        changed = set(git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines())
        self.assertEqual(changed, {"README.md", "wb_proxy.py", "wrt/openwrt/workbuddy2api/Makefile"})
        self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_badge_new_upstream_base_updates_both_visible_identity_fields(self):
        rc, out = self.ps(". ./tools/UpstreamSync.Common.ps1\nUpdate-ReleaseIdentityFiles -Repo . -NewVersion 1.7.3.1")
        self.assertEqual(rc, 0, out)
        doc = (self.repo / "README.md").read_text()
        self.assertNotIn("1.7.2.1", doc)
        self.assertIn("Release-v1.7.3.1", doc)
        self.assertIn('alt="Version 1.7.3.1"', doc)

    def test_badge_missing_ambiguous_or_disagreeing_stops_without_writes(self):
        original = (self.repo / "README.md").read_text()
        proxy = (self.repo / "wb_proxy.py").read_bytes()
        recipe = (self.repo / "wrt/openwrt/workbuddy2api/Makefile").read_bytes()
        current_alt = original.split('alt="Version ', 1)[1].split('"', 1)[0]
        wrong_alt = "9.9.9.9" if current_alt != "9.9.9.9" else "8.8.8.8"
        disagreeing = original.replace(
            f'alt="Version {current_alt}"', f'alt="Version {wrong_alt}"', 1)
        self.assertNotEqual(disagreeing, original)
        for content in ["no badge\n", original * 2, disagreeing]:
            with self.subTest(content=content):
                (self.repo / "README.md").write_text(content)
                rc, out = self.ps(". ./tools/UpstreamSync.Common.ps1\nUpdate-ReleaseIdentityFiles -Repo . -NewVersion 1.7.3.1")
                self.assertNotEqual(rc, 0, out)
                self.assertEqual((self.repo / "wb_proxy.py").read_bytes(), proxy)
                self.assertEqual((self.repo / "wrt/openwrt/workbuddy2api/Makefile").read_bytes(), recipe)
                self.assertEqual((self.repo / "README.md").read_text(), content)

    def test_failed_push_audit_resumes_exact_existing_integration(self):
        rc, out = self.update(failure="GIT_PUSH")
        self.assertNotEqual(rc, 0, out)
        e = self.evidence()
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        self.assertEqual(e["old_main_sha"], self.base)
        self.assertEqual(e["old_custom_sha"], self.custom)
        # Simulate the live boundary's local tag that survived a rejected push.
        git(self.repo, "tag", e["fork_tag"], e["integration_sha"])
        rc, out = self.update(extra="-ResumeReleaseEvidence " + quote(path), review=False)
        self.assertEqual(rc, 0, out)
        resumed = self.evidence()
        self.assertEqual(resumed["integration_sha"], e["integration_sha"])
        self.assertEqual(resumed["integration_path"], e["integration_path"])
        self.assertEqual(resumed["status"], "DRAFT_READY_AWAITING_REVIEW")

    def test_remote_verified_local_pending_is_recorded_and_resumable(self):
        rc, out = self.update(mutate="if ($Action -eq 'GIT_PUSH') { $r.Success=$false; $r.GitPushStatus='REMOTE_VERIFIED_LOCAL_PENDING' }")
        self.assertNotEqual(rc, 0, out)
        e = self.evidence()
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        self.assertEqual(e["git_push_status"], "REMOTE_VERIFIED_LOCAL_PENDING")
        self.assertEqual(self.actions(), ["GIT_PUSH"])
        # Saved original refs survive even after tracking refs have advanced.
        git(self.repo, "tag", e["fork_tag"], e["integration_sha"])
        git(self.repo, "update-ref", "refs/remotes/origin/main", self.up)
        git(self.repo, "update-ref", "refs/remotes/origin/custom/main", e["integration_sha"])
        rc, out = self.update(extra="-ResumeReleaseEvidence " + quote(path), review=False)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.evidence()["status"], "DRAFT_READY_AWAITING_REVIEW")

    def test_push_resume_rejects_missing_original_refs_or_moved_integration(self):
        self.assertNotEqual(self.update(failure="GIT_PUSH")[0], 0)
        e = self.evidence()
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        original = json.loads(path.read_text())
        invalid = dict(original)
        invalid.pop("old_main_sha")
        path.write_text(json.dumps(invalid))
        self.trace.unlink()
        self.assertNotEqual(self.update(extra="-ResumeReleaseEvidence "+quote(path))[0], 0)
        self.assertEqual(self.actions(), [])
        path.write_text(json.dumps(original))
        integrated = Path(e["integration_path"])
        (integrated / "changed-after-stop").write_text("unreviewed")
        git(integrated, "add", ".")
        git(integrated, "commit", "-m", "identity moved")
        self.assertNotEqual(self.update(extra="-ResumeReleaseEvidence "+quote(path))[0], 0)
        self.assertEqual(self.actions(), [])

    def test_draft_verification_stop_reuses_verified_push_intent(self):
        rc, out = self.update(failure="DRAFT_RELEASE_VERIFY")
        self.assertNotEqual(rc, 0, out)
        e = self.evidence()
        path = max(self.runtime.glob("sync-update-*.json"), key=lambda p: p.stat().st_mtime_ns)
        self.assertEqual(e["git_push_status"], "VERIFIED")
        rc, out = self.update(extra="-ResumeReleaseEvidence "+quote(path), review=False)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.evidence()["status"], "DRAFT_READY_AWAITING_REVIEW")
        self.assertEqual(self.evidence()["integration_sha"], e["integration_sha"])

    def test_version_progression_and_backwards_direction(self):
        rc, out = self.ps(". ./tools/UpstreamSync.Common.ps1\n(Derive-NextForkVersion '1.7.3' '1.7.2.8').ProposedForkVersion\n(Derive-NextForkVersion '1.7.2' '1.7.2.8').ProposedForkVersion\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("1.7.3.1", out)
        self.assertIn("1.7.2.9", out)
        self.assertNotEqual(self.ps(". ./tools/UpstreamSync.Common.ps1\nDerive-NextForkVersion '1.7.1' '1.7.2.8'\n")[0], 0)


class LiveBoundaryTests(unittest.TestCase):
    def context(self):
        return {"Repo": str(ROOT), "NewTag": "v1.7.2.2", "Sha": "c"*40, "UpstreamSha": "d"*40,
                "OldMain": "e"*40, "OldCustom": "f"*40, "SourceRepo": str(ROOT), "AuthorizeRelease": True,
                "CurrentTag": "v1.7.2.1",
                "AuthorizeNas": True, "StateCompatibilitySha": "d"*40}

    def test_live_unknown_action_fails_closed(self):
        with self.assertRaises(RuntimeError): OPS.execute("UNKNOWN", self.context())

    def test_push_executes_atomic_exact_refs(self):
        c = self.context()
        pushed = False
        def fake_git(ctx, *args):
            nonlocal pushed
            if args[:2] == ("remote", "get-url"): return "https://github.com/deefery/workbuddy2api-hub.git"
            if args == ("rev-parse", "HEAD"): return c["Sha"]
            if args == ("rev-parse", "refs/heads/main"): return c["OldMain"]
            if args[0] == "push": pushed = True
            if args[0] == "ls-remote":
                if pushed:
                    return f"{c['UpstreamSha']}\\trefs/heads/main\\n{c['Sha']}\\trefs/heads/custom/main\\n{c['Sha']}\\trefs/tags/{c['NewTag']}".replace("\\t", "\t").replace("\\n", "\n")
                return f"{c['OldMain']}\\trefs/heads/main\\n{c['OldCustom']}\\trefs/heads/custom/main".replace("\\t", "\t").replace("\\n", "\n")
            return ""
        with patch.object(OPS, "git", side_effect=fake_git) as g:
            self.assertTrue(OPS.execute("GIT_PUSH", c)["Success"])
            calls = [x.args[1:] for x in g.call_args_list]
            push = next(x for x in calls if x[0] == "push")
            self.assertIn("--atomic", push)
            self.assertIn(f"{c['UpstreamSha']}:refs/heads/main", push)
            self.assertIn(f"{c['Sha']}:refs/heads/custom/main", push)

    def test_unreviewed_draft_does_not_publish(self):
        c = self.context()
        with patch.object(OPS, "run") as run:
            with self.assertRaises(RuntimeError): OPS.execute("RELEASE_PUBLISH", c)
            run.assert_not_called()

    def test_nas_missing_compatibility_rejects_before_ssh(self):
        c = self.context()
        c["StateCompatibilitySha"] = "unknown"
        with patch.object(OPS, "ssh") as ssh:
            with self.assertRaises(RuntimeError): OPS.execute("NAS_DEPLOY_TAG", c)
            ssh.assert_not_called()

    def test_deploy_preserves_exact_env_field_and_uses_digest(self):
        c = self.context()
        with patch.object(OPS, "ssh") as ssh:
            OPS.deploy(c, "v1.7.2.2", DIGEST)
            text = ssh.call_args.args[1]
            self.assertIn("s/^WB_IMAGE_TAG=.*/WB_IMAGE_TAG=v1.7.2.2/", text)
            self.assertIn(f"{OPS.IMAGE}@{DIGEST}", text)
            self.assertIn("--pull never wb-proxy", text)

    def test_ghcr_wrong_platforms_stop(self):
        c = self.context()
        bad_manifest = {"manifests": [{"platform": {"os": "linux", "architecture": "amd64"}}]}
        with patch.object(OPS, "wait_workflow"), patch.object(OPS, "view_release", return_value={"isDraft": False, "isPrerelease": False}), \
             patch.object(OPS, "request_ghcr", return_value=(200, {}, json.dumps(bad_manifest).encode("utf-8"))):
            with self.assertRaises(RuntimeError) as cm:
                OPS.execute("GHCR_VERIFY", c)
            self.assertEqual(cm.exception.reason, "GHCR_PLATFORM_MISMATCH")

    def test_assets_checksum_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self.context(); c["Repo"] = tmp
            recipe = Path(tmp) / "wrt/openwrt/workbuddy2api/Makefile"
            recipe.parent.mkdir(parents=True); recipe.write_text("PKG_RELEASE:=1\n")
            dest = Path(tmp) / ".ai/runtime/release-assets"
            dest.mkdir(parents=True)
            names = ["workbuddy2api-hub-v1.7.2.2.zip", "workbuddy2api_1.7.2.2-1_all.ipk", "workbuddy2api-1.7.2.2-r1.apk"]
            for name in names: (dest/name).write_bytes(b"fixture")
            sums = "\n".join(OPS.hashlib.sha256(b"fixture").hexdigest()+"  "+n for n in names)
            (dest/"SHA256SUMS").write_text(sums)
            release = {"assets": [{"name": n} for n in names+["SHA256SUMS"]]}
            with patch.object(OPS, "run"):
                self.assertTrue(OPS.verify_assets(c, release))
                (dest/names[0]).write_bytes(b"tampered")
                with self.assertRaises(RuntimeError): OPS.verify_assets(c, release)



    def test_snapshot_covers_quiesced_state_and_failure_recovery(self):
        c = self.context(); c["NasDirectory"] = "/fixture"
        inspect = [{"Image": "img-id", "Config": {"Image": OPS.IMAGE + ":v1.7.2.9"}}]
        image = [{"RepoDigests": [OPS.IMAGE + "@" + PREVIOUS]}]
        def ssh(ctx, script, **kwargs):
            if "docker --version" in script: return ""
            if script.startswith("sed"): return "v1.7.2.9\n"
            if script.startswith("docker inspect"): return json.dumps(inspect)
            if script.startswith("docker image inspect"): return json.dumps(image)
            self.assertIn("docker stop wb-proxy", script)
            self.assertIn("cp -p .env docker-compose.yml", script)
            self.assertIn("data/accounts data/usage", script)
            self.assertIn("trap 'resume; rmdir .t007-update-lock' 0", script)
            self.assertIn("sha256sum", script)
            self.assertIn("docker start wb-proxy", script)
            return ""
        with patch.object(OPS, "ssh", side_effect=ssh), patch.object(OPS, "health", return_value={"AccountsReady": 3}), patch.object(OPS, "smoke", return_value=True):
            r = OPS.execute("NAS_PREFLIGHT_AND_SNAPSHOT", c)
            self.assertEqual(r["PreviousTag"], "v1.7.2.9")
            self.assertEqual(r["PreviousDigest"], PREVIOUS)

    def test_live_rollback_verifies_previous_digest_and_smoke(self):
        c = self.context()
        c.update(PreviousTag="v1.7.2.9", PreviousDigest=PREVIOUS)
        with patch.object(OPS, "deploy") as deploy, patch.object(OPS, "await_health", return_value={"Healthy": True, "NetworkOk": True, "AccountsReady": 3, "Digest": PREVIOUS}), patch.object(OPS, "smoke") as smoke, patch.object(OPS, "ssh"):
            r = OPS.execute("NAS_ROLLBACK", c)
            deploy.assert_called_once_with(c, "v1.7.2.9", PREVIOUS, reason="NAS_ROLLBACK_FAILURE")
            smoke.assert_called_once_with(c)
            self.assertEqual(r["RestoredTag"], "v1.7.2.9")


    def test_workflow_failure_is_not_a_success(self):
        c = self.context()
        run = {"head_sha": c["Sha"], "event": "push", "head_branch": c["NewTag"],
               "id": 4, "status": "completed", "conclusion": "failure"}
        with patch.object(OPS, "api", return_value={"workflow_runs": [run]}), patch.object(OPS.time, "sleep"):
            with self.assertRaises(RuntimeError): OPS.wait_workflow(c, "release.yml", "push")

    def test_live_draft_requires_stable_matching_draft(self):
        c = self.context()
        for draft, prerelease, tag in [(False, False, c["NewTag"]), (True, True, c["NewTag"]), (True, False, "v9.9.9.9")]:
            with self.subTest(draft=draft, prerelease=prerelease, tag=tag):
                with patch.object(OPS, "wait_workflow"), patch.object(OPS, "view_release", return_value={"isDraft": draft, "isPrerelease": prerelease, "tagName": tag}), patch.object(OPS, "verify_assets") as verify:
                    with self.assertRaises(RuntimeError): OPS.execute("DRAFT_RELEASE_VERIFY", c)
                    verify.assert_not_called()

    def test_live_nas_inspection_rejects_each_invalid_state(self):
        import copy
        c = self.context()
        c.update(Digest=DIGEST, AccountsReady=3)
        info = {"State": {"Health": {"Status": "healthy"}},
                "Config": {"Labels": {"com.docker.compose.project": "workbuddy2api-hub"}},
                "NetworkSettings": {"Networks": {"workbuddy2api-hub_default": {}, "sub2api_sub2api-network": {}}},
                "Image": "img"}
        image = {"RepoDigests": [OPS.IMAGE+"@"+DIGEST], "Config": {"Labels": {"org.opencontainers.image.revision": c["Sha"]}}}
        for kind in ["health", "owner", "network", "digest", "revision", "accounts", "auth"]:
            with self.subTest(kind=kind):
                i, m = copy.deepcopy(info), copy.deepcopy(image)
                ready = {"AccountsReady": 3, "KeyRequired": True}
                if kind == "health": i["State"]["Health"]["Status"] = "unhealthy"
                if kind == "owner": i["Config"]["Labels"]["com.docker.compose.project"] = "other"
                if kind == "network": i["NetworkSettings"]["Networks"].pop("sub2api_sub2api-network")
                if kind == "digest": m["RepoDigests"] = [OPS.IMAGE+"@"+PREVIOUS]
                if kind == "revision": m["Config"]["Labels"]["org.opencontainers.image.revision"] = "wrong"
                if kind == "accounts": ready["AccountsReady"] = 2
                if kind == "auth": ready["KeyRequired"] = False
                def ssh(ctx, script, **kwargs):
                    if script.startswith("docker inspect"): return json.dumps([i])
                    if script.startswith("docker image"): return json.dumps([m])
                    return json.dumps(ready)
                with patch.object(OPS, "ssh", side_effect=ssh):
                    with self.assertRaises(RuntimeError): OPS.health(c, DIGEST)


    def test_utf8_locale_independence(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self.context(); c["Repo"] = tmp
            recipe = Path(tmp) / "wrt/openwrt/workbuddy2api/Makefile"
            recipe.parent.mkdir(parents=True)
            # UTF-8 non-ASCII characters that fail under GBK/cp1252:
            recipe.write_text("PKG_RELEASE:=1\n# 测试中文字符与特殊符号 €★\n", encoding="utf-8")
            dest = Path(tmp) / ".ai/runtime/release-assets"
            dest.mkdir(parents=True)
            names = ["workbuddy2api-hub-v1.7.2.2.zip", "workbuddy2api_1.7.2.2-1_all.ipk", "workbuddy2api-1.7.2.2-r1.apk"]
            for name in names: (dest/name).write_bytes(b"fixture")
            sums = "\n".join(OPS.hashlib.sha256(b"fixture").hexdigest()+"  "+n for n in names)
            (dest/"SHA256SUMS").write_text(sums + "\n", encoding="utf-8")
            release = {"assets": [{"name": n} for n in names+["SHA256SUMS"]]}
            with patch.object(OPS, "run"):
                self.assertTrue(OPS.verify_assets(c, release))

    def test_lf_safe_ssh_transport(self):
        c = self.context()
        c["TargetNasHost"] = "nas-host"
        c["NasDirectory"] = "/share/test"
        captured = []
        def fake_run(argv, *, cwd=None, input=None, capture_output=True, timeout=180):
            captured.append((argv, input))
            class Resp:
                returncode = 0
                stdout = b"ok\n"
            return Resp()
        with patch("subprocess.run", side_effect=fake_run):
            OPS.ssh(c, "echo hello\r\necho world\r\n")
        self.assertEqual(len(captured), 1)
        argv, stdin_bytes = captured[0]
        self.assertIsInstance(stdin_bytes, bytes)
        self.assertNotIn(b"\r\n", stdin_bytes)
        self.assertIn(b"\n", stdin_bytes)
        self.assertIn(b"/share/CACHEDEV1_DATA/.qpkg/container-station/bin", stdin_bytes)

    def test_remote_docker_discovery_and_fallback(self):
        c = self.context()
        c["TargetNasHost"] = "nas-host"
        c["NasDirectory"] = "/share/test"
        # Remote exit 127 indicates missing docker executable in non-interactive environment
        def fake_run(argv, *, cwd=None, input=None, capture_output=True, timeout=180):
            class Resp:
                returncode = 127
                stdout = b""
            return Resp()
        with patch("subprocess.run", side_effect=fake_run):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.ssh(c, "docker inspect wb-proxy\n")
            self.assertEqual(cm.exception.reason, "SSH_SESSION_FAILURE")

    def test_docker_free_ghcr_verification(self):
        c = self.context()
        multi_manifest = {
            "schemaVersion": 2,
            "mediaType": OPS.OCI_INDEX_MEDIA,
            "manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}, "digest": "sha256:1111111111111111111111111111111111111111111111111111111111111111"},
                {"platform": {"os": "linux", "architecture": "arm64"}, "digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222"}
            ]
        }
        body_bytes = json.dumps(multi_manifest).encode("utf-8")
        expected_digest = "sha256:" + OPS.hashlib.sha256(body_bytes).hexdigest()

        with patch.object(OPS, "wait_workflow"), \
             patch.object(OPS, "view_release", return_value={"isDraft": False, "isPrerelease": False}), \
             patch.object(OPS, "request_ghcr", return_value=(200, {}, body_bytes)):
            res = OPS.execute("GHCR_VERIFY", c)
            self.assertTrue(res["Success"])
            self.assertEqual(res["Digest"], expected_digest)
            self.assertTrue(res["MultiArch"])

        # Missing arm64 fails closed
        amd_only = {"manifests": [{"platform": {"os": "linux", "architecture": "amd64"}}]}
        with patch.object(OPS, "wait_workflow"), \
             patch.object(OPS, "view_release", return_value={"isDraft": False, "isPrerelease": False}), \
             patch.object(OPS, "request_ghcr", return_value=(200, {}, json.dumps(amd_only).encode("utf-8"))):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.execute("GHCR_VERIFY", c)
            self.assertEqual(cm.exception.reason, "GHCR_PLATFORM_MISMATCH")

        # Moving tag between calls fails closed
        second_manifest = {"manifests": [{"platform": {"os": "linux", "architecture": "amd64"}}, {"platform": {"os": "linux", "architecture": "arm64"}, "extra": 1}]}
        with patch.object(OPS, "wait_workflow"), \
             patch.object(OPS, "view_release", return_value={"isDraft": False, "isPrerelease": False}), \
             patch.object(OPS, "request_ghcr", side_effect=[
                 (200, {}, body_bytes),
                 (200, {}, json.dumps(second_manifest).encode("utf-8"))
             ]):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.execute("GHCR_VERIFY", c)
            self.assertEqual(cm.exception.reason, "GHCR_MUTABLE_TAG_DETECTED")

    def test_pre_publish_ordering_and_capability_gate(self):
        c = self.context()
        multi_manifest = {"schemaVersion": 2, "mediaType": OPS.OCI_INDEX_MEDIA, "manifests": [
            {"platform": {"os": "linux", "architecture": "amd64"}},
            {"platform": {"os": "linux", "architecture": "arm64"}},
        ]}
        body = json.dumps(multi_manifest, separators=(",", ":")).encode("utf-8")
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        with patch.object(OPS, "request_ghcr", side_effect=[(200, {}, body), (200, {}, body)]) as req:
            res = OPS.execute("GHCR_CAPABILITY_PREFLIGHT", c)
        self.assertTrue(res["Success"])
        self.assertTrue(res["PreflightPassed"])
        self.assertEqual(res["Digest"], digest)
        self.assertEqual(req.call_args_list[0].args[0], "manifests/" + c["CurrentTag"])
        self.assertEqual(req.call_args_list[1].args[0], "manifests/" + digest)

        with patch.object(OPS, "fetch_ghcr_manifest", side_effect=OPS.ExternalGateError("GHCR_MALFORMED_MANIFEST")):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.execute("GHCR_CAPABILITY_PREFLIGHT", c)
            self.assertEqual(cm.exception.reason, "GHCR_MALFORMED_MANIFEST")

    def test_request_ghcr_bearer_challenge_success_and_failure(self):
        class Resp:
            def __init__(self, body, status=200, headers=None):
                self._body=body; self.status=status; self.headers=headers or {}
            def read(self): return self._body
            def __enter__(self): return self
            def __exit__(self, *a): return False
        challenge = urllib.error.HTTPError(
            OPS.GHCR_REGISTRY_BASE + "/manifests/v1.7.2.1", 401, "unauthorized",
            {"WWW-Authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:deefery/workbuddy2api-hub:pull"'}, None)
        with patch("urllib.request.urlopen", side_effect=[challenge, Resp(b'{"token":"TOKEN_CANARY"}'), Resp(b'{}')]) as opened:
            status, _headers, body = OPS.request_ghcr("manifests/v1.7.2.1", accept=OPS.ACCEPT_MANIFEST_HEADER)
            self.assertEqual(status, 200)
            self.assertEqual(body, b'{}')
            self.assertTrue(opened.call_args_list[2].args[0].headers.get("Authorization", "").startswith("Bearer "))
        challenge2 = urllib.error.HTTPError(
            OPS.GHCR_REGISTRY_BASE + "/manifests/v1.7.2.1", 401, "unauthorized",
            {"WWW-Authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:deefery/workbuddy2api-hub:pull"'}, None)
        with patch("urllib.request.urlopen", side_effect=[challenge2, Resp(b'{}')]):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.request_ghcr("manifests/v1.7.2.1")
            self.assertEqual(cm.exception.reason, "GHCR_TOKEN_FAILURE")

    def test_semantic_nas_failure_classification(self):
        c = self.context()
        with patch.object(OPS, "ssh", side_effect=OPS.ExternalGateError("REMOTE_DOCKER_CAPABILITY_FAILURE")):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.execute("NAS_PREFLIGHT_AND_SNAPSHOT", c)
            self.assertEqual(cm.exception.reason, "REMOTE_DOCKER_CAPABILITY_FAILURE")
        with patch.object(OPS, "deploy", side_effect=OPS.ExternalGateError("NAS_DEPLOY_FAILURE")):
            with self.assertRaises(OPS.ExternalGateError) as cm:
                OPS.execute("NAS_DEPLOY_TAG", dict(c, Digest=DIGEST))
            self.assertEqual(cm.exception.reason, "NAS_DEPLOY_FAILURE")

    def test_cli_secret_safety_and_bounded_reason(self):
        import io
        secret = "ghp_VerySecretAccessToken12345"
        out, err = io.StringIO(), io.StringIO()
        with patch.object(OPS, "execute", side_effect=OPS.ExternalGateError("GHCR_TOKEN_FAILURE", secret)):
            rc = OPS.cli_main(["upstream_ops.py", "GHCR_CAPABILITY_PREFLIGHT"], io.StringIO("{}"), out, err)
        self.assertEqual(rc, 1)
        combined = out.getvalue() + err.getvalue()
        self.assertNotIn(secret, combined)
        self.assertIn("GHCR_TOKEN_FAILURE", out.getvalue())




class PushRecoveryTests(unittest.TestCase):
    """Actual Git and atomic pushes only to disposable on-disk remotes."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t007-push-")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source"
        self.remote = Path(self.temp.name) / "remote.git"
        self.integration = Path(self.temp.name) / "integration"
        self.source.mkdir()
        git(self.source, "init", "-b", "main")
        git(self.source, "config", "user.name", "T007 fixture")
        git(self.source, "config", "user.email", "fixture@example.invalid")
        (self.source / "base").write_text("base")
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "base")
        base = git(self.source, "rev-parse", "HEAD")
        git(self.source, "checkout", "-b", "custom/main")
        (self.source / "fork").write_text("fork")
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "fork")
        custom = git(self.source, "rev-parse", "HEAD")
        git(self.source, "checkout", "-b", "upstream-fixture", base)
        (self.source / "upstream").write_text("upstream")
        git(self.source, "add", ".")
        git(self.source, "commit", "-m", "upstream")
        upstream = git(self.source, "rev-parse", "HEAD")
        git(self.source, "checkout", "custom/main")
        git(self.source, "worktree", "add", "-b", "codex/sync-fixture", str(self.integration), custom)
        git(self.integration, "merge", "--no-ff", "-m", "integrate", upstream)
        sha = git(self.integration, "rev-parse", "HEAD")
        git(self.source, "init", "--bare", str(self.remote))
        git(self.source, "remote", "add", "origin", str(self.remote))
        git(self.source, "push", "origin", "main", "custom/main")
        self.c = {"Repo": str(self.integration), "SourceRepo": str(self.source),
                  "NewTag": "v1.7.2.2", "Sha": sha, "UpstreamSha": upstream,
                  "OldMain": base, "OldCustom": custom, "AuthorizeRelease": True}
        self.real_ops_git = OPS.git

    def local_boundary(self, c, *args):
        # Only URL validation is injected; all ref reads, tags, pushes and
        # bookkeeping use Git against the isolated on-disk fixture.
        if args[:2] == ("remote", "get-url"):
            return "https://github.com/deefery/workbuddy2api-hub.git"
        return self.real_ops_git(c, *args)

    def remote_ref(self, ref):
        return git(self.remote, "rev-parse", ref)

    def test_failed_push_same_sha_tag_retries_without_rewriting_identity(self):
        def reject(c, *args):
            if args[0] == "push":
                raise RuntimeError("injected remote failure")
            return self.local_boundary(c, *args)
        with patch.object(OPS, "git", side_effect=reject):
            with self.assertRaises(RuntimeError):
                OPS.execute("GIT_PUSH", self.c)
        self.assertEqual(git(self.integration, "rev-parse", "refs/tags/"+self.c["NewTag"]), self.c["Sha"])
        self.assertEqual(self.remote_ref("refs/heads/main"), self.c["OldMain"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])
            self.assertFalse(any(x.args[1:2] == ("tag",) and "--list" not in x.args for x in calls.call_args_list))
            push = next(x.args for x in calls.call_args_list if x.args[1] == "push")
            self.assertIn("--atomic", push)
        self.assertEqual(self.remote_ref("refs/tags/"+self.c["NewTag"]), self.c["Sha"])

    def test_remote_advanced_local_pending_recovers_without_another_push(self):
        def fail_local(c, *args):
            if args[:2] == ("update-ref", "refs/heads/main"):
                raise RuntimeError("injected late bookkeeping failure")
            return self.local_boundary(c, *args)
        with patch.object(OPS, "git", side_effect=fail_local):
            result = OPS.execute("GIT_PUSH", self.c)
        self.assertEqual(result, {"Success": False, "GitPushStatus": "REMOTE_VERIFIED_LOCAL_PENDING"})
        self.assertEqual(self.remote_ref("refs/heads/main"), self.c["UpstreamSha"])
        self.assertEqual(self.remote_ref("refs/heads/custom/main"), self.c["Sha"])
        self.assertEqual(git(self.source, "rev-parse", "main"), self.c["OldMain"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])
            self.assertFalse(any(x.args[1] == "push" for x in calls.call_args_list))
        self.assertEqual(git(self.source, "rev-parse", "main"), self.c["UpstreamSha"])
        self.assertEqual(git(self.source, "rev-parse", "custom/main"), self.c["Sha"])
        self.assertEqual(git(self.source, "status", "--porcelain"), "")
        with patch.object(OPS, "git", side_effect=self.local_boundary):
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])

    def test_lost_push_response_is_reconciled_from_actual_remote_refs(self):
        def lost(c, *args):
            value = self.local_boundary(c, *args)
            if args[0] == "push":
                raise RuntimeError("push response lost")
            return value
        with patch.object(OPS, "git", side_effect=lost):
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])
        self.assertEqual(self.remote_ref("refs/tags/"+self.c["NewTag"]), self.c["Sha"])

    def test_mismatched_local_tag_is_never_deleted_or_pushed(self):
        git(self.integration, "tag", self.c["NewTag"], self.c["OldMain"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            with self.assertRaises(RuntimeError):
                OPS.execute("GIT_PUSH", self.c)
            self.assertFalse(any(x.args[1] == "push" for x in calls.call_args_list))
        self.assertEqual(git(self.integration, "rev-parse", "refs/tags/"+self.c["NewTag"]), self.c["OldMain"])

    def test_mismatched_remote_tag_or_partial_refs_stop_before_mutation(self):
        tag = "refs/tags/"+self.c["NewTag"]
        git(self.remote, "update-ref", tag, self.c["OldMain"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            with self.assertRaises(RuntimeError):
                OPS.execute("GIT_PUSH", self.c)
            self.assertFalse(any(x.args[1] in {"push", "tag"} for x in calls.call_args_list))
        self.assertEqual(self.remote_ref(tag), self.c["OldMain"])
        # A different fixture state with only one branch advanced is not an atomic success.
        git(self.remote, "update-ref", "-d", tag)
        git(self.source, "push", "origin", self.c["UpstreamSha"]+":refs/heads/main")
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            with self.assertRaises(RuntimeError):
                OPS.execute("GIT_PUSH", self.c)
            self.assertFalse(any(x.args[1] in {"push", "tag"} for x in calls.call_args_list))

    def test_fetch_push_destination_difference_fails_before_any_ref_mutation(self):
        def different(c, *args):
            if args == ("remote", "get-url", "origin"):
                return "https://github.com/unexpected/other.git"
            return self.local_boundary(c, *args)
        with patch.object(OPS, "git", side_effect=different) as calls:
            with self.assertRaises(RuntimeError):
                OPS.execute("GIT_PUSH", self.c)
            self.assertFalse(any(x.args[1] in {"tag", "push", "update-ref"} for x in calls.call_args_list))


    def test_local_ref_mismatch_after_verified_push_requires_manual_recovery(self):
        with patch.object(OPS, "git", side_effect=self.local_boundary):
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])
        git(self.source, "update-ref", "refs/heads/main", self.c["OldCustom"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            result = OPS.execute("GIT_PUSH", self.c)
            self.assertEqual(result["GitPushStatus"], "REMOTE_VERIFIED_LOCAL_PENDING")
            self.assertFalse(any(x.args[1] == "push" for x in calls.call_args_list))
        self.assertEqual(git(self.source, "rev-parse", "main"), self.c["OldCustom"])

    def test_same_sha_remote_tag_allows_original_refs_retry(self):
        git(self.integration, "tag", self.c["NewTag"], self.c["Sha"])
        git(self.integration, "push", "origin", self.c["NewTag"])
        with patch.object(OPS, "git", side_effect=self.local_boundary) as calls:
            self.assertTrue(OPS.execute("GIT_PUSH", self.c)["Success"])
            push = next(x.args for x in calls.call_args_list if x.args[1] == "push")
            self.assertFalse(any("refs/tags/" in arg for arg in push[1:]))


if __name__ == "__main__":
    unittest.main()
