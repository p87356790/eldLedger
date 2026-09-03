$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
docker compose down
Write-Host "eldLedger를 중지했습니다. 장부 파일은 data 폴더에 그대로 있습니다."
