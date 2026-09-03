$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root "data\backups\eldledger-$stamp"
New-Item -ItemType Directory -Path $dest -Force | Out-Null

$database = Join-Path $root "data\database"
if (Test-Path $database) {
    Copy-Item -Path $database -Destination (Join-Path $dest "database") -Recurse -Force
}
$uploads = Join-Path $root "data\uploads"
if (Test-Path $uploads) {
    Copy-Item -Path $uploads -Destination (Join-Path $dest "uploads") -Recurse -Force
}

Write-Host "백업했습니다: $dest"
