"""T-007 live external boundary. No successful stub defaults; stdlib only.

Called by PowerShell with JSON context on stdin. Credentials stay in gh/ssh
stores or NAS-mounted settings; command output/errors are never echoed.
"""
import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

IMAGE = "ghcr.io/deefery/workbuddy2api-hub"
GITHUB_REPO = "deefery/workbuddy2api-hub"
TAG_RE = re.compile(r"v\d+\.\d+\.\d+\.\d+")
DIGEST_RE = re.compile(r"sha256:[a-f0-9]{64}")


def run(argv, *, cwd=None, stdin=None):
    p = subprocess.run(argv, cwd=cwd, input=stdin, text=True, encoding="utf-8",
                       capture_output=True, timeout=180)
    if p.returncode:
        raise RuntimeError("External command failed; output suppressed")
    return p.stdout


def git(c, *args):
    return run(["git", "-c", "safe.directory=*", *args], cwd=c["Repo"]).strip()


def api(path):
    return json.loads(run(["gh", "api", f"repos/{GITHUB_REPO}/{path}"]))


def wait_workflow(c, filename, event):
    # Exact SHA, workflow and event; failed/missing runs never authorize success.
    for _ in range(180):
        runs = api(f"actions/workflows/{filename}/runs?head_sha={c['Sha']}&per_page=100")["workflow_runs"]
        exact = [r for r in runs if r["head_sha"] == c["Sha"] and r["event"] == event
                 and r.get("head_branch") == c["NewTag"]]
        if exact:
            r = max(exact, key=lambda r: r["id"])
            if r["status"] == "completed":
                if r["conclusion"] != "success":
                    raise RuntimeError("Workflow failed")
                return r
        time.sleep(10)
    raise RuntimeError("Workflow timed out")


def view_release(c):
    return json.loads(run(["gh", "release", "view", c["NewTag"], "--repo", GITHUB_REPO,
                          "--json", "id,isDraft,isPrerelease,tagName,assets"]))


def verify_assets(c, release):
    v = c["NewTag"][1:]
    recipe = (Path(c["Repo"]) / "wrt/openwrt/workbuddy2api/Makefile").read_text()
    m = re.findall(r"^PKG_RELEASE:=(\d+)$", recipe, re.M)
    if len(m) != 1:
        raise RuntimeError("Unknown package release")
    names = {f"workbuddy2api-hub-v{v}.zip", f"workbuddy2api_{v}-{m[0]}_all.ipk",
             f"workbuddy2api-{v}-r{m[0]}.apk", "SHA256SUMS"}
    if {a["name"] for a in release["assets"]} != names:
        raise RuntimeError("Asset identity mismatch")
    dest = Path(c["Repo"]) / ".ai/runtime/release-assets"
    dest.mkdir(parents=True, exist_ok=True)
    run(["gh", "release", "download", c["NewTag"], "--repo", GITHUB_REPO,
         "--dir", str(dest), "--clobber"])
    hashes = {}
    for line in (dest / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  (\S+)", line)
        if not match or match[2] in hashes or match[2] not in names - {"SHA256SUMS"}:
            raise RuntimeError("Invalid checksum manifest")
        hashes[match[2]] = match[1]
    if set(hashes) != names - {"SHA256SUMS"}:
        raise RuntimeError("Incomplete checksum manifest")
    for name, digest in hashes.items():
        with (dest / name).open("rb") as f:
            h = hashlib.sha256()
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        if h.hexdigest() != digest:
            raise RuntimeError("Asset hash mismatch")
    # CI performed package content/runtime verification; insist its exact run passed.
    return True


def ssh(c, script):
    host = c.get("TargetNasHost") or ""
    directory = c.get("NasDirectory") or ""
    if not re.fullmatch(r"(?:[a-zA-Z0-9_.-]+@)?[a-zA-Z0-9_.-]+", host):
        raise RuntimeError("Explicit SSH host/alias required")
    if not re.fullmatch(r"/[a-zA-Z0-9_./-]+", directory) or ".." in directory.split("/"):
        raise RuntimeError("Invalid NAS directory")
    # Payload only through stdin, no passwords in arguments/logs.
    return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "sh", "-s"],
               stdin="set -eu\ncd " + shlex.quote(directory) + "\n" + script)


