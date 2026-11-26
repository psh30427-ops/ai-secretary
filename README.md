# 내 학사 일정을 아는 AI 비서

일반 ChatGPT는 내 일정을 모릅니다. "이번 주에 뭐 해야 해?"라고 물으면 일반적인 조언만 돌아옵니다.

이 서비스는 학교 LMS(한림 SmartLEAD)에서 가져온 **과제 마감, 퀴즈, 강의 시청 기한, 시험** 데이터를 Firestore에 저장하고 분석합니다. 분석한 **요약을 GPT 시스템 프롬프트에 넣어서**(컨텍스트 주입) 내 상황에 맞는 답을 줍니다.

- "이번 주에 뭐 해야 해?" → 다가오는 마감을 날짜·중요도 순으로 정리
- "이번 달이 지난달보다 바빠?" → 월별·주별 일정 수와 최근 추세로 비교
- 요약에 없는 일정은 지어내지 않고 "확인할 수 없다"고 답합니다

## 배포 URL

| 구분 | URL |
|---|---|
| 프론트엔드 (Vercel) | `https://<your-app>.vercel.app` |
| 백엔드 API (Render) | `https://<your-api>.onrender.com` |
| Swagger UI | `https://<your-api>.onrender.com/docs` |

> Render 무료 티어는 15분 동안 요청이 없으면 잠듭니다. 첫 접속은 30초~1분 걸릴 수 있습니다. 프론트는 페이지를 열 때 `/health`를 호출해 서버를 미리 깨우고, 3초 넘게 걸리면 안내 배너를 띄웁니다.

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 백엔드 | Python 3.10+, FastAPI, Uvicorn, Pydantic v2 |
| 데이터베이스 | Firebase Firestore (`firebase-admin`) |
| AI | OpenAI Chat Completions API (`openai`) |
| 설정 | `python-dotenv` (환경변수) |
| 프론트엔드 | 바닐라 HTML / CSS / JavaScript (프레임워크 없음) |
| 배포 | Render (백엔드), Vercel (프론트엔드) |

## 폴더 구조

```
backend/
  main.py                  FastAPI 앱, CORS, 예외 처리, /health
  app/config.py            환경변수 로딩, KST 시간대, CORS 출처
  app/errors.py            서비스 예외 (404 / 502 / 503으로 변환)
  app/routers/             HTTP 계층: 요청 받고 서비스 호출 (data, conversations, chat)
  app/services/            비즈니스 로직: Firestore CRUD, 요약 계산, OpenAI 호출
  app/schemas/             Pydantic 요청·응답 모델 (검증 규칙)
  scripts/seed.py          CSV → Firestore 초기 데이터 입력
  scripts/setup_env.py     서비스 계정 키 파일 → .env 생성 (base64 자동 변환)
  scripts/check_setup.py   환경변수, Firestore, OpenAI 연결 점검
  tests/                   단위·API 테스트 (Firestore·OpenAI 대역 사용, 키 불필요)
  requirements.txt
  .env.example
frontend/
  index.html  style.css  app.js
  config.js                로컬용 API 주소 (기본 http://localhost:8000)
  build-config.js          Vercel 빌드 때 API_BASE_URL로 dist/config.js 생성
  vercel.json
data/
  smartlead_seed.csv       초기 데이터 (개인 정보라 git에 올리지 않음)
```

## 데이터 모델

### `data` 컬렉션: 과제 형식 `(date, value, memo)`

| 필드 | 형식 | 설명 |
|---|---|---|
| `date` | `YYYY-MM-DD` 문자열 | 마감일 또는 일정 날짜 |
| `value` | 정수 1~5 | 중요도. 시험 5, 과제 4, 퀴즈 3, 강의시청 2, 법정교육·신청·개인 1 |
| `memo` | 1~200자 | `[분류] 강좌 - 제목 (마감 HH:MM)` |

분류(`시험 | 과제 | 퀴즈 | 강의시청 | 법정교육 | 신청 | 개인`)는 필드를 따로 두지 않고 memo의 `[ ]`에서 읽습니다.
SmartLEAD는 "23:59 마감"을 다음 날 00:00으로 저장하기 때문에, 이런 일정은 전날 날짜에 `(마감 24:00)`으로 넣었습니다.

