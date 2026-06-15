# GoGoDoc - 종합검진 결과 AI 해석 서비스

종합검진 결과지(PDF)를 업로드하면 검사 수치를 일반인이 이해할 수 있는 언어로 풀어 설명하고, 신경 써야 할 항목과 추적할 항목을 정리해 주는 AI 비서입니다.

> ⚠️ 본 서비스는 의료 진단을 대체하지 않습니다. 모든 해석은 참고용이며 정확한 판단은 반드시 의료진과 상담해야 합니다.

기능 명세 요약(F-001~F-007·데이터 모델·역할)은 [docs/SPEC.md](docs/SPEC.md)를 참고하세요.

## 아키텍처

백엔드는 실용 Hexagonal (Ports & Adapters), 화면은 통합 Streamlit 앱(`app.py`)입니다. 의존성은 항상 도메인 안쪽으로 향합니다.

```
Streamlit app.py (로그인 · 대시보드 · 검진 해석)
        ↓  composition 으로 어댑터 주입
application (파이프라인·인증·포트)  →  domain (순수 규칙)
        ↑
infrastructure (OpenAI · pdfplumber · pdf2image · PostgreSQL · pgvector)
```

- **domain** - 의료 안전 규칙·판정·정적 지식. 외부 의존 없이 단위 테스트
- **application** - 파이프라인 오케스트레이션, 인증(auth_service), 포트 정의
- **infrastructure** - OpenAI LLM·임베딩, PDF 파싱/렌더, PostgreSQL(인증·분석 기록), pgvector 검색
- **UI** - Streamlit `app.py` (로그인/회원가입/대시보드/검진 해석 Split 뷰)

### 파이프라인 (선형 5단계)

```
단계 0  사용자 입력      성별·나이 (사이드바)
  ↓ ①  파싱·추출        pdfplumber → gpt-4o-mini JSON 구조화   [application + 포트]
  ↓ ②  정상범위 매칭     동의어 매핑 + rapidfuzz, 성별·나이 → 정상/주의/이상/응급  [순수 도메인]
  ↓ ③  해석·설명        gpt-4o-mini, 해설 dict 근거 인용(RAG)   [application + 포트]
  ↓ ④  안전·요약        추적·면책·과잉표현 필터·응급 안내         [순수 도메인]
  ↓     화면 출력        원본 PDF(좌) / 해석 결과(우) Split View
```

## 기능

F-001~F-005 구현, F-006(병원 추천·예약)·F-007(결과 기반 챗봇)은 계획입니다. 상세는 [docs/SPEC.md](docs/SPEC.md).

## 기술 스택

| 레이어 | 선택 |
|--------|------|
| UI | Streamlit |
| PDF 파싱 / 렌더링 | pdfplumber / pdf2image (poppler 필요) |
| 수치 구조화 | Pydantic v2 + gpt-4o-mini |
| 항목 매핑 | Python dict + rapidfuzz |
| LLM 해석 | OpenAI gpt-4o-mini |
| 근거 검색 | dict 키조회 기본 + pgvector 선택 (임베딩 text-embedding-3-small) |
| 저장소 | PostgreSQL (인증·분석 기록, pgvector 확장) |

## 프로젝트 구조

```
GoGoDoc/
├── app.py                          Streamlit 진입점 (로그인·대시보드·검진 해석)
├── ui.py · styles.py · sample_data.py · pipeline.py   화면 구성·데모 데이터·샘플 파이프라인
├── requirements.txt · .env.example · Dockerfile · docker-compose.yml
├── gogodoc/                        백엔드 패키지 (Hexagonal)
│   ├── domain/                     순수 규칙 (models·policy·reference·services)
│   ├── application/                pipeline·ports·prompts·auth_service·errors
│   ├── infrastructure/             config·llm(openai)·pdf·retrieval(dict·pgvector)·db(postgres)
│   └── composition.py              컴포지션 루트 (어댑터 주입)
├── scripts/index_reference.py      해설 dict pgvector 색인
├── docs/SPEC.md                    기능 명세 요약
├── 문서/                            원본 기획서·기능명세서 (docx)
└── tests/                          domain·application·infrastructure 테스트
```

## 시작하기

### 사전 요구사항

- Python 3.11 또는 3.12 권장 (일부 의존성 wheel 호환성)
- poppler (PDF 렌더링용) - macOS `brew install poppler` / Ubuntu `sudo apt-get install poppler-utils`
- PostgreSQL (로그인·분석 기록 저장) - 직접 띄우거나 아래 Docker 사용

### 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 OPENAI_API_KEY 와 DB 접속 정보 입력
```

### 실행

```bash
streamlit run app.py
```

### Docker 실행 (앱 + pgvector Postgres)

poppler 등 시스템 의존성이 이미지에 포함되어 별도 설치가 필요 없습니다.

```bash
cp .env.example .env
# .env 에 OPENAI_API_KEY 입력

docker compose up --build
```

실행 후 http://localhost:8501 접속

### 벡터 RAG (pgvector, 선택)

기본 근거 검색은 dict 키 조회(`RETRIEVER=dict`)입니다. 의미 검색이 필요하면 pgvector 로 전환합니다 (확장 모달리티 대비 트랙).

```bash
docker compose up -d db                                          # pgvector Postgres 기동
docker compose run --rm app python -m scripts.index_reference    # 해설 dict 임베딩 색인
# .env 에 RETRIEVER=pgvector 설정 후 앱 실행
```

- 근거 검색은 해석 단계에만 적용, 정상범위 판정은 dict 유지 (결정론·의료 안전)
- DB·임베딩 실패 시 dict 폴백

### 테스트

```bash
pytest
```

도메인·애플리케이션 테스트는 API 키나 네트워크 없이 동작합니다.

## 데모 범위 (5일 MVP)

- 디지털 PDF·깨끗한 샘플 전제 (스캔본 OCR 제외)
- 핵심 10-15개 항목 (간수치, 혈당/당화혈색소, 콜레스테롤, 혈압, 신장 등)
- 다년도 결과 비교 범위 외
- F-006(병원 추천)·F-007(챗봇)은 확장 기능

## 의료 책임 경계 (가드레일)

- 모든 출력에 "참고용·진단 아님" 면책 강제, 단정 표현 후처리 차단
- 응급 이상치 감지 시 즉시 내원 안내 최우선
- 해설 dict 근거 내에서만 설명(RAG), 출처 없는 추론 차단
- 업로드 PDF는 세션 내 처리 후 즉시 삭제, 서버 미저장

## 데이터 출처

해설 dict 근거 - 질병관리청 국가건강정보포털, 대한당뇨병학회·고혈압학회, 서울아산병원, 건강보험심사평가원 등
