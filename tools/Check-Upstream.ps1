<#
.SYNOPSIS
    Check-Upstream.ps1 — Read-only upstream drift check (T-007)
.DESCRIPTION
    Safely inspects upstream commits, assesses risk, computes version drift,
    and reports status without mutating tags, releases, or NAS state.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$RepoPath = (Resolve-Path "$PSScriptRoot\..").Path,

    [Parameter(Mandatory=$false)]
    [switch]$NoFetch,

    [Parameter(Mandatory=$false)]
    [switch]$Json
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\UpstreamSync.Common.ps1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " WorkBuddy2API-Hub Upstream Read-Only Check (T-007)       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Inspect Git Context
$gitCtx = Get-SyncGitContext -Repo $RepoPath
Write-Host "[1/6] Workspace Status: " -NoNewline
if ($gitCtx.IsClean) {
    Write-Host "CLEAN" -ForegroundColor Green
} else {
    Write-Host "DIRTY (Warning: working tree has uncommitted changes)" -ForegroundColor Yellow
    foreach ($df in $gitCtx.DirtyFiles) {
        Write-Host "      - $df" -ForegroundColor DarkGray
    }
}
Write-Host "      Current Branch : $($gitCtx.Branch)"
Write-Host "      Current HEAD   : $($gitCtx.HeadSha)"
Write-Host "      Remotes        : origin=$($gitCtx.HasOrigin), upstream=$($gitCtx.HasUpstream)"

if (-not $gitCtx.HasOrigin -or -not $gitCtx.HasUpstream) {
    Write-Error "Missing required remotes: origin and upstream must both be configured."
}

# 2. Safe Fetch
if (-not $NoFetch) {
    Write-Host "[2/6] Fetching remote refs (origin + upstream)... " -NoNewline
    $fetchRes = Invoke-SafeFetch -Repo $RepoPath
    if ($fetchRes.OriginSuccess -and $fetchRes.UpstreamSuccess) {
        Write-Host "DONE" -ForegroundColor Green
    } else {
        Write-Host "WARNING" -ForegroundColor Yellow
        if (-not $fetchRes.OriginSuccess) { Write-Host "      origin fetch failed: $($fetchRes.OriginError)" -ForegroundColor Red }
        if (-not $fetchRes.UpstreamSuccess) { Write-Host "      upstream fetch failed: $($fetchRes.UpstreamError)" -ForegroundColor Red }
    }
} else {
    Write-Host "[2/6] Fetching: SKIPPED (-NoFetch requested)" -ForegroundColor DarkGray
}

# 3. Detect Drift and Delta
Write-Host "[3/6] Analyzing Upstream Delta... "
$delta = Get-UpstreamDeltaSummary -Repo $RepoPath -ForkBaseRef "origin/main" -UpstreamRef "upstream/main"
Write-Host "      origin/main   : $($delta.ForkBaseSha)"
Write-Host "      upstream/main : $($delta.UpstreamSha)"
Write-Host "      merge-base    : $($delta.MergeBaseSha)"

if (-not $delta.HasUpdate) {
    Write-Host "      Status        : UP TO DATE (No upstream commits pending)" -ForegroundColor Green
} else {
    if ($delta.IsDivergent) {
        Write-Host "      Status        : DIVERGENT (origin/main has local commits not in upstream)" -ForegroundColor Yellow
    } else {
        Write-Host "      Status        : DRIFT DETECTED ($($delta.CommitCount) new commits in upstream)" -ForegroundColor Cyan
    }
    Write-Host "      New Commits   :"
    foreach ($c in $delta.Commits) {
        Write-Host "        * $c" -ForegroundColor White
    }
}

# 4. Assess Dangerous Changes
Write-Host "[4/6] Assessing Dangerous Upstream Changes... "
$risks = Test-DangerousUpstreamChanges -Repo $RepoPath -ForkBaseRef "origin/main" -UpstreamRef "upstream/main"
$riskColor = "Green"
if ($risks.RiskLevel -eq "HIGH") { $riskColor = "Red" }
elseif ($risks.RiskLevel -eq "MEDIUM") { $riskColor = "Yellow" }
Write-Host "      Risk Level    : $($risks.RiskLevel)" -ForegroundColor $riskColor

