[CmdletBinding()]
param([string]$RepoPath, [switch]$NoFetch, [switch]$Json)
if (-not $RepoPath) { $RepoPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/UpstreamSync.Common.ps1"
$e = @{ mode = 'check'; timestamp = (Get-Date).ToString('o'); status = 'STOPPED'; rollback_status = 'NOT_NEEDED'; final_health = 'NOT_RUN' }
try {
    $e.last_gate = 'WORKSPACE'
    $g = Get-SyncGitContext -Repo $RepoPath
    $e.workspace_clean = $g.IsClean; $e.head_sha = $g.HeadSha
    if (-not $g.HasOrigin -or -not $g.HasUpstream) { throw 'STOP: Required remotes missing' }
    $e.last_gate = 'FETCH'
    if (-not $NoFetch) {
        $f = Invoke-SafeFetch -Repo $RepoPath
        if (-not $f.OriginSuccess -or -not $f.UpstreamSuccess) { throw 'STOP: Fetch failed; refusing stale refs' }
    }
    $e.last_gate = 'DELTA'
    $d = Get-UpstreamDeltaSummary -Repo $RepoPath
    $e.old_upstream_sha = $d.ForkBaseSha; $e.new_upstream_sha = $d.UpstreamSha; $e.has_update = $d.HasUpdate
    if ($d.IsDivergent) { $e.status = 'DIVERGENT_STOP'; throw 'STOP: origin/main contains commits outside upstream/main' }
    $e.last_gate = 'VERSION'
    $current = Read-ExactVersion -Content (Assert-SyncGit -Repo $RepoPath -Arguments @('show', 'custom/main:wb_proxy.py'))
    $up = Get-UpstreamStableVersion -Repo $RepoPath
    $v = Derive-NextForkVersion -UpstreamBaseVer $up -CurrentForkVer $current
    $e.current_fork_version = $current; $e.upstream_version = $up
    $e.fork_version = $v.ProposedForkVersion; $e.fork_tag = $v.ProposedTag
    $e.last_gate = 'RISK'
    $r = Test-DangerousUpstreamChanges -Repo $RepoPath
    $e.risk_level = $r.RiskLevel
    $e.t008_dual_network = (Test-T008DualNetworkConfig -Repo $RepoPath).IsValid
    if (-not $e.t008_dual_network) { throw 'STOP: T-008 invariant failed' }
    $e.status = if ($d.IsDivergent) { 'DIVERGENT_STOP' } elseif (-not $d.HasUpdate) { 'UP_TO_DATE' } elseif ($r.RequiresManualReview) { 'UPDATE_AVAILABLE_REVIEW_REQUIRED' } else { 'UPDATE_AVAILABLE' }
    Write-Host "$($e.status): $($d.CommitCount) upstream commits, risk $($r.RiskLevel), proposed $($v.ProposedTag), T-008 PASS"
    if ($Json) { $e | ConvertTo-Json -Depth 5 }
} catch {
    $e.stop_reason = "Failed at $($e.last_gate)"
    Write-Error ("STOP: " + $e.stop_reason)
} finally {
    Write-SyncAuditEvidence -Repo $RepoPath -EvidenceData $e | Write-Host
}
