#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

docker_bin="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    echo "Docker는 설치되어 있지만 이 계정으로 바로 쓸 수 없습니다."
    echo "한 번만 실행하세요: sudo usermod -aG docker $USER"
    echo "적용하려면 로그아웃 후 다시 로그인하세요. 지금은 sudo로 실행합니다."
    docker_bin="sudo docker"
  else
    echo "Docker가 실행 중이지 않습니다."
    echo "Ubuntu에서는 다음을 실행한 뒤 이 스크립트를 다시 돌려 주세요."
    echo "  curl -fsSL https://get.docker.com | sudo sh"
    echo "  sudo usermod -aG docker \$USER"
    exit 1
  fi
fi

compose() {
  $docker_bin compose "$@"
}

if ! compose version >/dev/null 2>&1; then
  echo "docker compose 플러그인이 없습니다. Docker를 다시 설치해 주세요."
  exit 1
fi

for name in database uploads reports backups; do
  mkdir -p "$root/data/$name"
done

env_file="$root/.env"
example="$root/.env.example"
if [[ ! -f "$env_file" ]]; then
  cp "$example" "$env_file"
fi

set_env_value() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

if grep -qE '^SECRET_KEY=change-me-in-production[[:space:]]*$' "$env_file"; then
  if command -v openssl >/dev/null 2>&1; then
    secret="$(openssl rand -hex 32)"
  else
    secret="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  fi
  set_env_value SECRET_KEY "$secret"
  echo "비밀키를 새로 만들었습니다."
fi

preferred=8080
if grep -qE '^FRONTEND_PORT=[0-9]+' "$env_file"; then
  preferred="$(sed -n 's/^FRONTEND_PORT=//p' "$env_file" | head -n 1 | tr -d '[:space:]')"
fi

port_busy() {
  local port="$1"
  if $docker_bin ps --format '{{.Ports}}' 2>/dev/null | grep -q ":${port}->"; then
    return 0
  fi
  if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE ":${port}[[:space:]]"; then
    return 0
  fi
  return 1
}

port="$preferred"
if port_busy "$port"; then
  for candidate in 8180 8280 8380 18080; do
    if ! port_busy "$candidate"; then
      port="$candidate"
      break
    fi
  done
  if [[ "$port" != "$preferred" ]]; then
    echo "포트 $preferred 는 다른 프로그램이 쓰고 있어서 $port 로 엽니다."
    set_env_value FRONTEND_PORT "$port"
    set_env_value BACKEND_CORS_ORIGINS "http://localhost:${port},http://127.0.0.1:${port}"
  fi
fi

echo "eldLedger를 준비하고 있습니다. 처음이면 몇 분 걸릴 수 있습니다."
up_args=(up -d --build)
if [[ "${ELDLEDGER_FORCE_RECREATE:-}" == "1" ]]; then
  if [[ -z "${BUILD_ID:-}" ]]; then
    BUILD_ID="$(date +%Y%m%d%H%M%S)"
  fi
  export BUILD_ID
  echo "업데이트라서 화면(프론트) 이미지를 다시 만듭니다. BUILD_ID=$BUILD_ID"
  compose build --no-cache --build-arg BUILD_ID="$BUILD_ID" frontend
  up_args=(up -d --build --force-recreate --remove-orphans)
fi
compose "${up_args[@]}"

ok=0
for _ in $(seq 1 60); do
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 3 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
  elif command -v wget >/dev/null 2>&1; then
    if wget -q -O /dev/null --timeout=3 "http://127.0.0.1:${port}/health"; then
      ok=1
      break
    fi
  else
    sleep 2
    continue
  fi
  sleep 2
done

if [[ "$ok" -ne 1 ]]; then
  echo "서버가 아직 준비되지 않았습니다. 잠시 후 브라우저에서 http://서버주소:${port} 을 열어 보세요."
  exit 0
fi

echo "준비되었습니다. 브라우저에서 여세요: http://서버주소:${port}"
echo "이 서버에서 열려면: http://127.0.0.1:${port}"
