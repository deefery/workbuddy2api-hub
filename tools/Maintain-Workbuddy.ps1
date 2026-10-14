[CmdletBinding()]
param(
    [ValidateSet('menu','status','check','update','help')]
    [string]$Action = 'menu',
    [string]$RepoPath,
    [string]$TargetNasHost = 'openmaic-nas-q4',
    [string]$NasDirectory = '/share/Container/workbuddy2api-hub'
)

$ErrorActionPreference = 'Stop'
if (-not $RepoPath) { $RepoPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')) }
$RepoPath = [IO.Path]::GetFullPath($RepoPath)
if ($TargetNasHost -match '(^|@)tro($|\.)') { throw 'Refusing forbidden tro target.' }
if ($NasDirectory -notmatch '^/[A-Za-z0-9_./-]+$' -or $NasDirectory -match '(^|/)\.\.(/|$)') { throw 'Invalid NAS directory.' }

. (Join-Path $PSScriptRoot 'UpstreamSync.Common.ps1')

function Invoke-GitText {
    param([string[]]$Arguments)
    $old = Get-Location
    try {
        Set-Location $RepoPath
        $out = & git @Arguments 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'git command failed.' }
        (($out | ForEach-Object { "$_" }) -join "`n").Trim()
    } finally { Set-Location $old }
}

function Get-LatestAudit {
    param([string]$Prefix, [datetime]$Since)
    $dir = Join-Path $RepoPath '.ai/runtime'
    $f = Get-ChildItem -LiteralPath $dir -Filter "$Prefix-*.json" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -ge $Since.ToUniversalTime().AddSeconds(-2) } |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if (-not $f) { throw "No fresh $Prefix audit found." }
    [PSCustomObject]@{
        Path = $f.FullName
        Data = (Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json)
    }
}

function Show-AuditSummary {
    param($Audit)
    $d = $Audit.Data
    Write-Host "status       : $($d.status)"
    if ($d.upstream_version) { Write-Host "upstream     : $($d.upstream_version)  $($d.new_upstream_sha)" }
    if ($d.fork_tag) { Write-Host "target       : $($d.fork_tag)" }
    if ($d.risk_level) { Write-Host "risk         : $($d.risk_level)" }
    if ($d.last_gate) { Write-Host "last gate    : $($d.last_gate)" }
    if ($d.stop_reason) { Write-Host "stop reason  : $($d.stop_reason)" }
    if ($d.ghcr_digest) { Write-Host "GHCR digest  : $($d.ghcr_digest)" }
    if ($d.new_nas_tag) { Write-Host "NAS tag      : $($d.new_nas_tag)" }
    if ($d.final_health) { Write-Host "NAS health   : $($d.final_health)" }
    if ($d.rollback_status -and $d.rollback_status -ne 'NOT_NEEDED') { Write-Host "rollback     : $($d.rollback_status)" }
    Write-Host "audit        : $($Audit.Path)"
}

function Get-NasStatus {
    $dockerPath = '/share/CACHEDEV1_DATA/.qpkg/container-station/bin:/share/CACHEDEV1_DATA/.qpkg/container-station/usr/bin:$PATH'
    $remote = "set -eu; export PATH=$dockerPath; cd '$NasDirectory'; printf 'tag='; sed -n 's/^WB_IMAGE_TAG=//p' .env; printf 'health='; docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' wb-proxy; printf 'image='; docker inspect -f '{{.Config.Image}}' wb-proxy"
    $out = & ssh -o BatchMode=yes -o ConnectTimeout=10 $TargetNasHost $remote 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'NAS status check failed; SSH details suppressed.' }
    (($out | ForEach-Object { "$_" }) -join "`n").Trim()
}

function Invoke-Status {
    Write-Host '=== WorkBuddy maintenance status ==='
    $branch = Invoke-GitText @('branch','--show-current')
    $head = Invoke-GitText @('rev-parse','HEAD')
    $origin = Invoke-GitText @('rev-parse','origin/custom/main')
    $upstream = Invoke-GitText @('rev-parse','upstream/main')
    $version = Get-SourceReleaseVersion -Repo $RepoPath
    Write-Host "repo         : $RepoPath"
    Write-Host "branch       : $branch"
    Write-Host "version      : v$version"
    Write-Host "HEAD         : $head"
    Write-Host "origin/custom: $origin"
    Write-Host "upstream/main: $upstream"
    if ($head -ne $origin) { Write-Host 'WARNING      : local custom/main differs from origin/custom/main' }
    Write-Host '--- NAS ---'
    Get-NasStatus | Write-Host
}

