"""T-007 live external boundary. No successful stub defaults; stdlib only.

Called by PowerShell with JSON context on stdin. Credentials stay in gh/ssh
stores or NAS-mounted settings; command output/errors are never echoed.
"""
import hashlib
import json
import urllib.request
import urllib.error
import urllib.parse
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


class ExternalGateError(RuntimeError):
    def __init__(self, reason, message=None):
        super().__init__(message or f"External gate failed ({reason})")
        self.reason = reason


def read_utf8_text(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        raise ExternalGateError("LOCAL_TEXT_IO_FAILURE", "Local UTF-8 text read failed") from e


def write_utf8_text(path, value):
    try:
        Path(path).write_text(value, encoding="utf-8")
    except (OSError, UnicodeError) as e:
        raise ExternalGateError("LOCAL_TEXT_IO_FAILURE", "Local UTF-8 text write failed") from e


def run(argv, *, cwd=None, stdin=None):
    stdin_bytes = None
    if stdin is not None:
        if isinstance(stdin, str):
            stdin = stdin.replace("\r\n", "\n")
            stdin_bytes = stdin.encode("utf-8")
        else:
            stdin_bytes = stdin
    p = subprocess.run(argv, cwd=cwd, input=stdin_bytes, capture_output=True, timeout=180)
    if p.returncode:
        raise RuntimeError("External command failed; output suppressed")
    return p.stdout.decode("utf-8", errors="replace")


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
    recipe = read_utf8_text(Path(c["Repo"]) / "wrt/openwrt/workbuddy2api/Makefile")
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
    for line in read_utf8_text(dest / "SHA256SUMS").splitlines():
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


REMOTE_DOCKER_PRELUDE = '''if ! command -v docker >/dev/null 2>&1; then
  for candidate in /share/CACHEDEV1_DATA/.qpkg/container-station/bin /share/CACHEDEV1_DATA/.qpkg/container-station/usr/bin; do
    if [ -x "$candidate/docker" ]; then
      PATH="$candidate:$PATH"
      break
    fi
  done
fi
'''


def ssh(c, script, *, reason="SSH_SESSION_FAILURE"):
    host = c.get("TargetNasHost") or ""
    directory = c.get("NasDirectory") or ""
    if not re.fullmatch(r"(?:[a-zA-Z0-9_.-]+@)?[a-zA-Z0-9_.-]+", host):
        raise ExternalGateError("SSH_SESSION_FAILURE", "Explicit SSH host/alias required")
    if not re.fullmatch(r"/[a-zA-Z0-9_./-]+", directory) or ".." in directory.split("/"):
        raise ExternalGateError("SSH_SESSION_FAILURE", "Invalid NAS directory")
    full_script = "set -eu\n" + REMOTE_DOCKER_PRELUDE + "cd " + shlex.quote(directory) + "\n" + script
    try:
        return run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, "sh", "-s"],
                   stdin=full_script)
    except ExternalGateError:
        raise
    except Exception as e:
        raise ExternalGateError(reason, "Remote SSH/session operation failed") from e


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
    info = json.loads(ssh(c, "docker inspect wb-proxy\n", reason="REMOTE_HEALTH_VERIFY_FAILURE"))[0]
    if info["State"].get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("Container unhealthy")
    if info["Config"]["Labels"].get("com.docker.compose.project") != "workbuddy2api-hub":
        raise RuntimeError("Unexpected Compose owner")
    networks = info["NetworkSettings"]["Networks"]
    if not {"workbuddy2api-hub_default", "sub2api_sub2api-network"} <= set(networks):
        raise RuntimeError("Dual-network membership lost")
    image = json.loads(ssh(c, "docker image inspect " + shlex.quote(info["Image"]) + "\n", reason="REMOTE_HEALTH_VERIFY_FAILURE"))[0]
    if f"{IMAGE}@{expected}" not in image.get("RepoDigests", []):
        raise RuntimeError("Container RepoDigest mismatch")
    if c.get("Sha") and expected == c.get("Digest"):
        if image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") != c["Sha"]:
            raise RuntimeError("Image revision mismatch")
    status = json.loads(ssh(c, "docker exec wb-proxy python -c " + shlex.quote(HEALTH_CODE) + "\n", reason="REMOTE_HEALTH_VERIFY_FAILURE"))
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
    if ssh(c, "docker exec wb-proxy python -c " + shlex.quote(SMOKE_CODE) + "\n", reason="AUTHENTICATED_SMOKE_FAILURE").strip() != "smoke-ok":
        raise RuntimeError("Authenticated smoke failed")
    return True


