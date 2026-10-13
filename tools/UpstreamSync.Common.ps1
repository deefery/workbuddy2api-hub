# UTF-8 with BOM
<#
.SYNOPSIS
    WorkBuddy2API-Hub Upstream Sync & Safe Auto-Deploy Common Library (T-007)
.DESCRIPTION
    Shared logic for upstream drift detection, risk assessment, fail-closed version
    derivation, isolated Git branch integration, test execution (focused + full suite),
    draft-first GitHub release verification, GHCR checks, safe NAS deployment with rollback,
    and structured audit evidence generation.
#>

function Invoke-SyncProcess {
    param([string]$Executable, [string[]]$Arguments, [string]$Repo, [string]$InputText)
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    $info.WorkingDirectory = $Repo
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.RedirectStandardInput = $true
    $info.Arguments = ($Arguments | ForEach-Object {
        '"' + ([regex]::Replace(([regex]::Replace($_, '(\\*)"', '$1$1\"')), '(\\+)$', '$1$1')) + '"'
    }) -join ' '
    $process = [System.Diagnostics.Process]::Start($info)
    $outTask = $process.StandardOutput.ReadToEndAsync()
    $errTask = $process.StandardError.ReadToEndAsync()
    if ($InputText) { $process.StandardInput.Write($InputText) }
    $process.StandardInput.Close()
    $process.WaitForExit()
    [PSCustomObject]@{ ExitCode = $process.ExitCode; StdOut = $outTask.Result.TrimEnd(); StdErr = $errTask.Result.TrimEnd() }
}
function Get-GitCommandOutput {
    param([string]$Repo, [string[]]$Arguments)
    Invoke-SyncProcess -Executable 'git' -Repo $Repo -Arguments (@('-c', 'safe.directory=*') + $Arguments)
}
function Get-SyncGitContext {
    param([Parameter(Mandatory=$true)][string]$Repo)
    $statusRes = Get-GitCommandOutput -Repo $Repo -Arguments @("status", "--porcelain")
    $branchRes = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $headRes   = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", "HEAD")
    $remoteRes = Get-GitCommandOutput -Repo $Repo -Arguments @("remote")

    $dirtyLines = @()
    if ($statusRes.StdOut.Length -gt 0) {
        $dirtyLines = @($statusRes.StdOut -split '\r?\n' | Where-Object { $_ -match '\S' })
    }

    foreach ($r in @($statusRes, $branchRes, $headRes, $remoteRes)) { if ($r.ExitCode -ne 0) { throw 'STOP: Git inspection failed' } }
    $remotes = @($remoteRes.StdOut -split '\r?\n' | ForEach-Object { $_.Trim() })
    return [PSCustomObject]@{
        IsClean      = ($dirtyLines.Count -eq 0)
        DirtyFiles   = $dirtyLines
        Branch       = $branchRes.StdOut.Trim()
        HeadSha      = $headRes.StdOut.Trim()
        HasOrigin    = ($remotes -contains "origin")
        HasUpstream  = ($remotes -contains "upstream")
    }
}

function Invoke-SafeFetch {
    param([Parameter(Mandatory=$true)][string]$Repo)
    $originRes   = Get-GitCommandOutput -Repo $Repo -Arguments @("fetch", "origin")
    $upstreamRes = Get-GitCommandOutput -Repo $Repo -Arguments @("fetch", "upstream")
    return [PSCustomObject]@{
        OriginSuccess   = ($originRes.ExitCode -eq 0)
        OriginError     = $originRes.StdErr
        UpstreamSuccess = ($upstreamRes.ExitCode -eq 0)
        UpstreamError   = $upstreamRes.StdErr
    }
}

