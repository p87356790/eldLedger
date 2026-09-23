#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

stamp="$(date +%Y%m%d-%H%M%S)"
dest="$root/data/backups/eldledger-$stamp"
mkdir -p "$dest"

if [[ -d "$root/data/database" ]]; then
  cp -a "$root/data/database" "$dest/database"
fi
if [[ -d "$root/data/uploads" ]]; then
  cp -a "$root/data/uploads" "$dest/uploads"
fi

# 30일이 지난 자동/수동 백업은 삭제합니다.
if [[ -d "$root/data/backups" ]]; then
  find "$root/data/backups" -mindepth 1 -maxdepth 1 -name 'eldledger-*' -mtime +30 -exec rm -rf {} +
fi

echo "백업했습니다: $dest"
