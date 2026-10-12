<#
.SYNOPSIS
    WorkBuddy2API-Hub Upstream Sync & Safe Auto-Deploy Common Library (T-007)
.DESCRIPTION
    Shared logic for upstream drift detection, risk assessment, version derivation,
    release-identity updates, draft-first GitHub release verification, GHCR checks,
    and safe NAS deployment with rollback protection.
#>

function Get-GitCommandOutput {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][string[]]$Arguments
    )
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = "git"
    $pinfo.WorkingDirectory = $Repo
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $pinfo.CreateNoWindow = $true

    $allArgs = @("-c", "safe.directory=*") + $Arguments
    $pinfo.Arguments = ($allArgs | ForEach-Object {
        if ($_ -match '[\s"]') { '"{0}"' -f ($_ -replace '"', '\"') } else { $_ }
    }) -join " "

    $p = [System.Diagnostics.Process]::Start($pinfo)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    return [PSCustomObject]@{
        ExitCode = $p.ExitCode
        StdOut   = $stdout.TrimEnd("`r`n")
        StdErr   = $stderr.TrimEnd("`r`n")
    }
}

function Get-SyncGitContext {
    param([Parameter(Mandatory=$true)][string]$Repo)

    $resStatus = Get-GitCommandOutput -Repo $Repo -Arguments @("status", "--porcelain")
    $isClean = [string]::IsNullOrWhiteSpace($resStatus.StdOut)

    $resRemote = Get-GitCommandOutput -Repo $Repo -Arguments @("remote", "-v")
    $hasOrigin = $resRemote.StdOut -match "(?m)^origin\s+"
    $hasUpstream = $resRemote.StdOut -match "(?m)^upstream\s+"

    $resBranch = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    $resHead = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", "HEAD")

    return [PSCustomObject]@{
        RepoPath    = $Repo
        IsClean     = $isClean
        DirtyFiles  = if (-not $isClean) { ($resStatus.StdOut -split "`r?`n") } else { @() }
        HasOrigin   = [bool]$hasOrigin
        HasUpstream = [bool]$hasUpstream
        Branch      = $resBranch.StdOut
        HeadSha     = $resHead.StdOut
    }
}

function Invoke-SafeFetch {
    param([Parameter(Mandatory=$true)][string]$Repo)
    $fetchOrigin = Get-GitCommandOutput -Repo $Repo -Arguments @("fetch", "origin")
    $fetchUpstream = Get-GitCommandOutput -Repo $Repo -Arguments @("fetch", "upstream")
    return [PSCustomObject]@{
        OriginSuccess   = ($fetchOrigin.ExitCode -eq 0)
        UpstreamSuccess = ($fetchUpstream.ExitCode -eq 0)
        OriginError     = $fetchOrigin.StdErr
        UpstreamError   = $fetchUpstream.StdErr
    }
}

function Get-UpstreamDeltaSummary {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [string]$ForkBaseRef = "origin/main",
        [string]$UpstreamRef = "upstream/main"
    )
    $resFork = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", $ForkBaseRef)
    $resUpstream = Get-GitCommandOutput -Repo $Repo -Arguments @("rev-parse", $UpstreamRef)
    if ($resFork.ExitCode -ne 0 -or $resUpstream.ExitCode -ne 0) {
        throw "Failed to resolve refs '$ForkBaseRef' or '$UpstreamRef'"
    }

    $forkSha = $resFork.StdOut
    $upstreamSha = $resUpstream.StdOut

    $resBase = Get-GitCommandOutput -Repo $Repo -Arguments @("merge-base", $ForkBaseRef, $UpstreamRef)
    $mergeBaseSha = $resBase.StdOut

    $hasUpdate = ($forkSha -ne $upstreamSha)
    $isFastForward = ($mergeBaseSha -eq $forkSha)
    $isDivergent = ($hasUpdate -and -not $isFastForward)

    $commits = @()
    if ($hasUpdate) {
        $resLog = Get-GitCommandOutput -Repo $Repo -Arguments @("log", "--oneline", "$ForkBaseRef..$UpstreamRef")
        if (-not [string]::IsNullOrWhiteSpace($resLog.StdOut)) {
            $commits = ($resLog.StdOut -split "`r?`n") | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        }
    }

    return [PSCustomObject]@{
        ForkBaseRef   = $ForkBaseRef
        ForkBaseSha   = $forkSha
        UpstreamRef   = $UpstreamRef
        UpstreamSha   = $upstreamSha
        MergeBaseSha  = $mergeBaseSha
        HasUpdate     = $hasUpdate
        IsFastForward = $isFastForward
        IsDivergent   = $isDivergent
        Commits       = $commits
        CommitCount   = $commits.Length
    }
}