function Get-UpstreamDeltaSummary {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [string]$ForkBaseRef = "origin/main",
        [string]$UpstreamRef = "upstream/main"
    )
    $forkShaRes = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", $ForkBaseRef)
    $upShaRes   = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", $UpstreamRef)

    if ($forkShaRes.ExitCode -ne 0 -or $upShaRes.ExitCode -ne 0) {
        throw "Failed to resolve refs for delta inspection: $ForkBaseRef or $UpstreamRef"
    }

    $forkSha = $forkShaRes.StdOut.Trim()
    $upSha   = $upShaRes.StdOut.Trim()

    $mbRes = Get-GitCommandOutput -Repo $Repo -Arguments @("merge-base", $ForkBaseRef, $UpstreamRef)
    $mbSha = if ($mbRes.ExitCode -eq 0) { $mbRes.StdOut.Trim() } else { "" }

    $logRes = Get-GitCommandOutput -Repo $Repo -Arguments @("log", "--oneline", "$ForkBaseRef..$UpstreamRef")
    $commits = @()
    if ($logRes.StdOut.Length -gt 0) {
        $commits = $logRes.StdOut -split "`r?`n" | Where-Object { $_ -match '\S' }
    }

    $revListDiverge = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-list", "--left-right", "--count", "$ForkBaseRef...$UpstreamRef")
    $ahead = 0
    $behind = 0
    if ($revListDiverge.ExitCode -eq 0 -and $revListDiverge.StdOut -match '(\d+)\s+(\d+)') {
        $ahead  = [int]$Matches[1]
        $behind = [int]$Matches[2]
    }

    return [PSCustomObject]@{
        ForkBaseSha  = $forkSha
        UpstreamSha  = $upSha
        MergeBaseSha = $mbSha
        HasUpdate    = ($commits.Count -gt 0)
        CommitCount  = $commits.Count
        Commits      = $commits
        AheadCount   = $ahead
        BehindCount  = $behind
        IsDivergent  = ($ahead -gt 0 -and $behind -gt 0)
    }
}

function Test-DangerousUpstreamChanges {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [string]$ForkBaseRef = "origin/main",
        [string]$UpstreamRef = "upstream/main"
    )
    $diffFilesRes = Get-GitCommandOutput -Repo $Repo -Arguments @("diff", "--name-only", "$ForkBaseRef...$UpstreamRef")
    $files = @()
    if ($diffFilesRes.StdOut.Length -gt 0) {
        $files = $diffFilesRes.StdOut -split "`r?`n" | Where-Object { $_ -match '\S' }
    }

    if ($diffFilesRes.ExitCode -ne 0) { throw 'STOP: Risk diff failed' }
    $workflowFiles = @($files | Where-Object { $_ -like ".github/workflows/*" -or $_ -like "release/*" -or $_ -like "wrt/*" })
    $deployFiles   = @($files | Where-Object { $_ -like "deploy/*" -or $_ -like "*docker*" -or $_ -like "*compose*" })
    $storageFiles  = @($files | Where-Object { $_ -like "*data*" -or $_ -like "*account*" -or $_ -like "*storage*" -or $_ -like "*settings*" -or $_ -like "*usage*" -or $_ -like "*db*" })

    $requiresManual = ($workflowFiles.Count -gt 0 -or $deployFiles.Count -gt 0 -or $storageFiles.Count -gt 0)
    $riskLevel = "LOW"
    if ($workflowFiles.Count -gt 0 -or $storageFiles.Count -gt 0) {
        $riskLevel = "HIGH"
    } elseif ($deployFiles.Count -gt 0) {
        $riskLevel = "MEDIUM"
    }

    return [PSCustomObject]@{
        AllChangedFiles     = $files
        WorkflowChanges     = @($workflowFiles)
        DeployChanges       = @($deployFiles)
        StorageChanges      = @($storageFiles)
        RequiresManualReview= $requiresManual
        RiskLevel           = $riskLevel
    }
}