### `conversations` 컬렉션

```json
{
  "title": "이번 주에 뭐 해야 해?",
  "created_at": "2026-11-26T15:18:00+09:00",
  "updated_at": "2026-11-26T15:19:10+09:00",
  "message_count": 2,
  "messages": [
    {"role": "user", "content": "...", "created_at": "..."},
    {"role": "assistant", "content": "...", "created_at": "..."}
  ]
}
```

`message_count`를 따로 저장해서, 목록을 조회할 때 messages 전체를 읽지 않아도 됩니다.

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스 체크 (콜드스타트 깨우기용) |
| POST | `/api/data` | 일정 추가 |
| GET | `/api/data?from=&to=` | 일정 목록 (date 오름차순, 기간 필터 선택) |
| PUT | `/api/data/{id}` | 일정 수정 (전체 교체) |
| DELETE | `/api/data/{id}` | 일정 삭제 |
| GET | `/api/data/summary` | 데이터 요약 (프롬프트 주입용) |
| POST | `/api/conversations` | 대화 저장 |
| GET | `/api/conversations` | 대화 목록: id, 제목, 생성 시각, 메시지 수 (messages 미포함) |
| GET | `/api/conversations/{id}` | 대화 불러오기: 전체 messages (과제 옵션 A) |
| DELETE | `/api/conversations/{id}` | 대화 삭제 |
| POST | `/api/chat` | `{message, conversation_id?}` → `{conversation_id, reply}` |

### `/api/data/summary`가 반환하는 것

- `today`: 기준일 (Asia/Seoul)
- `period`, `count`: 데이터 기간과 전체 개수
- `value_stats`: 중요도의 평균, 최대, 최소
- `category_counts`: 분류별 개수
- `weekly_counts`, `monthly_counts`: 주별(월요일 시작)·월별 건수
- `trend`: 오늘을 포함한 최근 14일과 그 전 14일의 주평균 건수를 비교합니다. 변화율이 ±20%(`TREND_THRESHOLD`)를 넘으면 증가/감소, 아니면 유지입니다
- `upcoming`: 오늘 이후 가장 가까운 마감 10건 (같은 날이면 마감 시각 순)

### `/api/chat` 동작 흐름 (컨텍스트 주입)

1. `summary_service.get_summary()`로 데이터 요약을 계산합니다
2. 요약 JSON을 시스템 프롬프트에 넣습니다 (`chat_service.SYSTEM_PROMPT_TEMPLATE`). "요약에 없는 일정은 지어내지 말 것"이라는 규칙도 함께 넣습니다
3. 이전 대화(최근 20개 메시지)와 새 질문을 붙여 OpenAI를 호출합니다
4. 질문과 답변을 `conversations`에 자동 저장합니다. 새 대화면 문서를 만들고 id를 돌려줍니다

## 로컬 실행 방법 (Windows PowerShell)

### 1. 준비물
- Python 3.10 이상 (`python --version`으로 확인)
- Firebase 서비스 계정 키(JSON)와 OpenAI API 키 (아래 "배포 안내"의 1~2단계 참고)