function Test-DangerousUpstreamChanges {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [string]$ForkBaseRef = "origin/main",
        [string]$UpstreamRef = "upstream/main"
    )
    $resDiff = Get-GitCommandOutput -Repo $Repo -Arguments @("diff", "--name-only", "$ForkBaseRef..$UpstreamRef")
    if ($resDiff.ExitCode -ne 0) {
        throw "Failed to compute diff between $ForkBaseRef and $UpstreamRef"
    }

    $changedFiles = if ([string]::IsNullOrWhiteSpace($resDiff.StdOut)) { @() } else { $resDiff.StdOut -split "`r?`n" }

    $workflowChanges = @()
    $deployChanges = @()
    $storageChanges = @()
    $packagingChanges = @()

    foreach ($file in $changedFiles) {
        if ($file -like ".github/workflows/*") {
            $workflowChanges += $file
        } elseif ($file -like "deploy/*" -or $file -match "^docker-compose.*\.ya?ml$" -or $file -eq "Dockerfile") {
            $deployChanges += $file
        } elseif ($file -eq "wb_settings.py" -or $file -eq "wb_atrest.py" -or $file -like "accounts/*" -or $file -like "usage/*") {
            $storageChanges += $file
        } elseif ($file -like "wrt/*" -or $file -like "release/*") {
            $packagingChanges += $file
        }
    }

    $isHighRisk = ($workflowChanges.Count -gt 0 -or $deployChanges.Count -gt 0 -or $storageChanges.Count -gt 0)
    $riskLevel = if ($isHighRisk) { "HIGH" } elseif ($packagingChanges.Count -gt 0) { "MEDIUM" } else { "LOW" }

    return [PSCustomObject]@{
        ChangedFilesCount    = $changedFiles.Count
        ChangedFiles         = $changedFiles
        WorkflowChanges      = $workflowChanges
        DeployChanges        = $deployChanges
        StorageChanges       = $storageChanges
        PackagingChanges     = $packagingChanges
        RiskLevel            = $riskLevel
        RequiresManualReview = $isHighRisk
    }
}

function Get-SourceReleaseVersion {
    param([Parameter(Mandatory=$true)][string]$Repo)
    $proxyPath = Join-Path $Repo "wb_proxy.py"
    if (-not (Test-Path $proxyPath)) {
        throw "wb_proxy.py not found at $proxyPath"
    }
    $src = Get-Content $proxyPath -Raw -Encoding UTF8
    $matchOverview = [regex]::Match($src, '"version"\s*:\s*"([^"]+)"')
    $matchServer = [regex]::Match($src, 'server_version\s*=\s*"wb-proxy/([^"]+)"')

    if (-not $matchOverview.Success -or -not $matchServer.Success) {
        throw "Could not parse version literals from wb_proxy.py"
    }
    if ($matchOverview.Groups[1].Value -ne $matchServer.Groups[1].Value) {
        throw "Version mismatch in wb_proxy.py: overview '$($matchOverview.Groups[1].Value)' vs server '$($matchServer.Groups[1].Value)'"
    }
    return $matchServer.Groups[1].Value
}