if ($risks.RequiresManualReview) {
    Write-Host "      MANUAL REVIEW REQUIRED for upstream changes:" -ForegroundColor Red
    if ($risks.WorkflowChanges.Count -gt 0) {
        Write-Host "        - Workflow changes (.github/workflows):" -ForegroundColor Red
        foreach ($wf in $risks.WorkflowChanges) { Write-Host "            $wf" -ForegroundColor DarkRed }
    }
    if ($risks.DeployChanges.Count -gt 0) {
        Write-Host "        - Deploy/Container changes:" -ForegroundColor Red
        foreach ($dc in $risks.DeployChanges) { Write-Host "            $dc" -ForegroundColor DarkRed }
    }
    if ($risks.StorageChanges.Count -gt 0) {
        Write-Host "        - Data/Storage changes:" -ForegroundColor Red
        foreach ($sc in $risks.StorageChanges) { Write-Host "            $sc" -ForegroundColor DarkRed }
    }
} else {
    Write-Host "      No dangerous workflow, container, or storage changes detected." -ForegroundColor Green
}

# 5. Version Drift & Proposed Identity
Write-Host "[5/6] Determining Version Alignment... "
$currentSourceVer = Get-SourceReleaseVersion -Repo $RepoPath
$upstreamProxyRes = Get-GitCommandOutput -Repo $RepoPath -Arguments @("show", "upstream/main:wb_proxy.py")
$upstreamStableVer = $currentSourceVer
if ($upstreamProxyRes.ExitCode -eq 0) {
    $matchUp = [regex]::Match($upstreamProxyRes.StdOut, 'server_version\s*=\s*"wb-proxy/([^"]+)"')
    if ($matchUp.Success) {
        $upstreamStableVer = $matchUp.Groups[1].Value
    }
}
$versionDeriv = Derive-NextForkVersion -UpstreamBaseVer $upstreamStableVer -CurrentForkVer $currentSourceVer
Write-Host "      Current Source Version   : $currentSourceVer"
Write-Host "      Upstream Base Version    : $upstreamStableVer"
Write-Host "      Proposed Fork Version    : $($versionDeriv.ProposedForkVersion)" -ForegroundColor Cyan
Write-Host "      Proposed Tag             : $($versionDeriv.ProposedTag)" -ForegroundColor Cyan

# 6. Verify T-008 Dual Network Baseline
Write-Host "[6/6] Verifying T-008 Dual Network Baseline... "
$t008Check = Test-T008DualNetworkConfig -Repo $RepoPath
if ($t008Check.IsValid) {
    Write-Host "      T-008 Dual Network       : PASS (default + sub2api preserved)" -ForegroundColor Green
} else {
    Write-Host "      T-008 Dual Network       : FAILED ($($t008Check.Reason))" -ForegroundColor Red
}

# 7. Record Audit Evidence
$evidence = @{
    mode                   = "check"
    timestamp              = (Get-Date).ToString("o")
    repo_path              = $RepoPath
    workspace_clean        = $gitCtx.IsClean
    current_branch         = $gitCtx.Branch
    head_sha               = $gitCtx.HeadSha
    origin_sha             = $delta.ForkBaseSha
    upstream_sha           = $delta.UpstreamSha
    merge_base_sha         = $delta.MergeBaseSha
    has_update             = $delta.HasUpdate
    commit_count           = $delta.CommitCount
    risk_level             = $risks.RiskLevel
    requires_manual_review = $risks.RequiresManualReview
    current_version        = $currentSourceVer
    upstream_version       = $upstreamStableVer
    proposed_fork_version  = $versionDeriv.ProposedForkVersion
    proposed_tag           = $versionDeriv.ProposedTag
    t008_dual_network      = $t008Check.IsValid
}
$auditFile = Write-SyncAuditEvidence -Repo $RepoPath -EvidenceData $evidence
Write-Host "`nAudit log saved to: $auditFile" -ForegroundColor DarkGray

if ($Json) {
    $evidence | ConvertTo-Json -Depth 5
}