def deploy(c, tag, digest, *, reason="NAS_DEPLOY_FAILURE"):
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
    ssh(c, script, reason=reason)



def remote_push_state(c):
    """Read the push destination itself; tracking refs alone are not evidence."""
    refs = ["refs/heads/main", "refs/heads/custom/main", "refs/tags/" + c["NewTag"]]
    lines = git(c, "ls-remote", "origin", *refs).splitlines()
    found = {}
    for line in lines:
        parts = line.split()
        if len(parts) != 2 or not re.fullmatch(r"[a-f0-9]{40}", parts[0]) or parts[1] not in refs or parts[1] in found:
            raise RuntimeError("Invalid remote ref evidence")
        found[parts[1]] = parts[0]
    tag = found.get(refs[2])
    if tag is not None and tag != c["Sha"]:
        raise RuntimeError("Remote tag identity mismatch")
    if found.get(refs[0]) == c["UpstreamSha"] and found.get(refs[1]) == c["Sha"] and tag == c["Sha"]:
        return "ADVANCED", tag
    if found.get(refs[0]) == c["OldMain"] and found.get(refs[1]) == c["OldCustom"]:
        return "ORIGINAL", tag
    raise RuntimeError("Remote refs differ from original or exact reviewed push")


def reconcile_local_push(c):
    """Idempotent CAS/fast-forward bookkeeping; never reset an occupied checkout."""
    current = git(c, "rev-parse", "refs/heads/main")
    if current not in {c["OldMain"], c["UpstreamSha"]}:
        raise RuntimeError("Local main identity moved")
    if current != c["UpstreamSha"]:
        if "branch refs/heads/main" in git(c, "worktree", "list", "--porcelain"):
            raise RuntimeError("Local main is checked out; manual reconciliation required")
        git(c, "update-ref", "refs/heads/main", c["UpstreamSha"], current)
    source = dict(c, Repo=c["SourceRepo"])
    if git(source, "branch", "--show-current") == "custom/main":
        current = git(source, "rev-parse", "HEAD")
        if current not in {c["OldCustom"], c["Sha"]} or git(source, "status", "--porcelain"):
            raise RuntimeError("Operator checkout changed; reconcile manually")
        if current != c["Sha"]:
            git(source, "merge", "--ff-only", c["Sha"])
    # Refresh only the verified identities, including on recovery with -NoFetch.
    git(c, "update-ref", "refs/remotes/origin/main", c["UpstreamSha"])
    git(c, "update-ref", "refs/remotes/origin/custom/main", c["Sha"])


def push_reviewed_refs(c):
    url = git(c, "remote", "get-url", "--push", "origin")
    if url not in {f"https://github.com/{GITHUB_REPO}.git", f"git@github.com:{GITHUB_REPO}.git"}:
        raise RuntimeError("Unexpected release remote")
    # ls-remote must inspect the same URL that receives the push.
    if git(c, "remote", "get-url", "origin") != url:
        raise RuntimeError("Different fetch/push remotes require manual reconciliation")
    if git(c, "rev-parse", "HEAD") != c["Sha"]:
        raise RuntimeError("Integration SHA changed")
    git(c, "merge-base", "--is-ancestor", c["OldCustom"], c["Sha"])
    git(c, "merge-base", "--is-ancestor", c["OldMain"], c["UpstreamSha"])
    state, remote_tag = remote_push_state(c)
    local_tag = git(c, "tag", "--list", c["NewTag"])
    if local_tag:
        if local_tag != c["NewTag"] or git(c, "rev-parse", "refs/tags/" + c["NewTag"]) != c["Sha"]:
            raise RuntimeError("Local tag identity mismatch")
    else:
        git(c, "tag", c["NewTag"], c["Sha"])
    if state == "ORIGINAL":
        if "branch refs/heads/main" in git(c, "worktree", "list", "--porcelain"):
            raise RuntimeError("main is checked out; cannot advance its ref safely")
        refspecs = [f"{c['UpstreamSha']}:refs/heads/main", f"{c['Sha']}:refs/heads/custom/main"]
        if remote_tag is None:
            refspecs.append(f"refs/tags/{c['NewTag']}:refs/tags/{c['NewTag']}")
        try:
            git(c, "push", "--atomic", f"--force-with-lease=refs/heads/main:{c['OldMain']}",
                f"--force-with-lease=refs/heads/custom/main:{c['OldCustom']}", "origin", *refspecs)
        except RuntimeError:
            # A lost response may follow a successful atomic push. Inspect, never guess.
            if remote_push_state(c)[0] != "ADVANCED":
                raise
        if remote_push_state(c)[0] != "ADVANCED":
            raise RuntimeError("Remote push identities not verified")
    try:
        reconcile_local_push(c)
    except RuntimeError:
        return {"Success": False, "GitPushStatus": "REMOTE_VERIFIED_LOCAL_PENDING"}
    return {"Success": True, "GitPushStatus": "VERIFIED"}