function Derive-NextForkVersion {
    param(
        [Parameter(Mandatory=$true)][string]$UpstreamBaseVer,
        [Parameter(Mandatory=$true)][string]$CurrentForkVer
    )

    $cleanUpstream = $UpstreamBaseVer -replace '^v', ''
    $cleanFork = $CurrentForkVer -replace '^v', ''

    if ($cleanUpstream -match '-' -or $cleanFork -match '-') {
        throw "Invalid version format containing hyphen: Upstream='$UpstreamBaseVer', Fork='$CurrentForkVer'. Must strictly adhere to D-004/D-010 dot-numeric rule."
    }

    $upstreamMatch = [regex]::Match($cleanUpstream, '^(\d+)\.(\d+)\.(\d+)$')
    if (-not $upstreamMatch.Success) {
        throw "Upstream version '$UpstreamBaseVer' does not match standard <major>.<minor>.<patch> semantic format."
    }

    $forkMatch = [regex]::Match($cleanFork, '^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$')
    if (-not $forkMatch.Success) {
        throw "Current fork version '$CurrentForkVer' does not match dot-numeric format X.Y.Z[.N]."
    }

    $uMajor = [int]$upstreamMatch.Groups[1].Value
    $uMinor = [int]$upstreamMatch.Groups[2].Value
    $uPatch = [int]$upstreamMatch.Groups[3].Value

    $fMajor = [int]$forkMatch.Groups[1].Value
    $fMinor = [int]$forkMatch.Groups[2].Value
    $fPatch = [int]$forkMatch.Groups[3].Value
    $fRev   = if ($forkMatch.Groups[4].Success) { [int]$forkMatch.Groups[4].Value } else { 0 }

    $isNewUpstream = ($uMajor -gt $fMajor) -or 
                     ($uMajor -eq $fMajor -and $uMinor -gt $fMinor) -or 
                     ($uMajor -eq $fMajor -and $uMinor -eq $fMinor -and $uPatch -gt $fPatch)

    $nextVer = ""
    if ($isNewUpstream) {
        $nextVer = "$uMajor.$uMinor.$uPatch.1"
    } else {
        $nextRev = if ($fRev -gt 0) { $fRev + 1 } else { 1 }
        $nextVer = "$uMajor.$uMinor.$uPatch.$nextRev"
    }

    return [PSCustomObject]@{
        CleanUpstreamVer    = $cleanUpstream
        CleanForkVer        = $cleanFork
        ProposedForkVersion = $nextVer
        ProposedTag         = "v$nextVer"
        IsNewUpstreamBase   = $isNewUpstream
    }
}

function Update-ReleaseIdentityFiles {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][string]$Version
    )

    $cleanVer = $Version -replace '^v', ''
    if ($cleanVer -notmatch '^\d+\.\d+\.\d+\.\d+$') {
        throw "Version '$Version' must be four dot-separated integers (e.g. 1.7.2.2) according to D-004/D-010."
    }

    $proxyFile = Join-Path $Repo "wb_proxy.py"
    $proxyText = Get-Content $proxyFile -Raw -Encoding UTF8
    
    $proxyText = [regex]::Replace($proxyText, '"version":\s*"[^"]+"', ('"version": "{0}"' -f $cleanVer), 1)
    $proxyText = [regex]::Replace($proxyText, 'server_version\s*=\s*"wb-proxy/[^"]+"', ('server_version = "wb-proxy/{0}"' -f $cleanVer), 1)
    [System.IO.File]::WriteAllText($proxyFile, $proxyText, [System.Text.Encoding]::UTF8)

    $mkFile = Join-Path $Repo "wrt\openwrt\workbuddy2api\Makefile"
    $mkText = Get-Content $mkFile -Raw -Encoding UTF8
    $mkText = [regex]::Replace($mkText, 'PKG_VERSION:=[^\r\n]+', ('PKG_VERSION:={0}' -f $cleanVer), 1)
    [System.IO.File]::WriteAllText($mkFile, $mkText, [System.Text.Encoding]::UTF8)

    $verifiedVer = Get-SourceReleaseVersion -Repo $Repo
    if ($verifiedVer -ne $cleanVer) {
        throw "Verification failed: wb_proxy.py source version '$verifiedVer' != target '$cleanVer'"
    }

    $newMkText = Get-Content $mkFile -Raw -Encoding UTF8
    $mkMatch = [regex]::Match($newMkText, 'PKG_VERSION:=([^\r\n]+)')
    if (-not $mkMatch.Success -or $mkMatch.Groups[1].Value.Trim() -ne $cleanVer) {
        throw "Verification failed: Makefile PKG_VERSION != target '$cleanVer'"
    }

    return [PSCustomObject]@{
        Success           = $true
        UpdatedVersion    = $cleanVer
        VerifiedSourceVer = $verifiedVer
    }
}

