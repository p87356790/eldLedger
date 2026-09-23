# eldLedger

개인과 사업을 한 장부에서 다루는 자가 설치형 가계부입니다. 입력은 가계부처럼 하고, 내부에서 복식부기 분개를 만듭니다.

브라우저로만 사용합니다. Ubuntu 서버 또는 Windows에 Docker만 있으면 됩니다.

## 다른 기기에서 설치

자세한 단계는 [docs/INSTALL.md](docs/INSTALL.md) 를 보세요.

요약:

1. 이 PC에서 `scripts\package-release.ps1` 로 zip을 만듭니다.
   - **처음 설치:** `eldledger-날짜-install.zip` (`data` 빈 골격 포함)
   - **버전만 올리기:** `eldledger-날짜-upgrade.zip` (`data` 없음 → 기존 장부 유지)
   - **Windows 장부 → Ubuntu:** `eldledger-날짜-data.zip` (있을 때만, 실물 `data`)
2. **Ubuntu:** install zip을 풀고 Docker를 설치한 뒤 `bash start.sh`
3. **Windows:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) 실행 후 `start.bat`
4. 브라우저에서 http://서버주소:8080 이 열리면 관리자 계정을 만듭니다.

끄려면 Ubuntu는 `bash stop.sh`, Windows는 `stop.bat` 입니다. 장부 백업은 설정 → 데이터 백업/복원(자동 백업) 또는 `backup.sh` / `backup.bat` 입니다.

버전만 올리기: upgrade zip을 받은 뒤 Ubuntu는 `bash upgrade.sh`, Windows는 `upgrade.bat` (장부 `data` 유지).

## 개발자

- 백엔드: `backend` 에서 FastAPI (`http://127.0.0.1:8000`)
- 프론트: `frontend` 에서 Vite (`http://127.0.0.1:5173`)
- 배포 묶음: `scripts\package-release.ps1`
