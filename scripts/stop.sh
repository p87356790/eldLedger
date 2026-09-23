#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

docker_bin="docker"
if ! docker info >/dev/null 2>&1; then
  if sudo docker info >/dev/null 2>&1; then
    docker_bin="sudo docker"
  else
    echo "Docker가 실행 중이지 않습니다."
    exit 1
  fi
fi

$docker_bin compose down
echo "eldLedger를 중지했습니다. 장부 파일은 data 폴더에 그대로 있습니다."