function Assert-SyncGit {
    param([string]$Repo, [string[]]$Arguments)
    $r = Get-GitCommandOutput -Repo $Repo -Arguments $Arguments
    if ($r.ExitCode -ne 0) { throw "STOP: Git $($Arguments[0]) failed" }
    $r.StdOut
}
function Read-ExactVersion {
    param([string]$Content, [switch]$Upstream)
    $s = [regex]::Matches($Content, 'server_version\s*=\s*"wb-proxy/([^"]+)"')
    $o = [regex]::Matches($Content, '"version"\s*:\s*"([^"]+)"')
    if ($s.Count -ne 1 -or $o.Count -ne 1 -or $s[0].Groups[1].Value -cne $o[0].Groups[1].Value) {
        throw 'STOP: Missing, ambiguous or disagreeing source versions'
    }
    $v = $s[0].Groups[1].Value
    $pattern = if ($Upstream) { '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$' } else { '^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$' }
    if ($v -notmatch $pattern) { throw 'STOP: Invalid release version grammar' }
    $v
}
function Get-SourceReleaseVersion {
    param([string]$Repo)
    Read-ExactVersion -Content (Get-Content -LiteralPath (Join-Path $Repo 'wb_proxy.py') -Raw -Encoding UTF8)
}
function Get-UpstreamStableVersion {
    param([string]$Repo, [string]$UpstreamRef = 'upstream/main')
    $c = Assert-SyncGit -Repo $Repo -Arguments @('show', "$($UpstreamRef):wb_proxy.py")
    Read-ExactVersion -Content $c -Upstream
}
function Derive-NextForkVersion {
    param([string]$UpstreamBaseVer, [string]$CurrentForkVer)
    if ($UpstreamBaseVer -notmatch '^\d+\.\d+\.\d+$' -or $CurrentForkVer -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'STOP: Invalid dot-numeric version' }
    $parts = $CurrentForkVer.Split('.')
    $oldBase = ($parts[0..2] -join '.')
    if ([version]$UpstreamBaseVer -lt [version]$oldBase) { throw 'STOP: Upstream version goes backwards' }
    $rev = if ($UpstreamBaseVer -eq $oldBase) { [int]$parts[3] + 1 } else { 1 }
    [PSCustomObject]@{ ProposedForkVersion = "$UpstreamBaseVer.$rev"; ProposedTag = "v$UpstreamBaseVer.$rev" }
}
function Invoke-UpstreamGitIntegration {
    param([string]$Repo, [string]$UpstreamTargetSha, [string]$ProposedVersion, [hashtable]$Evidence)
    $main = Assert-SyncGit -Repo $Repo -Arguments @('rev-parse', 'main')
    $custom = Assert-SyncGit -Repo $Repo -Arguments @('rev-parse', 'custom/main')
    $originMain = Assert-SyncGit -Repo $Repo -Arguments @('rev-parse', 'origin/main')
    $originCustom = Assert-SyncGit -Repo $Repo -Arguments @('rev-parse', 'origin/custom/main')
    if ($main -ne $originMain -or $custom -ne $originCustom) { throw 'STOP: Local/remote branch divergence' }
    Assert-SyncGit -Repo $Repo -Arguments @('merge-base', '--is-ancestor', $main, $UpstreamTargetSha) | Out-Null
    $id = [guid]::NewGuid().ToString('N')
    $branch = "codex/sync-upstream-$ProposedVersion-$id"
    $path = Join-Path $Repo ".ai/runtime/integration-$id"
    $Evidence.integration_path = $path; $Evidence.integration_branch = $branch
    Assert-SyncGit -Repo $Repo -Arguments @('worktree', 'add', '-b', $branch, $path, $custom) | Out-Null
    # Failed worktrees remain intact. Never switch or reset the operator checkout.
    Assert-SyncGit -Repo $path -Arguments @('merge', '--no-ff', '-m', "Integrate upstream $UpstreamTargetSha", $UpstreamTargetSha) | Out-Null
    Assert-SyncGit -Repo $path -Arguments @('merge-base', '--is-ancestor', $UpstreamTargetSha, 'HEAD') | Out-Null
    [PSCustomObject]@{ Repo = $path; SyncBranch = $branch; OldMain = $main; OldCustom = $custom }
}
function Update-ReleaseIdentityFiles {
    param([string]$Repo, [string]$NewVersion)
    if ($NewVersion -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw 'STOP: Invalid fork identity' }
    $proxy = Join-Path $Repo 'wb_proxy.py'
    $mk = Join-Path $Repo 'wrt/openwrt/workbuddy2api/Makefile'
    $s = Get-Content -LiteralPath $proxy -Raw -Encoding UTF8
    $recipe = Get-Content -LiteralPath $mk -Raw -Encoding UTF8
    if ([regex]::Matches($s, 'server_version\s*=\s*"wb-proxy/[^"]+"').Count -ne 1 -or
        [regex]::Matches($s, '"version"\s*:\s*"[^"]+"').Count -ne 1 -or
        [regex]::Matches($recipe, '(?m)^PKG_VERSION:=[^\r\n]+').Count -ne 1) { throw 'STOP: Identity points missing or ambiguous' }
    $s = [regex]::Replace($s, 'server_version\s*=\s*"wb-proxy/[^"]+"', "server_version = ""wb-proxy/$NewVersion""")
    $s = [regex]::Replace($s, '"version"\s*:\s*"[^"]+"', """version"": ""$NewVersion""")
    $recipe = [regex]::Replace($recipe, '(?m)^PKG_VERSION:=[^\r\n]+', "PKG_VERSION:=$NewVersion")
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($proxy, $s, $utf8)
    [IO.File]::WriteAllText($mk, $recipe, $utf8)
    if ((Get-SourceReleaseVersion -Repo $Repo) -ne $NewVersion) { throw 'STOP: Version equality failed' }
}
function Test-T008DualNetworkConfig {
    param([string]$Repo)
    $path = Join-Path $Repo 'deploy/nas/docker-compose.yml'
    if (-not (Test-Path $path)) { return [PSCustomObject]@{ IsValid = $false; Reason = 'Compose missing' } }
    $c = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $valid = $c -match '(?ms)^services:\s*\r?\n  wb-proxy:\s*\r?\n(?:(?!^  \S|^networks:).)*?    networks:\s*\r?\n      - default\s*\r?\n      - sub2api(?:\s*\r?\n|$)' -and
        $c -match '(?m)^networks:\s*\r?\n  sub2api:\s*\r?\n    external: true\s*\r?\n    name: sub2api_sub2api-network\s*$'
    [PSCustomObject]@{ IsValid = [bool]$valid; Reason = 'Requires wb-proxy default + external sub2api network' }
}
function Get-SyncPython {
    param([string]$PythonExe)
    if ($PythonExe) { return $PythonExe }
    if ($env:WB_SYNC_PYTHON) { return $env:WB_SYNC_PYTHON }
    $bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path $bundled) { return $bundled }
    'python'
}
function Invoke-FullTestSuiteGate {
    param([string]$Repo, [string]$PythonExe, [hashtable]$Evidence)
    $python = Get-SyncPython $PythonExe
    $logs = Join-Path $Repo '.ai/runtime/tests'
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $focused = Invoke-SyncProcess -Executable $python -Repo $Repo -Arguments @('tests/_test_release_engineering.py')
    [IO.File]::WriteAllText((Join-Path $logs 'focused.log'), ($focused.StdOut + [Environment]::NewLine + $focused.StdErr))
    $full = Invoke-SyncProcess -Executable $python -Repo $Repo -Arguments @('tests/run_all.py', '--jobs', '4', '--logs', $logs)
    [IO.File]::WriteAllText((Join-Path $logs 'full.log'), ($full.StdOut + [Environment]::NewLine + $full.StdErr))
    $Evidence.focused_exit = $focused.ExitCode; $Evidence.full_exit = $full.ExitCode; $Evidence.test_logs = $logs
    [PSCustomObject]@{ Success = ($focused.ExitCode -eq 0 -and ($focused.StdOut + $focused.StdErr) -match '(?m)^Ran [1-9]\d* tests?' -and $full.ExitCode -eq 0 -and $full.StdOut -match '(?m)^\s*[1-9]\d* passed, 0 failed, 0 skipped\b'); FocusedExit = $focused.ExitCode; FullExit = $full.ExitCode }
}
function Invoke-LiveExternalOperation {
    param([string]$Action, [hashtable]$Context)
    $r = Invoke-SyncProcess -Executable (Get-SyncPython $Context.PythonExe) -Repo $Context.Repo -Arguments @((Join-Path $PSScriptRoot 'upstream_ops.py'), $Action) -InputText ($Context | ConvertTo-Json -Depth 5 -Compress)
    if ($r.ExitCode -ne 0) { throw "STOP: External action $Action failed (details suppressed)" }
    try { $r.StdOut | ConvertFrom-Json } catch { throw "STOP: Invalid response from $Action" }
}

