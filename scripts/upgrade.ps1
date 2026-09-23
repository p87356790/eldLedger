$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path (Join-Path $root "docker-compose.yml"))) {
    Write-Host "이 스크립트는 eldLedger 설치 폴더에서 실행해야 합니다."
    exit 1
}

function Find-UpgradeZip {
    param([string]$Hint)

    if ($Hint -ne "") {
        if (-not (Test-Path -LiteralPath $Hint -PathType Leaf)) {
            throw "zip 파일을 찾을 수 없습니다: $Hint"
        }
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $dirs = @(
        $root,
        (Split-Path -Parent $root),
        $env:USERPROFILE,
        (Join-Path $env:USERPROFILE "Downloads"),
        (Join-Path $env:USERPROFILE "다운로드"),
        (Join-Path $root "release")
    ) | Where-Object { $_ -and (Test-Path $_) }

    $candidates = @()
    foreach ($dir in $dirs) {
        $candidates += Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^eldledger-.+-(upgrade|install)\.zip$' }
    }

    if ($candidates.Count -eq 0) {
        throw @"
업그레이드 zip을 찾지 못했습니다.
사용법: upgrade.bat C:\경로\eldledger-날짜-upgrade.zip
또는 upgrade zip을 Downloads/설치폴더/release 에 두고 upgrade.bat
"@
    }

    return ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}

$zipPath = Find-UpgradeZip -Hint $(if ($args.Count -gt 0) { [string]$args[0] } else { "" })
Write-Host "사용할 zip: $zipPath"

Write-Host "업그레이드 전 백업을 만듭니다..."
try {
    & (Join-Path $PSScriptRoot "backup.ps1")
} catch {
    Write-Host "백업을 건너뜁니다: $($_.Exception.Message)"
}

Write-Host "서버를 잠시 멈춥니다..."
try {
    & (Join-Path $PSScriptRoot "stop.ps1")
} catch {
    Write-Host "중지 경고: $($_.Exception.Message)"
}

$tmpdir = Join-Path ([System.IO.Path]::GetTempPath()) ("eldledger-upgrade-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpdir | Out-Null
try {
    Expand-Archive -LiteralPath $zipPath -DestinationPath $tmpdir -Force

    $compose = Get-ChildItem -LiteralPath $tmpdir -Recurse -Filter "docker-compose.yml" -File |
        Select-Object -First 1
    if ($null -eq $compose) {
        throw "zip 안에 docker-compose.yml 이 없습니다. 올바른 eldLedger zip인지 확인하세요."
    }
    $payload = $compose.Directory.FullName

    Write-Host "파일을 덮어씁니다. data/ 와 .env 는 그대로 둡니다."
    Get-ChildItem -LiteralPath $payload -Force | ForEach-Object {
        if ($_.Name -eq "data" -or $_.Name -eq ".env") {
            return
        }
        $dest = Join-Path $root $_.Name
        if ($_.PSIsContainer) {
            & robocopy $_.FullName $dest /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD node_modules .venv __pycache__ .pytest_cache | Out-Null
            if ($LASTEXITCODE -ge 8) {
                throw "robocopy failed for $($_.Name) (code $LASTEXITCODE)"
            }
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
        }
    }
} finally {
    Remove-Item -Recurse -Force $tmpdir -ErrorAction SilentlyContinue
}

Write-Host "다시 켭니다..."
$env:BUILD_ID = Get-Date -Format "yyyyMMddHHmmss"
$env:ELDLEDGER_FORCE_RECREATE = "1"
& (Join-Path $PSScriptRoot "start.ps1")
Write-Host "업그레이드가 끝났습니다. data/ 장부는 그대로입니다."
