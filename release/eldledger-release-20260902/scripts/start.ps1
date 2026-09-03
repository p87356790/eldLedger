$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-Docker {
    try {
        docker info | Out-Null
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-Docker)) {
    Write-Host "Docker Desktop가 실행 중이지 않습니다."
    Write-Host "Docker Desktop을 설치하고 실행한 다음, 이 파일을 다시 눌러 주세요."
    Write-Host "설치: https://www.docker.com/products/docker-desktop/"
    exit 1
}

foreach ($name in @("database", "uploads", "reports", "backups")) {
    $path = Join-Path $root "data\$name"
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

$envFile = Join-Path $root ".env"
$example = Join-Path $root ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $example $envFile
}

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = -join ($bytes | ForEach-Object { $_.ToString("x2") })

function Test-PortBusy([int]$Port) {
    $mapped = docker ps --format "{{.Ports}}" 2>$null | Select-String -SimpleMatch ":${Port}->"
    if ($null -ne $mapped) {
        return $true
    }
    $listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $listen
}

function Set-EnvValue([string]$Text, [string]$Key, [string]$Value) {
    $pattern = "(?m)^$Key=.*$"
    if ($Text -match $pattern) {
        return [regex]::Replace($Text, $pattern, "$Key=$Value")
    }
    return $Text.TrimEnd() + "`r`n$Key=$Value`r`n"
}

$envText = Get-Content -Raw -Path $envFile
$utf8 = New-Object System.Text.UTF8Encoding $false

if ($envText -match "(?m)^SECRET_KEY=change-me-in-production\s*$") {
    $envText = Set-EnvValue $envText "SECRET_KEY" $secret
    Write-Host "비밀키를 새로 만들었습니다."
}

$preferred = 8080
if ($envText -match "(?m)^FRONTEND_PORT=(\d+)") {
    $preferred = [int]$Matches[1]
}
$port = $preferred
if (Test-PortBusy $port) {
    foreach ($candidate in @(8180, 8280, 8380, 18080)) {
        if (-not (Test-PortBusy $candidate)) {
            $port = $candidate
            break
        }
    }
    if ($port -ne $preferred) {
        Write-Host "포트 $preferred 는 다른 프로그램이 쓰고 있어서 $port 로 엽니다."
        $envText = Set-EnvValue $envText "FRONTEND_PORT" "$port"
        $envText = Set-EnvValue $envText "BACKEND_CORS_ORIGINS" "http://localhost:$port,http://127.0.0.1:$port"
    }
}

[System.IO.File]::WriteAllText($envFile, $envText.TrimEnd() + "`n", $utf8)

Write-Host "eldLedger를 준비하고 있습니다. 처음이면 몇 분 걸릴 수 있습니다."
docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "실행에 실패했습니다. Docker Desktop이 켜져 있는지 확인해 주세요."
    exit $LASTEXITCODE
}

$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            $ok = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ok) {
    Write-Host "서버가 아직 준비되지 않았습니다. 잠시 후 브라우저에서 http://localhost:$port 을 열어 보세요."
    exit 0
}

Write-Host "준비되었습니다. 브라우저를 엽니다: http://localhost:$port"
Start-Process "http://localhost:$port"