HEALTH_CODE = """import json,urllib.request
d=json.load(urllib.request.urlopen('http://127.0.0.1:8788/health',timeout=15))
print(json.dumps({'AccountsReady':d.get('accounts_ready',0),'KeyRequired':d.get('api_key_required',False)}))
"""
SMOKE_CODE = """import json,sys,urllib.request
sys.path.insert(0,'/app')
import wb_settings
keys=[k for k in wb_settings.api_keys('/app/accounts') if k.get('enabled') and k.get('key')]
if not keys: raise SystemExit(1)
req=urllib.request.Request('http://127.0.0.1:8788/v1/models',headers={'Authorization':'Bearer '+keys[0]['key']})
d=json.load(urllib.request.urlopen(req,timeout=30))
if not isinstance(d.get('data'),list) or not d['data']: raise SystemExit(1)
# Prove authentication is enforced, not accidentally anonymous.
try: urllib.request.urlopen('http://127.0.0.1:8788/v1/models',timeout=15)
except urllib.error.HTTPError as e:
    if e.code!=401: raise
else: raise SystemExit(1)
print('smoke-ok')
"""


def health(c, expected):
    info = json.loads(ssh(c, "docker inspect wb-proxy\n"))[0]
    if info["State"].get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("Container unhealthy")
    if info["Config"]["Labels"].get("com.docker.compose.project") != "workbuddy2api-hub":
        raise RuntimeError("Unexpected Compose owner")
    networks = info["NetworkSettings"]["Networks"]
    if not {"workbuddy2api-hub_default", "sub2api_sub2api-network"} <= set(networks):
        raise RuntimeError("Dual-network membership lost")
    image = json.loads(ssh(c, "docker image inspect " + shlex.quote(info["Image"]) + "\n"))[0]
    if f"{IMAGE}@{expected}" not in image.get("RepoDigests", []):
        raise RuntimeError("Container RepoDigest mismatch")
    if c.get("Sha") and expected == c.get("Digest"):
        if image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") != c["Sha"]:
            raise RuntimeError("Image revision mismatch")
    status = json.loads(ssh(c, "docker exec wb-proxy python -c " + shlex.quote(HEALTH_CODE) + "\n"))
    if status["AccountsReady"] < c.get("AccountsReady", 1) or not status["KeyRequired"]:
        raise RuntimeError("Account/auth readiness lost")
    return {"Healthy": True, "NetworkOk": True, "AccountsReady": status["AccountsReady"],
            "Digest": expected}


def await_health(c, expected):
    for _ in range(30):
        try:
            return health(c, expected)
        except RuntimeError:
            time.sleep(5)
    raise RuntimeError("Health/digest/account verification timed out")


def smoke(c):
    if ssh(c, "docker exec wb-proxy python -c " + shlex.quote(SMOKE_CODE) + "\n").strip() != "smoke-ok":
        raise RuntimeError("Authenticated smoke failed")
    return True


def deploy(c, tag, digest):
    if not TAG_RE.fullmatch(tag) or not DIGEST_RE.fullmatch(digest):
        raise RuntimeError("Invalid exact deployment identity")
    # Keep the Compose expression/persistent mounts unchanged; replace one exact env field.
    script = r"""
umask 077
test -d .t007-update-lock
test "$(grep -c '^WB_IMAGE_TAG=' .env)" = 1
docker pull IMAGE_DIGEST >/dev/null 2>&1
docker tag IMAGE_DIGEST TARGET_IMAGE
sed 's/^WB_IMAGE_TAG=.*/WB_IMAGE_TAG=TAG/' .env > .env.t007
chmod 600 .env.t007
mv .env.t007 .env
docker compose config -q >/dev/null 2>&1
docker compose up -d --no-deps --pull never wb-proxy >/dev/null 2>&1
"""
    script = script.replace("IMAGE_DIGEST", shlex.quote(f"{IMAGE}@{digest}"))
    script = script.replace("TARGET_IMAGE", shlex.quote(f"{IMAGE}:{tag}"))
    script = script.replace("=TAG", "=" + tag)
    ssh(c, script)