function Invoke-ProductionGates {
    param([hashtable]$Context, [hashtable]$Evidence, [scriptblock]$ExternalExecutor)
    $executor = if ($ExternalExecutor) { $ExternalExecutor } else { (Get-Command Invoke-LiveExternalOperation).ScriptBlock }
    if (-not $Context.AuthorizeRelease) { throw 'STOP: Release authorization required before push/tag' }
    $mutation = $false
    try {
        foreach ($action in @('GIT_PUSH', 'DRAFT_RELEASE_VERIFY', 'RELEASE_PUBLISH', 'GHCR_VERIFY')) {
            if ($action -eq 'GIT_PUSH' -and $Context.ResumeRelease) { continue }
            $Evidence.last_gate = $action
            if ($action -eq 'GIT_PUSH') { $Evidence.git_push_status = 'ATTEMPTED' }
            $r = & $executor $action $Context
            if (-not $r.Success) { throw "STOP: $action failed" }
            if ($action -eq 'GIT_PUSH') { $Evidence.git_push_status = 'VERIFIED' }
            if ($action -eq 'DRAFT_RELEASE_VERIFY' -and (-not $r.Draft -or -not $r.AssetsVerified)) { throw 'STOP: Draft/assets verification failed' }
            if ($action -eq 'DRAFT_RELEASE_VERIFY' -and $Context.ReviewedDraftTag -cne $Context.NewTag) {
                $Evidence.status = 'DRAFT_READY_AWAITING_REVIEW'; return
            }
            if ($action -eq 'RELEASE_PUBLISH') { $Evidence.publishes_release = $true }
            if ($action -eq 'RELEASE_PUBLISH' -and -not $r.Published) { throw 'STOP: Release not published' }
            if ($action -eq 'GHCR_VERIFY') {
                if ($r.Digest -notmatch '^sha256:[a-f0-9]{64}$' -or -not $r.MultiArch) { throw 'STOP: GHCR identity/platforms failed' }
                $Context.Digest = $r.Digest; $Evidence.ghcr_digest = $r.Digest
            }
        }
        if ($Context.SkipNasDeploy) { $Evidence.status = 'RELEASE_PUBLISHED_NAS_SKIPPED'; return }
        if (-not $Context.AuthorizeNas -or $Context.StateCompatibilitySha -cne $Context.UpstreamSha) {
            throw 'STOP: NAS authorization and exact reviewed state compatibility required'
        }
        $Evidence.mutates_nas = $true; $Evidence.final_health = 'UNKNOWN'
        $Evidence.last_gate = 'NAS_PREFLIGHT_AND_SNAPSHOT'
        $r = & $executor 'NAS_PREFLIGHT_AND_SNAPSHOT' $Context
        if (-not $r.Success -or $r.PreviousTag -notmatch '^v\d+\.\d+\.\d+\.\d+$' -or
            $r.PreviousDigest -notmatch '^sha256:[a-f0-9]{64}$' -or -not $r.SnapshotPath -or $r.AccountsReady -lt 1) { throw 'STOP: NAS snapshot/preflight failed' }
        $Context.PreviousTag = $r.PreviousTag; $Context.PreviousDigest = $r.PreviousDigest
        $Context.SnapshotPath = $r.SnapshotPath; $Context.AccountsReady = $r.AccountsReady
        $Evidence.previous_nas_tag = $r.PreviousTag; $Evidence.previous_nas_digest = $r.PreviousDigest
        $Evidence.snapshot_path = $r.SnapshotPath
        $mutation = $true
        $Evidence.mutates_nas = $true; $Evidence.new_nas_tag = $Context.NewTag; $Evidence.final_health = 'UNKNOWN'
        foreach ($action in @('NAS_DEPLOY_TAG', 'NAS_VERIFY', 'NAS_AUTHENTICATED_SMOKE')) {
            $Evidence.last_gate = $action
            $r = & $executor $action $Context
            if (-not $r.Success) { throw "STOP: $action failed" }
            if ($action -eq 'NAS_VERIFY' -and (-not $r.Healthy -or -not $r.NetworkOk -or
                $r.AccountsReady -lt $Context.AccountsReady -or $r.Digest -cne $Context.Digest)) { throw 'STOP: NAS health/accounts/network/digest failed' }
            if ($action -eq 'NAS_AUTHENTICATED_SMOKE' -and -not $r.SmokePassed) { throw 'STOP: Authenticated API smoke failed' }
        }
        $Evidence.new_nas_tag = $Context.NewTag; $Evidence.final_health = 'HEALTHY'; $Evidence.status = 'SUCCESS'
    } catch {
        if ($mutation) {
            $Evidence.rollback_status = 'ATTEMPTED'
            try {
                $rb = & $executor 'NAS_ROLLBACK' $Context
                if (-not $rb.Success -or -not $rb.Healthy -or -not $rb.SmokePassed -or -not $rb.NetworkOk -or
                    $rb.RestoredTag -cne $Context.PreviousTag -or $rb.Digest -cne $Context.PreviousDigest -or
                    $rb.AccountsReady -lt $Context.AccountsReady) { throw 'Rollback verification failed' }
                $Evidence.rollback_status = 'VERIFIED'; $Evidence.final_health = 'HEALTHY_PREVIOUS'; $Evidence.status = 'ROLLED_BACK'
            } catch {
                $Evidence.rollback_status = 'FAILED_REQUIRES_MANUAL_RECOVERY'; $Evidence.final_health = 'UNKNOWN'; $Evidence.status = 'ROLLBACK_FAILED'
            }
        }
        throw
    }
}
function Write-SyncAuditEvidence {
    param([string]$Repo, [hashtable]$EvidenceData)
    $dir = Join-Path $Repo '.ai/runtime'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $allowed = @('mode','timestamp','status','stop_reason','last_gate','head_sha','old_upstream_sha','new_upstream_sha',
        'upstream_version','current_fork_version','fork_version','fork_tag','ghcr_digest','previous_nas_tag','new_nas_tag',
        'previous_nas_digest','final_health','rollback_status','snapshot_path','integration_path','integration_branch',
        'integration_sha','workspace_clean','has_update','risk_level','t008_dual_network','focused_exit','full_exit',
        'test_logs','mutates_nas','publishes_release','git_push_status')
    $safe = @{}
    foreach ($key in $allowed) { if ($EvidenceData.ContainsKey($key)) { $safe[$key] = $EvidenceData[$key] } }
    $path = Join-Path $dir ("sync-$($EvidenceData.mode)-$([guid]::NewGuid().ToString('N')).json")
    [IO.File]::WriteAllText($path, ($safe | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
    $path
}

