# eldLedger 설치 안내

브라우저만 있으면 됩니다. Python이나 Node는 설치하지 않아도 됩니다.

- **Ubuntu 서버:** Docker Engine + `bash start.sh`
- **Windows PC:** Docker Desktop + `start.bat`

권장: 메모리 8GB 이상, 디스크 여유 2GB 이상, 인터넷(처음 이미지 받을 때).

---

## 1. 이 PC에서 배포 묶음 만들기

이미 작업 중인 Windows PC에서:

```text
powershell -ExecutionPolicy Bypass -File scripts\package-release.ps1
```

`release` 폴더에 zip이 **두세 개** 생깁니다.

| 파일 | 언제 쓰나 | `data` 폴더 |
| --- | --- | --- |
| `eldledger-날짜-install.zip` | **처음 설치** | 빈 골격 포함 (장부 DB는 없음) |
| `eldledger-날짜-upgrade.zip` | **이미 쓰는 서버만 버전 올리기** | **없음** (기존 장부를 덮지 않음) |
| `eldledger-날짜-data.zip` | Windows에서 쓰던 장부를 Ubuntu로 **옮길 때** | 지금 PC의 `data` 실물 |

복사하지 마세요.

- `backend\.venv`
- `frontend\node_modules`
- `.git` (없어도 실행됩니다)

---

## 2. Ubuntu 서버에 설치

### 2-1. zip 복사 (처음 설치)

Windows에서 (PowerShell, 서버 주소·계정만 바꾸세요):

```text
scp release\eldledger-날짜-install.zip 사용자이름@서버주소:~/
```

USB나 공유 폴더로 복사해도 됩니다.

Ubuntu에서:

```bash
sudo apt update
sudo apt install -y unzip
cd ~
unzip eldledger-날짜-install.zip -d eldledger
cd eldledger
```

zip을 풀었을 때 `docker-compose.yml` 과 `start.sh` 가 바로 보여야 합니다. 한 단계 더 들어간 폴더에 있으면 그 안으로 `cd` 하세요.

### 2-2. Docker 설치

한 번도 Docker를 안 넣었다면:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

적용하려면 **로그아웃 후 다시 SSH 접속**하세요. 확인:

```bash
docker version
docker compose version
```

둘 다 버전이 나오면 됩니다.

### 2-3. 실행

```bash
bash start.sh
```

처음에는 이미지를 만드는 데 수 분이 걸립니다. 끝나면:

```text
http://서버IP:8080
```

처음이면 관리자 이름·비밀번호를 만드는 화면이 나옵니다. 이 비밀번호를 기억해 두세요.

서버 IP는 Ubuntu에서:

```bash
hostname -I
```

방화벽을 쓰고 있으면 **8080만** 엽니다. 백엔드 8000은 열지 마세요.

```bash
sudo ufw allow 8080/tcp
sudo ufw reload
```

### 2-4. 끄기 / 다시 켜기 / 백업

| 동작 | 방법 |
| --- | --- |
| 끄기 | `bash stop.sh` |
| 다시 켜기 | `bash start.sh` |
| 장부 백업 | 설정 → 데이터 백업/복원에서 자동 백업을 켜거나, `bash backup.sh` → `data/backups/` |
| 서버를 켜면 자동으로 | `restart: unless-stopped` 이므로 Docker만 켜져 있으면 컨테이너도 다시 뜹니다 |

장부는 `stop.sh` 를 눌러도 지워지지 않습니다. `data/database/eldledger.db` 에 있습니다. 영수증은 `data/uploads/연-월/` 입니다.

### 2-5. 이미 설치된 Ubuntu만 버전 올리기 (업그레이드)

가장 쉬운 방법:

1. Windows에서 `eldledger-날짜-upgrade.zip` 을 서버로 복사합니다. (홈 폴더나 `~/Downloads` 에 두면 됩니다)
2. 설치 폴더에서 한 줄만 실행합니다.

```bash
cd ~/eldledger
bash upgrade.sh ~/eldledger-날짜-upgrade.zip
```

인자 없이 `bash upgrade.sh` 만 해도, 홈/`Downloads`/설치 폴더 옆에서 가장 최근 `*upgrade*.zip` 을 찾아 씁니다.

스크립트가 백업 → 중지 → 파일 덮어쓰기 → 다시 시작까지 합니다. **`data/` 와 `.env` 는 건드리지 않습니다.**

### 2-6. Windows에서 쓰던 장부를 Ubuntu와 같게 쓰기

Windows PC의 `data` 를 Ubuntu 설치 폴더로 옮기면 같은 장부가 됩니다. **양쪽에 동시에 쓰지 마세요.** SQLite는 한 쪽이 쓰는 동안 다른 쪽이 같은 파일을 열면 깨질 수 있습니다.

1. Windows에서 `stop.bat` (또는 Docker 중지), Ubuntu에서도 `bash stop.sh`
2. Windows에서 `package-release.ps1` 을 돌렸다면 `eldledger-날짜-data.zip` 을 서버로 복사합니다.  
   없으면 Windows의 `data` 폴더 전체를 복사해도 됩니다.