function Invoke-Check {
    Write-Host '=== Checking upstream ==='
    $start = Get-Date
    & (Join-Path $PSScriptRoot 'Check-Upstream.ps1') -RepoPath $RepoPath
    $audit = Get-LatestAudit -Prefix 'sync-check' -Since $start
    Show-AuditSummary $audit
    $audit
}

function Invoke-OneClickUpdate {
    Write-Host '=== One-click upstream -> Release -> GHCR -> NAS ==='
    $check = Invoke-Check
    $c = $check.Data
    if ($c.status -eq 'UP_TO_DATE') {
        Write-Host 'Already up to date. Nothing to do.'
        return
    }
    if ($c.status -notin @('UPDATE_AVAILABLE','UPDATE_AVAILABLE_REVIEW_REQUIRED')) {
        throw "Check stopped with status $($c.status)."
    }
    if ($c.new_upstream_sha -notmatch '^[a-f0-9]{40}$') { throw 'Upstream SHA unresolved.' }

    $sha = $c.new_upstream_sha
    Write-Host "Approved upstream SHA by explicit update action: $sha"

    $stageStart = Get-Date
    & (Join-Path $PSScriptRoot 'Update-From-Upstream.ps1') `
        -RepoPath $RepoPath `
        -AuthorizeRelease -AuthorizeNas `
        -ReviewedUpstreamSha $sha `
        -StateCompatibilitySha $sha `
        -TargetNasHost $TargetNasHost -NasDirectory $NasDirectory
    $stage = Get-LatestAudit -Prefix 'sync-update' -Since $stageStart
    Show-AuditSummary $stage

    if ($stage.Data.status -eq 'UP_TO_DATE') { return }
    if ($stage.Data.status -ne 'DRAFT_READY_AWAITING_REVIEW') {
        throw "Release staging stopped at $($stage.Data.last_gate): $($stage.Data.stop_reason)"
    }
    $tag = $stage.Data.fork_tag
    if ($tag -notmatch '^v\d+\.\d+\.\d+\.\d+$') { throw 'Draft tag unresolved.' }

    Write-Host "Continuing draft automatically: $tag"
    $finishStart = Get-Date
    & (Join-Path $PSScriptRoot 'Update-From-Upstream.ps1') `
        -RepoPath $RepoPath `
        -ResumeReleaseEvidence $stage.Path `
        -AuthorizeRelease -AuthorizeNas `
        -ReviewedDraftTag $tag `
        -StateCompatibilitySha $sha `
        -TargetNasHost $TargetNasHost -NasDirectory $NasDirectory
    $final = Get-LatestAudit -Prefix 'sync-update' -Since $finishStart
    Show-AuditSummary $final
    if ($final.Data.status -ne 'SUCCESS') {
        throw "Maintenance update did not finish successfully. Last gate: $($final.Data.last_gate); $($final.Data.stop_reason)"
    }
    Write-Host "DONE: $tag is released and NAS accepted it."
}

function Show-Help {
    Write-Host @'
WorkBuddy maintenance

  Maintain-Workbuddy.cmd              interactive menu
  Maintain-Workbuddy.cmd status       local + NAS status
  Maintain-Workbuddy.cmd check        fetch/check upstream only
  Maintain-Workbuddy.cmd update       one-click upstream -> release -> GHCR -> NAS
  Maintain-Workbuddy.cmd help

The update command reuses the T-007 fail-closed pipeline. It automatically carries the
exact upstream SHA, draft tag and continuation audit between the two release phases.
If deployment fails after the snapshot boundary, the existing T-007 rollback path remains active.
'@
}

function Invoke-Menu {
    while ($true) {
        Write-Host ''
        Write-Host 'WorkBuddy maintenance'
        Write-Host '  1. Status'
        Write-Host '  2. Check upstream'
        Write-Host '  3. Update to latest + deploy NAS'
        Write-Host '  4. Help'
        Write-Host '  0. Exit'
        $choice = Read-Host 'Select'
        switch ($choice) {
            '1' { Invoke-Status }
            '2' { [void](Invoke-Check) }
            '3' { Invoke-OneClickUpdate }
            '4' { Show-Help }
            '0' { return }
            default { Write-Host 'Unknown selection.' }
        }
    }
}

try {
    switch ($Action) {
        'menu'   { Invoke-Menu }
        'status' { Invoke-Status }
        'check'  { [void](Invoke-Check) }
        'update' { Invoke-OneClickUpdate }
        'help'   { Show-Help }
    }
    exit 0
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
