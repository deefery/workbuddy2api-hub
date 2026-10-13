[CmdletBinding()]
param(
    [string]$RepoPath,
    [switch]$DryRun, [switch]$NoFetch, [switch]$Force, [switch]$SkipNasDeploy,
    [switch]$AuthorizeRelease, [switch]$AuthorizeNas,
    [string]$ReviewedUpstreamSha, [string]$ReviewedDraftTag, [string]$StateCompatibilitySha,
    [string]$TargetNasHost, [string]$NasDirectory = '/share/Container/workbuddy2api-hub',
    [string]$PythonExe, [scriptblock]$ExternalExecutor, [string]$ResumeReleaseEvidence
)
if (-not $RepoPath) { $RepoPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/UpstreamSync.Common.ps1"
$e = @{
    mode = $(if ($DryRun) { 'dry-run' } else { 'update' }); timestamp = (Get-Date).ToString('o')
    status = 'STOPPED'; old_upstream_sha = $null; new_upstream_sha = $null
    fork_version = $null; fork_tag = $null; ghcr_digest = $null
    previous_nas_tag = $null; new_nas_tag = $null; final_health = 'NOT_RUN'; rollback_status = 'NOT_NEEDED'
    mutates_nas = $false; publishes_release = $false
}
try {
    $e.last_gate = 'WORKSPACE'
    $g = Get-SyncGitContext -Repo $RepoPath
    $e.workspace_clean = $g.IsClean; $e.head_sha = $g.HeadSha
    if (-not $g.IsClean -and -not $DryRun) { throw 'STOP: Local workspace is DIRTY' }
    if (-not $g.HasOrigin -or -not $g.HasUpstream) { throw 'STOP: Required remotes missing' }
    $e.last_gate = 'FETCH'
    if (-not $NoFetch) {
        $fetch = Invoke-SafeFetch -Repo $RepoPath
        if (-not $fetch.OriginSuccess -or -not $fetch.UpstreamSuccess) { throw 'STOP: Fetch failed; refusing stale refs' }
    }
    if ($ResumeReleaseEvidence) {
        $e.last_gate = 'RESUME_RELEASE'
        $saved = Get-Content -LiteralPath $ResumeReleaseEvidence -Raw -Encoding UTF8 | ConvertFrom-Json
        $repo = [IO.Path]::GetFullPath($saved.integration_path)
        $root = [IO.Path]::GetFullPath((Join-Path $RepoPath '.ai/runtime')) + [IO.Path]::DirectorySeparatorChar
        if (-not $repo.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or
            $saved.fork_tag -notmatch '^v\d+\.\d+\.\d+\.\d+$' -or
            $saved.integration_sha -notmatch '^[a-f0-9]{40}$' -or
            $saved.new_upstream_sha -notmatch '^[a-f0-9]{40}$' -or
            ($saved.status -ne 'DRAFT_READY_AWAITING_REVIEW' -and $saved.last_gate -ne 'RELEASE_PUBLISH')) {
            throw 'STOP: Invalid release continuation evidence'
        }
        if (-not (Get-SyncGitContext -Repo $repo).IsClean) { throw 'STOP: Continuation worktree dirty' }
        if ((Assert-SyncGit -Repo $repo -Arguments @('rev-parse','HEAD')) -ne $saved.integration_sha -or
            (Assert-SyncGit -Repo $RepoPath -Arguments @('rev-parse',"refs/tags/$($saved.fork_tag)")) -ne $saved.integration_sha -or
            (Assert-SyncGit -Repo $RepoPath -Arguments @('rev-parse','origin/custom/main')) -ne $saved.integration_sha -or
            (Assert-SyncGit -Repo $RepoPath -Arguments @('rev-parse','origin/main')) -ne $saved.new_upstream_sha) {
            throw 'STOP: Release continuation identity moved'
        }
        foreach ($key in @('old_upstream_sha','new_upstream_sha','fork_version','fork_tag','integration_path','integration_branch','integration_sha')) {
            $e[$key] = $saved.$key
        }
        if ((Get-SourceReleaseVersion -Repo $repo) -ne $saved.fork_version -or -not (Test-T008DualNetworkConfig -Repo $repo).IsValid) {
            throw 'STOP: Continued source identity/network changed'
        }
        $e.last_gate = 'TESTS'
        if (-not (Invoke-FullTestSuiteGate -Repo $repo -PythonExe $PythonExe -Evidence $e).Success) { throw 'STOP: Continued full tests failed' }
        $context = @{
            Repo = $repo; SourceRepo = $RepoPath; ResumeRelease = $true; Sha = $saved.integration_sha
            UpstreamSha = $saved.new_upstream_sha; NewTag = $saved.fork_tag
            AuthorizeRelease = [bool]$AuthorizeRelease; AuthorizeNas = [bool]$AuthorizeNas
            ReviewedDraftTag = $ReviewedDraftTag; StateCompatibilitySha = $StateCompatibilitySha
            SkipNasDeploy = [bool]$SkipNasDeploy; TargetNasHost = $TargetNasHost; NasDirectory = $NasDirectory; PythonExe = $PythonExe
        }
        Invoke-ProductionGates -Context $context -Evidence $e -ExternalExecutor $ExternalExecutor
        Write-Host $e.status
        return
    }
    $e.last_gate = 'DELTA'
    $d = Get-UpstreamDeltaSummary -Repo $RepoPath
    $e.old_upstream_sha = $d.ForkBaseSha; $e.new_upstream_sha = $d.UpstreamSha; $e.has_update = $d.HasUpdate
    if ($d.IsDivergent) { throw 'STOP: Upstream/main divergence' }
    $e.last_gate = 'VERSION'
    $currentContent = Assert-SyncGit -Repo $RepoPath -Arguments @('show', 'custom/main:wb_proxy.py')
    $current = Read-ExactVersion -Content $currentContent
    $up = Get-UpstreamStableVersion -Repo $RepoPath
    $v = Derive-NextForkVersion -UpstreamBaseVer $up -CurrentForkVer $current
    $e.current_fork_version = $current; $e.upstream_version = $up
    $e.fork_version = $v.ProposedForkVersion; $e.fork_tag = $v.ProposedTag
    if (-not $d.HasUpdate) { $e.status = 'UP_TO_DATE'; return }
    $e.last_gate = 'RISK'
    $risk = Test-DangerousUpstreamChanges -Repo $RepoPath
    $e.risk_level = $risk.RiskLevel
    if ($risk.RequiresManualReview -and $ReviewedUpstreamSha -cne $d.UpstreamSha) {
        throw 'STOP: HIGH-RISK/packaging changes require exact upstream SHA review; -Force cannot bypass'
    }
    $e.last_gate = 'T008'
    $net = Test-T008DualNetworkConfig -Repo $RepoPath
    $e.t008_dual_network = $net.IsValid
    if (-not $net.IsValid) { throw 'STOP: T-008 dual-network invariant failed' }
    if ($DryRun) {
        $e.status = 'DRY_RUN_PLAN_ONLY'
        Write-Host "DRY-RUN PLAN: $($e.fork_tag), upstream $($d.UpstreamSha). Integration/tests/external operations NOT RUN."
        return
    }
    $e.last_gate = 'INTEGRATION'
    $integration = Invoke-UpstreamGitIntegration -Repo $RepoPath -UpstreamTargetSha $d.UpstreamSha -ProposedVersion $e.fork_version -Evidence $e
    $repo = $integration.Repo
    if (-not (Test-T008DualNetworkConfig -Repo $repo).IsValid) { throw 'STOP: Merged T-008 invariant failed' }
    Update-ReleaseIdentityFiles -Repo $repo -NewVersion $e.fork_version
    $e.last_gate = 'TESTS'
    $test = Invoke-FullTestSuiteGate -Repo $repo -PythonExe $PythonExe -Evidence $e
    if (-not $test.Success) { throw 'STOP: Focused/full suite failed or skipped tests; no release mutation' }
    Assert-SyncGit -Repo $repo -Arguments @('add', 'wb_proxy.py', 'wrt/openwrt/workbuddy2api/Makefile') | Out-Null
    Assert-SyncGit -Repo $repo -Arguments @('commit', '-m', "Prepare fork $($e.fork_tag)") | Out-Null
    $sha = Assert-SyncGit -Repo $repo -Arguments @('rev-parse', 'HEAD')
    $e.integration_sha = $sha
    $context = @{
        Repo = $repo; SourceRepo = $RepoPath; ResumeRelease = $false; SyncBranch = $integration.SyncBranch; Sha = $sha; UpstreamSha = $d.UpstreamSha
        OldMain = $integration.OldMain; OldCustom = $integration.OldCustom; NewTag = $e.fork_tag
        AuthorizeRelease = [bool]$AuthorizeRelease; AuthorizeNas = [bool]$AuthorizeNas
        ReviewedDraftTag = $ReviewedDraftTag; StateCompatibilitySha = $StateCompatibilitySha
        SkipNasDeploy = [bool]$SkipNasDeploy; TargetNasHost = $TargetNasHost; NasDirectory = $NasDirectory; PythonExe = $PythonExe
    }
    Invoke-ProductionGates -Context $context -Evidence $e -ExternalExecutor $ExternalExecutor
    Write-Host $e.status
} catch {
    # Never embed arbitrary command output, URLs or secret-bearing exceptions in evidence.
    $e.stop_reason = "Failed at $($e.last_gate); see gate-specific local diagnostics"
    Write-Error ("STOP: " + $e.stop_reason)
} finally {
    $audit = Write-SyncAuditEvidence -Repo $RepoPath -EvidenceData $e
    Write-Host "Audit: $audit"
}