function Test-T008DualNetworkConfig {
    param(
        [string]$Repo = "",
        [string]$ComposeFilePath = ""
    )
    $path = if ([string]::IsNullOrWhiteSpace($ComposeFilePath)) {
        Join-Path $Repo "deploy\nas\docker-compose.yml"
    } else {
        $ComposeFilePath
    }

    if (-not (Test-Path $path)) {
        return [PSCustomObject]@{
            IsValid = $false
            Reason  = "Compose file not found at $path"
        }
    }

    $content = Get-Content $path -Raw -Encoding UTF8

    $hasDefaultNet = $content -match "(?m)^\s+-\s+default\s*$"
    $hasSub2apiNet = $content -match "(?m)^\s+-\s+sub2api\s*$"
    $hasSub2apiBlock = $content -match "sub2api:\s*\r?\n\s+external:\s*true\s*\r?\n\s+name:\s*sub2api_sub2api-network"

    $isValid = ($hasDefaultNet -and $hasSub2apiNet -and $hasSub2apiBlock)
    return [PSCustomObject]@{
        IsValid          = $isValid
        HasDefaultNet    = [bool]$hasDefaultNet
        HasSub2apiNet    = [bool]$hasSub2apiNet
        HasSub2apiBlock  = [bool]$hasSub2apiBlock
        Reason           = if ($isValid) { "OK" } else { "Dual network configuration violated: missing default, sub2api, or external network block" }
    }
}

function Test-ReleaseGates {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [string]$PythonExe = "C:\Users\jinle\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    )
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found at $PythonExe"
    }

    $reTest = Join-Path $Repo "tests\_test_release_engineering.py"
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = $PythonExe
    $pinfo.Arguments = "`"$reTest`""
    $pinfo.WorkingDirectory = $Repo
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $pinfo.CreateNoWindow = $true

    $p = [System.Diagnostics.Process]::Start($pinfo)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()

    $passed = ($p.ExitCode -eq 0)
    return [PSCustomObject]@{
        Success  = $passed
        ExitCode = $p.ExitCode
        Output   = ($stdout + "`n" + $stderr).Trim()
    }
}

function Write-SyncAuditEvidence {
    param(
        [Parameter(Mandatory=$true)][string]$Repo,
        [Parameter(Mandatory=$true)][hashtable]$EvidenceData
    )
    $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
    $mode = if ($EvidenceData.ContainsKey("mode")) { $EvidenceData["mode"] } else { "check" }
    $filename = "upstream-sync-$mode-$timestamp.json"
    
    $preferredDir = Join-Path $Repo ".ai\runtime"
    $targetPath = Join-Path $preferredDir $filename

    $json = $EvidenceData | ConvertTo-Json -Depth 5
    try {
        if (-not (Test-Path $preferredDir)) {
            New-Item -ItemType Directory -Path $preferredDir -Force | Out-Null
        }
        [System.IO.File]::WriteAllText($targetPath, $json, [System.Text.Encoding]::UTF8)
        return $targetPath
    } catch {
        $fallbackDir = [System.IO.Path]::GetTempPath()
        $fallbackPath = Join-Path $fallbackDir $filename
        [System.IO.File]::WriteAllText($fallbackPath, $json, [System.Text.Encoding]::UTF8)
        return $fallbackPath
    }
}

