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

$excludeDirs = @("node_modules", ".venv", "dist", ".vite", ".pytest_cache", "__pycache__", ".git")
$files = @("docker-compose.yml", ".env.example", "start.bat", "stop.bat", "backup.bat", "README.md")
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

foreach ($name in @("database", "uploads", "reports", "backups")) {
    $dir = Join-Path $stage "data\$name"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Set-Content -Path (Join-Path $dir ".gitkeep") -Value "" -Encoding utf8
}

$zip = Join-Path $releaseDir "eldledger-$stamp.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
Write-Host "배포 묶음을 만들었습니다: $zip"
Write-Host "다른 PC에는 이 zip을 풀고 Docker Desktop 설치 후 start.bat을 실행하세요."