GHCR_REGISTRY_BASE = "https://ghcr.io/v2/deefery/workbuddy2api-hub"
OCI_INDEX_MEDIA = "application/vnd.oci.image.index.v1+json"
DOCKER_MANIFEST_LIST_MEDIA = "application/vnd.docker.distribution.manifest.list.v2+json"
OCI_MANIFEST_MEDIA = "application/vnd.oci.image.manifest.v1+json"
DOCKER_MANIFEST_MEDIA = "application/vnd.docker.distribution.manifest.v2+json"
ACCEPT_MANIFEST_HEADER = f"{OCI_INDEX_MEDIA}, {DOCKER_MANIFEST_LIST_MEDIA}, {OCI_MANIFEST_MEDIA}, {DOCKER_MANIFEST_MEDIA}"


def request_ghcr(path, *, token=None, accept=None):
    url = f"{GHCR_REGISTRY_BASE}/{path.lstrip('/')}"
    headers = {"User-Agent": "workbuddy2api-hub-t007"}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 401 and token is None:
            auth_header = e.headers.get("WWW-Authenticate")
            if not auth_header:
                raise ExternalGateError("GHCR_UNAUTHORIZED", "Registry 401 without challenge header")
            m_realm = re.search(r'realm="([^"]+)"', auth_header)
            m_service = re.search(r'service="([^"]+)"', auth_header)
            m_scope = re.search(r'scope="([^"]+)"', auth_header)
            if not m_realm:
                raise ExternalGateError("GHCR_UNAUTHORIZED", "Registry realm challenge missing")
            token_url = m_realm.group(1)
            params = []
            if m_service:
                params.append(f"service={urllib.parse.quote(m_service.group(1), safe="")}")
            if m_scope:
                params.append(f"scope={urllib.parse.quote(m_scope.group(1), safe="")}")
            if params:
                token_url += ("&" if "?" in token_url else "?") + "&".join(params)
            tok_req = urllib.request.Request(token_url, headers={"User-Agent": "workbuddy2api-hub-t007"})
            try:
                with urllib.request.urlopen(tok_req, timeout=30) as tok_resp:
                    tok_data = json.loads(tok_resp.read().decode("utf-8"))
                    bearer_token = tok_data.get("token") or tok_data.get("access_token")
                    if not bearer_token:
                        raise ExternalGateError("GHCR_TOKEN_FAILURE", "Empty token payload from registry auth")
            except Exception as tok_err:
                if isinstance(tok_err, ExternalGateError):
                    raise
                raise ExternalGateError("GHCR_TOKEN_FAILURE", "Failed to acquire registry bearer token") from tok_err
            return request_ghcr(path, token=bearer_token, accept=accept)
        raise ExternalGateError("GHCR_HTTP_ERROR", f"Registry HTTP error: {e.code}") from e
    except Exception as e:
        raise ExternalGateError("GHCR_NETWORK_ERROR", "Registry network failure") from e