def execute(action, c):
    if not TAG_RE.fullmatch(c["NewTag"]):
        raise RuntimeError("Invalid tag")
    if action in {"GIT_PUSH", "DRAFT_RELEASE_VERIFY", "RELEASE_PUBLISH", "GHCR_VERIFY"} and not c.get("AuthorizeRelease"):
        raise RuntimeError("Release authorization missing")
    if action.startswith("NAS_") and (not c.get("AuthorizeNas") or c.get("StateCompatibilitySha") != c["UpstreamSha"]):
        raise RuntimeError("NAS/state authorization missing")
    if action == "GIT_PUSH":
        url = git(c, "remote", "get-url", "--push", "origin")
        if url not in {f"https://github.com/{GITHUB_REPO}.git", f"git@github.com:{GITHUB_REPO}.git"}:
            raise RuntimeError("Unexpected release remote")
        if git(c, "rev-parse", "HEAD") != c["Sha"]:
            raise RuntimeError("Integration SHA changed")
        git(c, "merge-base", "--is-ancestor", c["OldCustom"], c["Sha"])
        git(c, "merge-base", "--is-ancestor", c["OldMain"], c["UpstreamSha"])
        occupied = git(c, "worktree", "list", "--porcelain")
        if "branch refs/heads/main" in occupied:
            raise RuntimeError("main is checked out; cannot advance its ref safely")
        git(c, "tag", c["NewTag"], c["Sha"])
        # Non-forced, atomic, exact expected remote heads; neither branch can drift.
        git(c, "push", "--atomic", f"--force-with-lease=refs/heads/main:{c['OldMain']}",
            f"--force-with-lease=refs/heads/custom/main:{c['OldCustom']}", "origin",
            f"{c['UpstreamSha']}:refs/heads/main", f"{c['Sha']}:refs/heads/custom/main",
            f"refs/tags/{c['NewTag']}:refs/tags/{c['NewTag']}")
        git(c, "update-ref", "refs/heads/main", c["UpstreamSha"], c["OldMain"])
        source = dict(c, Repo=c["SourceRepo"])
        if git(source, "branch", "--show-current") == "custom/main":
            if git(source, "status", "--porcelain") or git(source, "rev-parse", "HEAD") != c["OldCustom"]:
                raise RuntimeError("Operator checkout changed; reconcile local branch manually")
            git(source, "merge", "--ff-only", c["Sha"])
        return {"Success": True}
    if action == "DRAFT_RELEASE_VERIFY":
        wait_workflow(c, "release.yml", "push")
        release = view_release(c)
        if not release["isDraft"] or release["isPrerelease"] or release["tagName"] != c["NewTag"]:
            raise RuntimeError("Expected stable draft")
        if api(f"git/ref/tags/{c['NewTag']}")["object"]["sha"] != c["Sha"]:
            raise RuntimeError("Remote tag identity changed")
        verify_assets(c, release)
        # Persist immutable review identity for the subsequent boundary process.
        Path(c["Repo"], ".ai/runtime/draft-id").write_text(str(release["id"]))
        return {"Success": True, "Draft": True, "AssetsVerified": True}
    if action == "RELEASE_PUBLISH":
        if not c.get("ResumeRelease") or c.get("ReviewedDraftTag") != c["NewTag"]:
            raise RuntimeError("STOP: Human draft review/publication required; rerun after review")
        release = view_release(c)
        saved = Path(c["Repo"], ".ai/runtime/draft-id").read_text()
        if str(release["id"]) != saved or not release["isDraft"] or release["isPrerelease"]:
            raise RuntimeError("Draft changed")
        verify_assets(c, release)
        run(["gh", "release", "edit", c["NewTag"], "--repo", GITHUB_REPO, "--draft=false"])
        published = view_release(c)
        if published["isDraft"] or published["isPrerelease"]:
            raise RuntimeError("Release not published")
        return {"Success": True, "Published": True}
    if action == "GHCR_VERIFY":
        wait_workflow(c, "docker-publish.yml", "release")
        published = view_release(c)
        if published["isDraft"] or published["isPrerelease"]:
            raise RuntimeError("Published release missing")
        name = f"{IMAGE}:{c['NewTag']}"
        manifest = json.loads(run(["docker", "buildx", "imagetools", "inspect", name, "--raw"]))
        platforms = {(m["platform"]["os"], m["platform"]["architecture"]) for m in manifest["manifests"]}
        if not {("linux", "amd64"), ("linux", "arm64")} <= platforms:
            raise RuntimeError("Required platforms missing")
        display = run(["docker", "buildx", "imagetools", "inspect", name])
        matches = re.findall(r"^Digest:\s+(sha256:[a-f0-9]{64})\s*$", display, re.M)
        if len(matches) != 1:
            raise RuntimeError("Immutable digest unresolved")
        # Read by the immutable index too, ruling out a moving tag between calls.
        frozen = json.loads(run(["docker", "buildx", "imagetools", "inspect", f"{IMAGE}@{matches[0]}", "--raw"]))
        if frozen != manifest:
            raise RuntimeError("Image tag changed during verification")
        return {"Success": True, "Digest": matches[0], "MultiArch": True}
    if action == "NAS_PREFLIGHT_AND_SNAPSHOT":
        previous = ssh(c, "sed -n 's/^WB_IMAGE_TAG=//p' .env\n").strip()
        if not TAG_RE.fullmatch(previous):
            raise RuntimeError("Previous tag unresolved")
        info = json.loads(ssh(c, "docker inspect wb-proxy\n"))[0]
        image = json.loads(ssh(c, "docker image inspect " + shlex.quote(info["Image"]) + "\n"))[0]
        digests = [d.split("@")[1] for d in image.get("RepoDigests", []) if d.startswith(IMAGE + "@")]
        if len(digests) != 1 or info["Config"]["Image"] != f"{IMAGE}:{previous}":
            raise RuntimeError("Previous image identity unresolved")
        baseline = health(c, digests[0])
        smoke(c)
        snapshot = "backups/t007-" + c["NewTag"] + "-" + str(time.time_ns())
        ssh(c, r"""
umask 077
mkdir .t007-update-lock
snapshot=SNAPSHOT
resume() { docker start wb-proxy >/dev/null 2>&1 || return 1; }
trap 'resume; rmdir .t007-update-lock' 0 1 2 3 15
docker stop wb-proxy >/dev/null 2>&1
if ! (mkdir "$snapshot" && cp -p .env docker-compose.yml "$snapshot/" &&
      tar -cf "$snapshot/state.tar" data/accounts data/usage &&
      tar -tf "$snapshot/state.tar" >/dev/null &&
      sha256sum "$snapshot/.env" "$snapshot/docker-compose.yml" "$snapshot/state.tar" > "$snapshot/SHA256SUMS"); then
  resume; rmdir .t007-update-lock; exit 1
fi
resume
trap - 0 1 2 3 15
""".replace("SNAPSHOT", shlex.quote(snapshot)))
        await_health(c, digests[0])
        # Snapshot succeeded and the prior container was resumed; retain lock until final smoke/rollback.
        return {"Success": True, "PreviousTag": previous, "PreviousDigest": digests[0],
                "SnapshotPath": c["NasDirectory"] + "/" + snapshot, "AccountsReady": baseline["AccountsReady"]}
    if action == "NAS_DEPLOY_TAG":
        deploy(c, c["NewTag"], c["Digest"])
        return {"Success": True}
    if action == "NAS_VERIFY":
        return {"Success": True, **await_health(c, c["Digest"])}
    if action == "NAS_AUTHENTICATED_SMOKE":
        smoke(c)
        ssh(c, "rmdir .t007-update-lock\n")
        return {"Success": True, "SmokePassed": True}
    if action == "NAS_ROLLBACK":
        deploy(c, c["PreviousTag"], c["PreviousDigest"])
        status = await_health(c, c["PreviousDigest"])
        smoke(c)
        ssh(c, "rmdir .t007-update-lock\n")
        return {"Success": True, "RestoredTag": c["PreviousTag"], "SmokePassed": True, **status}
    raise RuntimeError("Unknown external operation")


if __name__ == "__main__":
    try:
        print(json.dumps(execute(sys.argv[1], json.load(sys.stdin))))
    except Exception:
        # Never print credentials, settings or a potentially secret-bearing subprocess exception.
        print(json.dumps({"Success": False, "Error": "External gate failed; inspect operator tools securely"}))
        sys.exit(1)
