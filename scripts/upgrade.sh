#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [[ ! -f "$root/docker-compose.yml" ]]; then
  echo "이 스크립트는 eldLedger 설치 폴더에서 실행해야 합니다."
  exit 1
fi

find_zip() {
  local hint="${1:-}"
  if [[ -n "$hint" ]]; then
    if [[ -f "$hint" ]]; then
      printf '%s\n' "$hint"
      return 0
    fi
    echo "zip 파일을 찾을 수 없습니다: $hint"
    return 1
  fi

  local candidates=()
  local dir
  for dir in "$root" "$root/.." "$HOME" "$HOME/Downloads" "$HOME/다운로드"; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r -d '' f; do
      candidates+=("$f")
    done < <(find "$dir" -maxdepth 1 -type f \( -name 'eldledger-*-upgrade.zip' -o -name 'eldledger-*-install.zip' \) -print0 2>/dev/null || true)
  done

  if [[ ${#candidates[@]} -eq 0 ]]; then
    echo "업그레이드 zip을 찾지 못했습니다."
    echo "사용법: bash upgrade.sh /경로/eldledger-날짜-upgrade.zip"
    echo "또는 upgrade zip을 홈/~Downloads/설치폴더 옆에 두고 bash upgrade.sh"
    return 1
  fi

  local newest=""
  local newest_mtime=0
  local f mtime
  for f in "${candidates[@]}"; do
    mtime="$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f")"
    if (( mtime >= newest_mtime )); then
      newest_mtime=$mtime
      newest=$f
    fi
  done
  printf '%s\n' "$newest"
}

zip_path="$(find_zip "${1:-}")"
echo "사용할 zip: $zip_path"

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip 이 필요합니다: sudo apt install -y unzip"
  exit 1
fi

echo "업그레이드 전 백업을 만듭니다..."
bash "$root/scripts/backup.sh" || true

echo "서버를 잠시 멈춥니다..."
bash "$root/scripts/stop.sh" || true

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

unzip -q -o "$zip_path" -d "$tmpdir"

payload="$tmpdir"
if [[ ! -f "$payload/docker-compose.yml" ]]; then
  found="$(find "$tmpdir" -maxdepth 3 -type f -name docker-compose.yml | head -n 1 || true)"
  if [[ -z "$found" ]]; then
    echo "zip 안에 docker-compose.yml 이 없습니다. 올바른 eldLedger zip인지 확인하세요."
    exit 1
  fi
  payload="$(dirname "$found")"
fi

echo "파일을 덮어씁니다. data/ 와 .env 는 그대로 둡니다."
shopt -s dotglob nullglob
for item in "$payload"/*; do
  name="$(basename "$item")"
  if [[ "$name" == "data" || "$name" == ".env" ]]; then
    continue
  fi
  if [[ -d "$item" ]]; then
    mkdir -p "$root/$name"
    # 폴더는 내용만 갱신 (기존 data는 위에서 skip)
    cp -a "$item"/. "$root/$name"/
  else
    cp -a "$item" "$root/$name"
  fi
done
shopt -u dotglob nullglob

# LF 유지 (Windows에서 만든 zip일 수 있음)
find "$root" -type f -name '*.sh' -print0 | while IFS= read -r -d '' shfile; do
  sed -i 's/\r$//' "$shfile" 2>/dev/null || true
done
chmod +x "$root"/start.sh "$root"/stop.sh "$root"/backup.sh "$root"/upgrade.sh 2>/dev/null || true
chmod +x "$root"/scripts/*.sh 2>/dev/null || true

echo "다시 켭니다..."
export BUILD_ID="$(date +%Y%m%d%H%M%S)"
export ELDLEDGER_FORCE_RECREATE=1
bash "$root/scripts/start.sh"
echo "업그레이드가 끝났습니다. data/ 장부는 그대로입니다."