3. Ubuntu 설치 폴더에서:

```bash
cd ~/eldledger
bash stop.sh
# 기존 Ubuntu 장부를 지우고 Windows 장부로 바꿉니다.
rm -rf data
unzip -o ~/eldledger-날짜-data.zip -d .
# zip 안에 data/ 가 바로 오면 됩니다.
bash start.sh
```

로그인 계정·거래·영수증이 Windows와 같아야 합니다. 로그인 비밀키(`.env`의 `SECRET_KEY`)까지 같게 하려면 Windows `.env` 도 같이 복사하세요. 비밀키만 다르면 장부는 같아도 기존 로그인 세션은 다시 잡아야 할 수 있습니다.

이후에는 **Ubuntu만** 쓰거나, 가끔 Windows로 다시 옮길 때도 같은 방식으로 `data` 만 복사하세요. 실시간 공유 폴더(SMB 등으로 동시에 마운트)는 쓰지 않는 편이 안전합니다.

---

## 3. Windows PC에 설치

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) 을 설치하고 실행합니다.
2. **`eldledger-날짜-install.zip`** 을 풉니다.
3. **`start.bat`** 을 더블클릭합니다.
4. 브라우저에서 http://localhost:8080 이 열리면 관리자 계정을 만듭니다.

끄려면 `stop.bat`, 장부 백업은 설정 → 데이터 백업/복원에서 자동 백업을 켜거나 `backup.bat` 입니다.

이미 쓰는 Windows PC만 버전 올리려면 `upgrade` zip을 Downloads나 설치 폴더에 두고 **`upgrade.bat`** 을 더블클릭하면 됩니다. (`data` / `.env` 유지)

같은 와이파이의 휴대폰·다른 컴퓨터에서는 서버 PC의 IP로 접속합니다.

```text
http://192.168.x.x:8080
```

IP는 Windows에서 `ipconfig` 의 IPv4 주소를 보면 됩니다. 방화벽이 8080을 막으면 허용해 주세요.

---

## 4. 문제 해결

**`Can't connect to server` / 연결이 거절됨**

- Ubuntu: `docker compose ps` 로 컨테이너가 Up 인지 확인합니다. `bash start.sh` 를 다시 실행합니다.
- Windows: Docker Desktop이 실행 중인지 확인한 뒤 `start.bat` 을 다시 실행합니다.
- 개발용 주소 `http://127.0.0.1:5173` 은 Docker 설치본이 아닙니다. 설치본은 **8080** 입니다.

**`SECRET_KEY를 .env에 넣어 주세요`**

- `bash start.sh` 또는 `start.bat` 을 사용하세요. `.env` 가 없으면 예시를 복사하고 비밀키를 만듭니다.
- 직접 `docker compose up` 을 쓰면 먼저 `.env.example` 을 `.env` 로 복사하고 `SECRET_KEY` 를 긴 임의 문자열로 바꾸세요.

**포트 8080이 이미 사용 중**

- `start.sh` / `start.bat` 이 8080이 막혀 있으면 8180 등으로 자동으로 바꿉니다. 화면에 나온 주소를 여세요.
- 직접 정하려면 `.env` 에서 `FRONTEND_PORT=8180` 처럼 바꾼 뒤 다시 실행합니다.

**처음 실행이 오래 걸리거나 실패**

- 인터넷이 되는지 확인합니다. Ubuntu는 `docker compose logs` 로 원인을 볼 수 있습니다.
- `permission denied` 가 나오면 `sudo usermod -aG docker $USER` 후 다시 로그인하세요.

**화면은 뜨는데 저장이 안 됨**

- 주소창이 `서버IP:8080` 또는 `localhost:8080` 인지 확인합니다. `file://` 로 HTML을 열면 동작하지 않습니다.

**개발 화면(5173/5174)은 바뀌었는데 서버(8080)는 그대로**

- `http://127.0.0.1:5173` 은 이 PC의 개발용입니다. 설치본·서버는 **8080** 입니다.
- zip만 만들고 서버에서 `upgrade.sh` / `upgrade.bat` 을 실행하지 않으면 Docker 안의 예전 화면이 그대로입니다.
- 서버에서 업그레이드를 돌린 뒤에는 브라우저에서 Ctrl+F5 로 새로고침하세요.
- 확인: 브라우저에서 `http://서버주소:8080/version.json` 에 `가계부 V00.01` 같은 값이 나와야 합니다.

---

## 5. 데이터 위치

| 내용 | 위치 |
| --- | --- |
| 장부(SQLite) | `data/database/eldledger.db` |
| 영수증 | `data/uploads/` (월별 폴더) |
| 백업 | `data/backups/` (30일이 지나면 자동 삭제) |

이 폴더만 안전한 곳에 복사해 두면 장부를 옮길 수 있습니다.
