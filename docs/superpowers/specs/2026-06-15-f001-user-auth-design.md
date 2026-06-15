# F-001 사용자 정보 및 세션 관리 설계

## 개요

GoGoDoc에 PostgreSQL 기반 회원가입·로그인 기능과 Streamlit 세션 라우팅을 추가한다.
인증 성공 후 사용자 정보(성별·나이)를 세션 상태에 저장하여 파이프라인에 주입한다.

## 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| DB | PostgreSQL | 영구 저장 필요 |
| ORM | psycopg2 직접 SQL | 테이블 1개 MVP, 의존성 최소 |
| 비밀번호 해싱 | passlib + bcrypt | 솔트·인코딩 자동 처리, 오류 가능성 최소 |
| 아키텍처 | DB 레이어 분리 (포트 없음) | Hexagonal 일관성 유지하되 MVP 속도 확보 |
| 접속 정보 | .env + config.py | 기존 패턴 통일 |

## 파일 구조

```
gogodoc/
├── infrastructure/
│   ├── config.py                  ← DB 설정 필드 추가 (수정)
│   └── db/
│       ├── __init__.py            ← 신규
│       ├── connection.py          ← psycopg2 커넥션 풀 (신규)
│       ├── init_db.py             ← CREATE TABLE IF NOT EXISTS (신규)
│       └── user_repository.py     ← find_by_name, create (신규)
├── application/
│   └── auth_service.py            ← register / login (신규)
└── interfaces/
    └── streamlit_app.py           ← 로그인·회원가입 + 세션 라우팅 추가 (수정)
.env / .env.example                ← DB 접속 변수 추가 (수정)
```

변경하지 않는 파일: `domain/` 전체, `application/pipeline.py·ports.py·prompts.py`,
`infrastructure/llm/`, `infrastructure/pdf/`, `composition.py`, 기존 테스트 전체.

## 데이터베이스

### users 테이블 DDL

```sql
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    sex           VARCHAR(6) NOT NULL CHECK (sex IN ('male', 'female')),
    age           INTEGER NOT NULL CHECK (age >= 0 AND age <= 120),
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 환경 변수 (.env 추가 항목)

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gogodoc
DB_USER=postgres
DB_PASSWORD=
```

## 컴포넌트 설명

### `infrastructure/db/connection.py`

- `psycopg2.pool.SimpleConnectionPool`로 최소 1·최대 5 커넥션 풀 생성
- `get_conn()` / `put_conn(conn)` 헬퍼 제공
- Streamlit은 매 인터랙션마다 스크립트를 재실행하므로 풀 생성 함수에 `@st.cache_resource` 적용 — 앱 프로세스 생명주기 동안 풀을 한 번만 생성

### `infrastructure/db/init_db.py`

- `init_db(settings)` 한 함수로 풀 초기화 + 테이블 생성 수행
- `streamlit_app.py`의 `main()` 진입 시 한 번 호출

### `infrastructure/db/user_repository.py`

| 함수 | 설명 |
|------|------|
| `find_by_name(conn, name) → dict \| None` | 로그인 시 사용자 조회 |
| `create(conn, name, password_hash, sex, age) → None` | 회원가입 시 사용자 생성 |

### `application/auth_service.py`

| 함수 | 반환 | 설명 |
|------|------|------|
| `register(name, password, sex, age) → None` | - | 중복 이름 체크 후 bcrypt 해싱·저장 |
| `login(name, password) → dict` | `{name, sex, age}` | 비밀번호 검증, 실패 시 예외 |

**예외:**

| 클래스 | 발생 시점 |
|--------|-----------|
| `AuthError` | 비밀번호 불일치 또는 존재하지 않는 이름 |
| `DuplicateNameError` | 회원가입 시 이름 중복 |

## 세션 상태

| 키 | 타입 | 초기값 | 설명 |
|----|------|--------|------|
| `page` | str | `"login"` | 현재 페이지 라우팅 |
| `authenticated` | bool | `False` | 로그인 여부 |
| `user_name` | str | `""` | 로그인한 사용자 이름 |
| `sex` | str | `"male"` | 파이프라인 주입용 성별 |
| `age` | int | `40` | 파이프라인 주입용 나이 |

## 페이지 흐름

```
앱 시작
  └─ authenticated=False → login 페이지
       ├─ 로그인 성공 → session_state 설정 → dashboard
       └─ 회원가입 클릭 → signup
            └─ 가입 성공 → 자동 로그인 → dashboard

dashboard
  └─ "새 검진 해석하기" → analysis
       └─ UserProfile(sex=session_state.sex, age=session_state.age) 파이프라인 주입

로그아웃
  └─ session_state 전체 초기화 → login 페이지
```

## 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| DB 연결 실패 | `st.error()` 안내 후 중단 |
| 이름 중복 | `DuplicateNameError` → 회원가입 폼 `st.error()` |
| 비밀번호 불일치 | `AuthError` → 로그인 폼 `st.error()` |
| 빈 입력값 | UI 단 즉시 `st.warning()` |

## 테스트

```
tests/
└── application/
    └── test_auth_service.py
        ├── test_register_creates_user
        ├── test_register_duplicate_name_raises
        ├── test_login_success
        ├── test_login_wrong_password_raises
        └── test_login_unknown_name_raises
```

DB 없이 실행: `user_repository` 함수를 `unittest.mock.patch`로 교체.

## 완료 조건

- [ ] `users` 테이블 자동 생성 확인
- [ ] 회원가입 → 로그인 → 대시보드 흐름 동작
- [ ] 잘못된 비밀번호 입력 시 `st.error()` 표시
- [ ] 중복 이름 가입 시 `st.error()` 표시
- [ ] 로그아웃 후 login 페이지로 복귀
- [ ] 단위 테스트 5개 통과