def fetch_ghcr_manifest(reference):
    status, headers, body = request_ghcr(f"manifests/{reference}", accept=ACCEPT_MANIFEST_HEADER)
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    try:
        manifest_obj = json.loads(body.decode("utf-8"))
    except Exception as e:
        raise ExternalGateError("GHCR_MALFORMED_MANIFEST", "Failed to parse registry manifest JSON") from e
    return manifest_obj, digest


def verify_ghcr_reference(reference):
    if not TAG_RE.fullmatch(reference):
        raise ExternalGateError("GHCR_REFERENCE_INVALID", "Registry reference is not an exact release tag")
    manifest_by_tag, computed_tag_digest = fetch_ghcr_manifest(reference)
    manifests = manifest_by_tag.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise ExternalGateError("GHCR_INVALID_MANIFEST", "Registry response is not a multi-arch manifest list")
    platforms = set()
    for m in manifests:
        platform = m.get("platform", {})
        platforms.add((platform.get("os"), platform.get("architecture")))
    if not {("linux", "amd64"), ("linux", "arm64")} <= platforms:
        raise ExternalGateError("GHCR_PLATFORM_MISMATCH", "Required platforms (linux/amd64, linux/arm64) missing")
    if not DIGEST_RE.fullmatch(computed_tag_digest):
        raise ExternalGateError("GHCR_DIGEST_UNRESOLVED", "Immutable digest format unresolved")
    manifest_by_digest, computed_frozen_digest = fetch_ghcr_manifest(computed_tag_digest)
    if computed_frozen_digest != computed_tag_digest or manifest_by_digest != manifest_by_tag:
        raise ExternalGateError("GHCR_MUTABLE_TAG_DETECTED", "Registry tag changed during verification")
    return {"Success": True, "Digest": computed_tag_digest, "MultiArch": True}


def verify_ghcr_image(c):
    return verify_ghcr_reference(c["NewTag"])


