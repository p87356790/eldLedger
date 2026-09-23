$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$releaseDir = Join-Path $root "release"
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd"
$stage = Join-Path $releaseDir "eldledger-release-$stamp"
if (Test-Path $stage) {
    Remove-Item -Recurse -Force $stage
}
New-Item -ItemType Directory -Path $stage | Out-Null

$files = @(
    "docker-compose.yml",
    ".env.example",
    "start.bat",
    "stop.bat",
    "backup.bat",
    "upgrade.bat",
    "start.sh",
    "stop.sh",
    "backup.sh",
    "upgrade.sh",
    "README.md"
)
foreach ($file in $files) {
    Copy-Item -Path (Join-Path $root $file) -Destination (Join-Path $stage $file) -Force
}

foreach ($folder in @("backend", "frontend", "docs", "scripts")) {
    $source = Join-Path $root $folder
    $target = Join-Path $stage $folder
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    & robocopy $source $target /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD node_modules .venv dist .vite .pytest_cache __pycache__ .git | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for $folder (code $LASTEXITCODE)"
    }
}

Get-ChildItem -Path $stage -Recurse -Filter *.sh | ForEach-Object {
    $text = [System.IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n" -replace "`r", "`n"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($_.FullName, $text, $utf8)
}

function New-ZipFromStage {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$SourceDir
    )
    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    # Compress-Archive는 잠긴 파일에서 자주 실패하므로 tar 사용
    & tar -a -cf $ZipPath -C $SourceDir .
    if ($LASTEXITCODE -ne 0) {
        throw "zip 생성 실패: $ZipPath"
    }
}

# 설치용: 빈 data 골격 포함 (처음 설치)
foreach ($name in @("database", "uploads", "reports", "backups")) {
    $dir = Join-Path $stage "data\$name"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Set-Content -Path (Join-Path $dir ".gitkeep") -Value "" -Encoding utf8
}

$installZip = Join-Path $releaseDir "eldledger-$stamp-install.zip"
New-ZipFromStage -ZipPath $installZip -SourceDir $stage

# 업그레이드용: data 폴더 없음 (기존 장부를 덮지 않음)
$dataStage = Join-Path $stage "data"
if (Test-Path $dataStage) {
    Remove-Item -Recurse -Force $dataStage
}

$upgradeZip = Join-Path $releaseDir "eldledger-$stamp-upgrade.zip"
New-ZipFromStage -ZipPath $upgradeZip -SourceDir $stage

# Windows에서 쓰던 장부를 Ubuntu 등으로 옮길 때: data만 별도 zip
$liveDb = Join-Path $root "data\database\eldledger.db"
$dataZip = $null
if (Test-Path $liveDb) {
    $dataStageDir = Join-Path $releaseDir "eldledger-data-$stamp"
    if (Test-Path $dataStageDir) {
        Remove-Item -Recurse -Force $dataStageDir
    }
    New-Item -ItemType Directory -Path $dataStageDir | Out-Null
    & robocopy (Join-Path $root "data") (Join-Path $dataStageDir "data") /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for live data (code $LASTEXITCODE)"
    }
    $dataZip = Join-Path $releaseDir "eldledger-$stamp-data.zip"
    New-ZipFromStage -ZipPath $dataZip -SourceDir $dataStageDir
    Remove-Item -Recurse -Force $dataStageDir
}

Write-Host ""
Write-Host "배포 묶음을 만들었습니다."
Write-Host "  설치용(처음):     $installZip"
Write-Host "  업그레이드용:     $upgradeZip"
if ($null -ne $dataZip) {
    Write-Host "  장부 data 이전용: $dataZip"
    Write-Host "    (지금 이 PC의 data 폴더. Ubuntu와 장부를 같게 쓸 때 같이 복사)"
} else {
    Write-Host "  장부 data 이전용: (이 PC에 eldledger.db 가 없어 만들지 않음)"
}
Write-Host ""
Write-Host "처음 설치: install zip 풀기 → start.sh / start.bat"
Write-Host "버전만 올리기: 기존 폴더에 upgrade zip 풀기(덮어쓰기) → data 는 그대로 둠"
Write-Host "Windows 장부 → Ubuntu: 서버에서 끈 뒤 data zip 을 설치 폴더에 풀기"
