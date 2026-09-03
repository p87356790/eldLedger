# eldLedger

개인과 사업을 한 장부에서 다루는 자가 설치형 가계부입니다. 입력은 가계부처럼 하고, 내부에서 복식부기 분개를 만듭니다.

브라우저로만 사용합니다. Windows에 따로 프로그램을 설치하지 않습니다.

## 다른 PC에 설치

자세한 단계는 [docs/INSTALL.md](docs/INSTALL.md) 를 보세요.

요약:

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) 을 설치하고 실행합니다.
2. 이 폴더를 USB나 공유 폴더로 복사합니다. (`release\eldledger-날짜.zip` 을 풀어도 됩니다.)
3. `start.bat` 을 더블클릭합니다.
4. 브라우저에서 http://localhost:8080 이 열리면 관리자 계정을 만듭니다.

끄려면 `stop.bat`, 장부 백업은 `backup.bat` 입니다.

## 개발자

- 백엔드: `backend` 에서 FastAPI (`http://127.0.0.1:8000`)
- 프론트: `frontend` 에서 Vite (`http://127.0.0.1:5173`)
- 배포 묶음: `scripts\package-release.ps1`