def execute(action, c):
    if not TAG_RE.fullmatch(c["NewTag"]):
        raise RuntimeError("Invalid tag")
    if action in {"GIT_PUSH", "DRAFT_RELEASE_VERIFY", "GHCR_CAPABILITY_PREFLIGHT", "RELEASE_PUBLISH", "GHCR_VERIFY"} and not c.get("AuthorizeRelease"):
        raise RuntimeError("Release authorization missing")
    if action.startswith("NAS_") and (not c.get("AuthorizeNas") or c.get("StateCompatibilitySha") != c["UpstreamSha"]):
        raise RuntimeError("NAS/state authorization missing")
    if action == "GIT_PUSH":
        return push_reviewed_refs(c)
    if action == "DRAFT_RELEASE_VERIFY":
        wait_workflow(c, "release.yml", "push")
        release = view_release(c)
        if not release["isDraft"] or release["isPrerelease"] or release["tagName"] != c["NewTag"]:
            raise RuntimeError("Expected stable draft")
        if api(f"git/ref/tags/{c['NewTag']}")["object"]["sha"] != c["Sha"]:
            raise RuntimeError("Remote tag identity changed")
        verify_assets(c, release)
        # Persist immutable review identity for the subsequent boundary process.
        write_utf8_text(Path(c["Repo"], ".ai/runtime/draft-id"), str(release["id"]))
        return {"Success": True, "Draft": True, "AssetsVerified": True}
    if action == "RELEASE_PUBLISH":
        if not c.get("ResumeRelease") or c.get("ReviewedDraftTag") != c["NewTag"]:
            raise RuntimeError("STOP: Human draft review/publication required; rerun after review")
        release = view_release(c)
        saved = read_utf8_text(Path(c["Repo"], ".ai/runtime/draft-id"))
        if str(release["id"]) != saved or not release["isDraft"] or release["isPrerelease"]:
            raise RuntimeError("Draft changed")
        verify_assets(c, release)
        run(["gh", "release", "edit", c["NewTag"], "--repo", GITHUB_REPO, "--draft=false"])
        published = view_release(c)
        if published["isDraft"] or published["isPrerelease"]:
            raise RuntimeError("Release not published")
        return {"Success": True, "Published": True}
    if action == "GHCR_CAPABILITY_PREFLIGHT":
        # Exercise the complete read-only token/manifest/digest path against the currently published fork image.
        current_tag = c.get("CurrentTag") or ""
        result = verify_ghcr_reference(current_tag)
        return {"Success": True, "PreflightPassed": True, "Digest": result["Digest"]}
    if action == "GHCR_VERIFY":
        wait_workflow(c, "docker-publish.yml", "release")
        published = view_release(c)
        if published["isDraft"] or published["isPrerelease"]:
            raise RuntimeError("Published release missing")
        return verify_ghcr_image(c)
    if action == "NAS_PREFLIGHT_AND_SNAPSHOT":
        # Docker/compose capability check before snapshot. Classify this separately from generic SSH failures.
        ssh(c, "docker --version >/dev/null 2>&1 && docker compose version >/dev/null 2>&1\n",
            reason="REMOTE_DOCKER_CAPABILITY_FAILURE")
        previous = ssh(c, "sed -n 's/^WB_IMAGE_TAG=//p' .env\n", reason="NAS_PREFLIGHT_FAILURE").strip()
        if not TAG_RE.fullmatch(previous):
            raise RuntimeError("Previous tag unresolved")
        info = json.loads(ssh(c, "docker inspect wb-proxy\n", reason="REMOTE_HEALTH_VERIFY_FAILURE"))[0]
        image = json.loads(ssh(c, "docker image inspect " + shlex.quote(info["Image"]) + "\n", reason="REMOTE_HEALTH_VERIFY_FAILURE"))[0]
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
""".replace("SNAPSHOT", shlex.quote(snapshot)), reason="NAS_SNAPSHOT_FAILURE")
        await_health(c, digests[0])
        # Snapshot succeeded and the prior container was resumed; retain lock until final smoke/rollback.
        return {"Success": True, "PreviousTag": previous, "PreviousDigest": digests[0],
                "SnapshotPath": c["NasDirectory"] + "/" + snapshot, "AccountsReady": baseline["AccountsReady"]}
    if action == "NAS_DEPLOY_TAG":
        deploy(c, c["NewTag"], c["Digest"], reason="NAS_DEPLOY_FAILURE")
        return {"Success": True}
    if action == "NAS_VERIFY":
        try:
            return {"Success": True, **await_health(c, c["Digest"])}
        except ExternalGateError:
            raise
        except Exception as e:
            raise ExternalGateError("REMOTE_HEALTH_VERIFY_FAILURE", "Remote health verification failed") from e
    if action == "NAS_AUTHENTICATED_SMOKE":
        try:
            smoke(c)
            ssh(c, "rmdir .t007-update-lock\n", reason="AUTHENTICATED_SMOKE_FAILURE")
            return {"Success": True, "SmokePassed": True}
        except ExternalGateError:
            raise
        except Exception as e:
            raise ExternalGateError("AUTHENTICATED_SMOKE_FAILURE", "Authenticated smoke failed") from e
    if action == "NAS_ROLLBACK":
        try:
            deploy(c, c["PreviousTag"], c["PreviousDigest"], reason="NAS_ROLLBACK_FAILURE")
            status = await_health(c, c["PreviousDigest"])
            smoke(c)
            ssh(c, "rmdir .t007-update-lock\n", reason="NAS_ROLLBACK_FAILURE")
            return {"Success": True, "RestoredTag": c["PreviousTag"], "SmokePassed": True, **status}
        except ExternalGateError as e:
            if e.reason == "NAS_ROLLBACK_FAILURE":
                raise
            raise ExternalGateError("NAS_ROLLBACK_FAILURE", "Rollback failed") from e
        except Exception as e:
            raise ExternalGateError("NAS_ROLLBACK_FAILURE", "Rollback failed") from e
    raise RuntimeError("Unknown external operation")


def cli_main(argv=None, stdin=None, stdout=None, stderr=None):
    argv = sys.argv if argv is None else argv
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    try:
        result = execute(argv[1], json.load(stdin))
        print(json.dumps(result), file=stdout)
        return 0
    except ExternalGateError as e:
        print(json.dumps({"Success": False, "Reason": e.reason,
                          "Error": "External gate failed; inspect operator tools securely"}), file=stdout)
        return 1
    except Exception:
        print(json.dumps({"Success": False, "Reason": "UNCLASSIFIED_ERROR",
                          "Error": "External gate failed; inspect operator tools securely"}), file=stdout)
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
