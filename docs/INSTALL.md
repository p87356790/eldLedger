# eldLedger 설치 안내

다른 Windows PC에서 장부를 쓰려면 **Docker Desktop**만 있으면 됩니다. Python이나 Node는 설치하지 않아도 됩니다. 사용은 Chrome 또는 Edge에서 합니다.

권장: Windows 11, 메모리 8GB 이상, 디스크 여유 2GB 이상.

---

## 1. 무엇을 복사하나요

아래 중 하나만 있으면 됩니다.

- 이 프로젝트 폴더 전체 (`eldLedger`)
- 또는 `release\eldledger-날짜.zip` 을 풀어 나온 폴더

장부 파일은 `data` 폴더에 생깁니다. 이미 쓰던 PC의 `data` 와 `.env` 를 함께 복사하면 기존 장부를 그대로 이어서 씁니다.

복사하지 마세요.

- `backend\.venv`
- `frontend\node_modules`
- `.git` (없어도 실행됩니다)

---

## 2. Docker Desktop 설치

1. https://www.docker.com/products/docker-desktop/ 에서 Docker Desktop을 받습니다.
2. 설치 후 PC를 재시작합니다.
3. Docker Desktop을 실행하고, 상태가 **Running** 이 될 때까지 기다립니다.
4. 처음이면 사용 약관에 동의하고, 계정이 없어도 로컬 실행은 가능합니다.

명령 프롬프트에서 확인:

```text
docker version
docker compose version
```

둘 다 버전이 나오면 준비된 것입니다.

WSL 2 또는 Hyper-V 안내가 나오면 Docker Desktop이 시키는 대로 따릅니다.

---

## 3. 실행

1. `eldLedger` 폴더를 엽니다.
2. **`start.bat`** 을 더블클릭합니다.
3. 처음에는 이미지를 받아 만드는 데 수 분이 걸릴 수 있습니다. 인터넷이 필요합니다.
4. 끝나면 브라우저가 **http://localhost:8080** 을 엽니다.
5. 처음이면 관리자 이름·비밀번호를 만드는 화면이 나옵니다. 이 비밀번호를 기억해 두세요.

같은 PC에서는 주소가 항상 `http://localhost:8080` 입니다.

같은 와이파이의 휴대폰·다른 컴퓨터에서는 서버 PC의 IP로 접속합니다.

```text
http://192.168.x.x:8080
```

IP는 서버 PC에서 `ipconfig` 의 IPv4 주소를 보면 됩니다. Windows 방화벽이 8080 포트를 막으면 허용해 주세요.

---

## 4. 끄기 / 다시 켜기

| 동작 | 방법 |
| --- | --- |
| 끄기 | `stop.bat` |
| 다시 켜기 | `start.bat` (이미 만들어 둔 이미지는 금방 뜹니다) |
| PC를 켜면 자동으로 | Docker Desktop이 켜져 있고 `restart: unless-stopped` 이므로, Docker만 자동 실행이면 컨테이너도 다시 뜹니다 |

장부는 `stop.bat` 을 눌러도 지워지지 않습니다. `data\database\eldledger.db` 에 있습니다.

---

## 5. 백업

`backup.bat` 을 실행하면 `data\backups\eldledger-날짜시간\` 아래에 데이터베이스와 영수증 사본이 생깁니다.

USB에 보관하려면 그 폴더와, 가능하면 `.env` 도 함께 복사하세요. `.env` 의 `SECRET_KEY` 가 바뀌면 로그인 세션만 만료되고, 비밀번호로 다시 로그인하면 됩니다.

---

## 6. 배포 묶음 만들기 (이 PC에서)

이미 Docker로 한 번 돌려 본 PC에서:

```text
powershell -ExecutionPolicy Bypass -File scripts\package-release.ps1
```

`release\eldledger-날짜.zip` 이 생깁니다. 이 파일을 다른 PC에 풀어 `start.bat` 을 실행하면 됩니다.

---

## 7. 문제 해결

**`Can't connect to server` / 연결이 거절됨**

- Docker Desktop이 실행 중인지 확인합니다.
- `start.bat` 을 다시 실행합니다.
- 개발용 주소 `http://127.0.0.1:5173` 은 Docker 설치본이 아닙니다. 설치본은 **8080** 입니다.

**`SECRET_KEY를 .env에 넣어 주세요`**

- `start.bat` 을 사용하세요. `.env` 가 없으면 예시를 복사하고 비밀키를 만듭니다.
- 직접 `docker compose up` 을 쓰면 먼저 `.env.example` 을 `.env` 로 복사하고 `SECRET_KEY` 를 긴 임의 문자열로 바꾸세요.

**포트 8080이 이미 사용 중**

- `start.bat` 이 8080이 막혀 있으면 8180 등으로 자동으로 바꿉니다. 화면에 나온 주소를 여세요.
- 직접 정하려면 `.env` 에서 `FRONTEND_PORT=8180` 처럼 바꾼 뒤 `start.bat` 을 다시 실행합니다.

**처음 실행이 오래 걸리거나 실패**

- 인터넷이 되는지 확인합니다. 이미지를 받을 때 필요합니다.
- Docker Desktop → Troubleshoot → Restart 후 `start.bat` 을 다시 누릅니다.

**화면은 뜨는데 저장이 안 됨**

- 주소창이 `localhost:8080` 인지 확인합니다. `file://` 로 HTML을 열면 동작하지 않습니다.

---

## 8. 데이터 위치

| 내용 | 위치 |
| --- | --- |
| 장부(SQLite) | `data\database\eldledger.db` |
| 영수증 | `data\uploads\` |
| 백업 | `data\backups\` |

이 폴더만 안전한 곳에 복사해 두면 장부를 옮길 수 있습니다.
