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

- **domain** - 의료 안전 규칙·판정·정적 지식. 외부 의존 없이 단위 테스트 (임상 밴드·정성 소견·복합검사·동의어·가드레일)
- **application** - 파이프라인 오케스트레이션, 인증(auth_service), 챗봇 서비스, 포트 정의
- **infrastructure** - OpenAI LLM·임베딩, PDF 파싱/렌더, PostgreSQL(인증·분석 기록), 검색(dict·pgvector·hybrid), HIRA 병원 API
- **UI** - Streamlit `app.py` (로그인/회원가입/대시보드/검진 해석 Split 뷰/챗봇)

### 파이프라인

```
단계 0  사용자 입력      성별·나이 (사이드바)
  ↓ ①  파싱·추출        pdfplumber → gpt-4o-mini JSON 구조화                       [application + 포트]
  ↓ ②  정규화·검색      동의어 정규화 → 하이브리드 RAG 검색(dict 우선+벡터 폴백) → 근거 카드   [application + 포트]
  ↓ ③  판정            항목별 임상 밴드(컷오프)·정성 소견·복합검사 → 정상/주의/이상/응급        [순수 도메인]
  ↓ ④  해석·요약        gpt-4o-mini, 근거 고정 해석 + 직장인 요약 + 생활 가이드            [application + 포트]
  ↓ ⑤  안전 가드레일     단정 표현 필터·응급 톤 강제·면책                              [순수 도메인]
  ↓     화면 출력        원본 PDF(좌) / 해석 결과(우) Split View + 결과 기반 챗봇
```