### 2. 백엔드

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `Activate.ps1` 실행이 막히면 먼저 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`를 실행하세요. 현재 PowerShell 창에서만 적용됩니다.

`.env` 파일을 만듭니다. 키 파일 경로만 주면 base64 변환까지 스크립트가 대신 합니다. OpenAI 키와 모델 이름은 물어볼 때 입력하거나, 아직 없으면 Enter로 건너뛰세요.

```powershell
python scripts\setup_env.py C:\keys\firebase-key.json
```

> 직접 하려면 `Copy-Item .env.example .env`로 파일을 만든 뒤, `[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\keys\firebase-key.json")) | Set-Clipboard`로 복사한 값을 `FIREBASE_CREDENTIALS_BASE64=` 뒤에 붙여 넣으면 됩니다. **`OPENAI_MODEL`은 기본값이 없으니 꼭 설정하세요.**

연결을 점검합니다. 키 값은 화면에 나오지 않습니다.

```powershell
python scripts\check_setup.py               # 환경변수, Firestore, OpenAI 모두
python scripts\check_setup.py --skip-openai # OpenAI 키가 아직 없을 때
```

초기 데이터를 넣고 서버를 실행합니다.

```powershell
python scripts\seed.py --dry-run   # CSV 검증만 (Firestore에 쓰지 않음)
python scripts\seed.py             # Firestore에 저장. 같은 (date, memo)는 건너뜀
uvicorn main:app --reload
```

http://localhost:8000/docs 에서 Swagger UI를 확인합니다.

### 3. 프론트엔드 (새 PowerShell 창)

```powershell
cd frontend
python -m http.server 5500
```

http://localhost:5500 을 엽니다. `frontend/config.js`의 기본 API 주소가 `http://localhost:8000`이라 따로 설정할 것은 없습니다.

### 4. 테스트 (키 없이 실행 가능)

```powershell
cd backend
python -m unittest discover -s tests -t .
```

- `test_summary.py`: 요약 계산 (기간, 통계, 분류, 주별, 추세 경계값, 다가오는 마감, 오늘 날짜 주입)
- `test_schemas.py`: Pydantic 검증 (잘못된 날짜·중요도·memo 거부)
- `test_api.py`: Firestore·OpenAI를 가짜 객체로 바꿔 전체 API 흐름 확인 (CRUD, 대화 저장·불러오기, 채팅 때 요약 주입과 자동 저장, 키가 없을 때 503)

### 데이터 100건 채우기

CSV에는 89건이 있습니다. 과제 요건(100건 이상)을 채우려면 화면의 **데이터 관리** 탭에서 `[신청]`, `[개인]` 일정을 11건 이상 추가하세요. 분류를 고르면 중요도 기본값이 자동으로 들어갑니다.

## 환경 변수

### 백엔드 (`backend/.env`, Render)

| 이름 | 필수 | 설명 |
|---|---|---|
| `FIREBASE_CREDENTIALS_BASE64` | ✅ | Firebase 서비스 계정 JSON 전체를 base64로 인코딩한 한 줄 |
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `OPENAI_MODEL` | ✅ | 사용할 모델 이름 (기본값 없음) |
| `ALLOWED_ORIGINS` | 배포 때 ✅ | CORS 허용 출처, 쉼표로 구분, 끝에 `/` 없이. 비우면 `http://localhost:5500`, `http://127.0.0.1:5500`만 허용 |

### 프론트엔드 (Vercel)

| 이름 | 필수 | 설명 |
|---|---|---|
| `API_BASE_URL` | ✅ | 백엔드 주소 (예: `https://<your-api>.onrender.com`) |

> 키는 코드에 쓰지 않습니다. `.env`, 서비스 계정 JSON, `data/*.csv`는 `.gitignore`에 들어 있습니다.

## 배포 안내 (직접 진행)

### 1. Firebase 준비
1. [Firebase 콘솔](https://console.firebase.google.com)에서 프로젝트를 만듭니다
2. **빌드 → Firestore Database → 데이터베이스 만들기**를 누릅니다. 위치는 `asia-northeast3 (서울)`을 권장합니다. 서버에서 Admin SDK로만 접근하므로 프로덕션 모드로 만들어도 됩니다
3. **프로젝트 설정(톱니바퀴) → 서비스 계정 → 새 비공개 키 생성**을 눌러 JSON을 받습니다. 이 파일은 저장소 폴더 밖에 보관하세요
4. 위 "로컬 실행 방법"대로 base64 값을 만들어 둡니다

### 2. OpenAI 준비
[OpenAI 플랫폼](https://platform.openai.com)에서 API 키를 만들고, 사용할 모델 이름을 정합니다.

### 3. GitHub에 올리기
```powershell
git status   # .env, data\*.csv, 서비스 계정 JSON이 목록에 없는지 꼭 확인
git add .
git commit -m "학사 일정 AI 비서"
git push
```

### 4. 백엔드 배포 (Render)
1. [Render](https://render.com)에서 **New → Web Service**를 누르고 GitHub 저장소를 연결합니다
2. 다음처럼 설정합니다
   - Root Directory: `backend`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Instance Type: Free
3. **Environment**에 `FIREBASE_CREDENTIALS_BASE64`, `OPENAI_API_KEY`, `OPENAI_MODEL`을 넣습니다. `ALLOWED_ORIGINS`는 5단계에서 Vercel 주소가 나온 뒤 넣습니다
4. (선택) Settings → Health Check Path를 `/health`로 지정합니다
5. 배포가 끝나면 `https://<your-api>.onrender.com/docs`가 열리는지 확인합니다

### 5. 프론트엔드 배포 (Vercel)
1. [Vercel](https://vercel.com)에서 **Add New → Project**를 누르고 같은 저장소를 가져옵니다
2. **Root Directory**를 `frontend`로, Framework Preset을 `Other`로 둡니다. 빌드 명령과 출력 폴더는 `frontend/vercel.json`에 있습니다 (`node build-config.js`, `dist`)
3. **Environment Variables**에 `API_BASE_URL` = Render 주소(끝에 `/` 없이)를 넣고 Deploy를 누릅니다
   - 정적 사이트는 브라우저에서 환경변수를 읽을 수 없습니다. 그래서 빌드 때 `build-config.js`가 이 값으로 `config.js`를 만듭니다. **값을 바꾸면 Redeploy해야** 반영됩니다
   - `API_BASE_URL`이 비어 있으면 빌드가 일부러 실패합니다

### 6. CORS 연결
1. Render → Environment에서 `ALLOWED_ORIGINS`에 Vercel 주소를 넣습니다. 예: `https://<your-app>.vercel.app,http://localhost:5500`
2. 저장하고 재배포한 뒤 Vercel 사이트에서 요약, 채팅, 데이터 추가가 되는지 확인합니다
3. 브라우저 콘솔에 CORS 오류가 나면 주소 철자와 끝의 `/`를 확인하세요

### 7. 데이터 넣기
로컬 PC에서 `.env`가 배포와 같은 Firebase 프로젝트를 가리키면, `python scripts\seed.py`로 넣은 데이터가 배포 서비스에도 그대로 보입니다.

## 스크린샷

| 화면 | 이미지 |
|---|---|
| 데이터 요약이 보이는 채팅 (질문+답변) | `docs/screenshots/chat.png` |
| 데이터 관리 (추가·수정·삭제) | `docs/screenshots/data.png` |
| 대화 기록 불러오기 | `docs/screenshots/history.png` |

<!-- 배포 후 캡처해서 docs/screenshots/에 넣고 아래 주석을 해제하세요
![채팅 + 요약](docs/screenshots/chat.png)
![데이터 관리](docs/screenshots/data.png)
![대화 불러오기](docs/screenshots/history.png)
-->

## 설계 메모

- **라우터와 서비스 분리**: 라우터는 HTTP(경로, 상태 코드, 의존성 주입)만 담당하고, Firestore·OpenAI를 다루는 로직은 서비스에 둡니다. 그래서 요약 계산(`build_summary`)은 DB 없이 단위 테스트할 수 있고, 테스트에서는 `dependency_overrides`로 DB와 OpenAI를 가짜 객체로 바꿀 수 있습니다
- **Pydantic 검증**: 잘못된 요청을 저장 전에 422로 막습니다. Pydantic은 기본적으로 `"3"`이나 `true`를 정수로, 숫자 타임스탬프를 날짜로 바꿔 받아 주기 때문에, `StrictInt`와 `YYYY-MM-DD` 형식 검사로 과제 형식만 허용했습니다
- **컨텍스트 주입**: 모델을 다시 학습시키지 않고 매 요청마다 최신 요약을 시스템 프롬프트에 넣습니다. 데이터를 고치면 다음 질문부터 바로 반영됩니다. 원본 전체 대신 요약만 넣어 토큰 비용을 줄입니다
- **시간대**: 한국은 서머타임이 없어서 UTC+9 고정 오프셋을 씁니다. `zoneinfo`는 Windows에서 `tzdata` 패키지가 따로 필요해서 쓰지 않았습니다
- **배포 보안**: 키는 환경변수로만 받고, 키가 없으면 500 대신 이유가 담긴 503을 돌려줍니다. CORS는 허용한 프론트 주소에서만 브라우저 요청을 받도록 제한합니다