근거 검색·판정·생성의 품질은 별도 평가 하네스(`evaluation/`)가 골든셋으로 상시 채점합니다 ([평가](#평가-evaluation) 참고).

## 기능

F-001~F-005 구현 완료, F-006(병원 추천·HIRA)·F-007(결과 기반 챗봇·RAG)도 구현되어 동작합니다. 상세·담당은 [docs/SPEC.md](docs/SPEC.md).

## 기술 스택

| 레이어 | 선택 |
|--------|------|
| UI | Streamlit |
| PDF 파싱 / 렌더링 | pdfplumber / pdf2image (poppler 필요) |
| 수치 구조화 | Pydantic v2 + gpt-4o-mini |
| 항목 정규화 | Python dict 동의어 + rapidfuzz |
| 판정 | 항목별 임상 밴드 컷오프 + 정성 소견 + 복합검사 분해 (순수 규칙) |
| LLM 해석 | OpenAI gpt-4o-mini |
| 근거 검색 | dict / pgvector / **hybrid**(권장, dict 우선+벡터 폴백), 임베딩 text-embedding-3-small |
| 평가 | 골든셋 + 결정적·LLM-judge 채점 하네스 + Streamlit 대시보드 |
| 저장소 | PostgreSQL (인증·분석 기록, pgvector 확장) |
| 병원 검색 | HIRA 공공데이터 API (F-006) |

## 프로젝트 구조

```
GoGoDoc/
├── app.py                          Streamlit 진입점 (로그인·대시보드·검진 해석)
├── ui.py · styles.py · sample_data.py · pipeline.py   화면 구성·데모 데이터·샘플 파이프라인
├── requirements.txt · .env.example · Dockerfile · docker-compose.yml
├── gogodoc/                        백엔드 패키지 (Hexagonal)
│   ├── domain/                     순수 규칙 (models·policy·services·reference)
│   │   ├── reference/              reference_dict·clinical_bands·findings·synonyms·category_guide
│   │   └── services/               classification·composite·normalization·safety
│   ├── application/                pipeline·ports·prompts·auth_service·chat_*_service·errors
│   ├── infrastructure/             config·llm(openai)·pdf·retrieval(dict·pgvector·hybrid)·hira·db
│   └── composition.py              컴포지션 루트 (어댑터 주입)
├── scripts/index_reference.py      reference_dict·정성 소견 pgvector 색인
├── evaluation/                     골든셋·채점 하네스·대시보드 (RAG 평가)
│   ├── datasets/                   rag·team·variant·assertion·chat 골든셋(jsonl)
│   ├── harness.py · *_eval.py      결정적·LLM-judge 채점, history 누적
│   └── dashboard.py                Streamlit 지표 추이 대시보드
├── docs/SPEC.md · docs/RAG_METRICS.md   기능 명세 · RAG 평가지표·측정 기록
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
# .env 에 OPENAI_API_KEY·DB 접속 정보 입력, RETRIEVER 선택(dict/hybrid - 아래 참고)
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

### 근거 검색 옵션 (retriever)

`.env` 의 `RETRIEVER` 로 선택합니다. 근거 검색은 해석 근거에만 쓰이고, 판정(정상/주의/이상/응급)은 항상 결정적 규칙(임상 밴드)을 따릅니다.

| 값 | 설명 | DB 필요 |
|----|------|---------|
| `dict` | 동의어 사전 정확매칭 (무지연·가장 안전) | 아니오 |
| `pgvector` | 벡터 단독 (정규화 후엔 dict보다 약함, 비권장) | 예 |
| `hybrid` | **권장** - dict 정확매칭 우선 + 사전 미등록 변형은 벡터 폴백 | 예 |

**하이브리드 사용 (권장)** - dict 100% 정확도를 유지하면서 사전이 못 잡는 변형명을 벡터로 의미 해소합니다 (벡터 임계값으로 미수록(OOV)은 차단).

```bash
docker compose up -d db                                          # pgvector Postgres 기동
docker compose run --rm app python -m scripts.index_reference    # 수치+정성 소견 임베딩 색인
# .env 에 RETRIEVER=hybrid 설정 후 앱 실행 (DB 를 안 띄웠으면 RETRIEVER=dict 유지)
```

- 임계값: `RETRIEVER_THRESHOLD`(기본 0.55, 실측 캘리브레이션), 하이브리드 폴백은 `HYBRID_FALLBACK_THRESHOLD`(기본 0.50, 오구제 차단 위해 더 보수적)
- DB·임베딩 실패 시 dict 폴백 (가용성), 먼 매칭은 `None`(근거 없음이 정답)
- 색인 스키마 변경 시 기존 `reference_chunks` 테이블 DROP 후 재색인
- 근거·임계값의 측정 근거는 [docs/RAG_METRICS.md](docs/RAG_METRICS.md)

### 평가 (Evaluation)

`evaluation/` 가 골든셋으로 검색·판정·생성 품질을 상시 채점하고 시계열로 누적합니다.

```bash
python evaluation/eval_rag.py                    # 검색·정규화·판정 (결정적)
python evaluation/clinical_eval.py               # 팀 골든 임상 채점
python evaluation/retrieval_eval.py              # Recall@3·Negative Retrieval·Coverage
python evaluation/gen_eval.py                    # 생성 LLM-judge (Groundedness·환각, OPENAI_API_KEY)
RETRIEVER=hybrid python evaluation/variant_eval.py   # 하이브리드 변형 구제 효과 (DB)
streamlit run evaluation/dashboard.py            # 지표 추이 대시보드
```

결과는 `evaluation/history/runs.jsonl`(gitignore) 에 누적되고 대시보드가 추이를 그립니다.

### 테스트

```bash
pytest
```

도메인·애플리케이션 테스트는 API 키나 네트워크 없이 동작합니다.


## 의료 책임 경계 (가드레일)

- 모든 출력에 "참고용·진단 아님" 면책 강제, 단정 표현 후처리 차단
- 응급 이상치 감지 시 즉시 내원 안내 최우선
- 해설 dict 근거 내에서만 설명(RAG), 출처 없는 추론 차단
- 업로드 PDF는 세션 내 처리 후 즉시 삭제, 서버 미저장

## 데이터 출처

해설 dict 근거 - 질병관리청 국가건강정보포털, 대한당뇨병학회·고혈압학회, 서울아산병원, 건강보험심사평가원 등
