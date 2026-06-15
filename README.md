# GoGoDoc - 종합검진 결과 AI 해석 서비스

종합검진 결과지(PDF)를 업로드하면 검사 수치를 일반인이 이해할 수 있는 언어로 풀어 설명하고, 신경 써야 할 항목과 추적할 항목을 정리해 주는 AI 비서입니다.

> ⚠️ 본 서비스는 의료 진단을 대체하지 않습니다. 모든 해석은 참고용이며 정확한 판단은 반드시 의료진과 상담해야 합니다.

## 아키텍처

실용 Hexagonal (Ports & Adapters) - 의존성은 항상 도메인 안쪽으로 향합니다.

```
interfaces (Streamlit)  →  application (유스케이스·포트)  →  domain (순수 규칙)
                                  ↑
infrastructure (Anthropic·pdfplumber·pdf2image) ── 포트 구현으로 주입
```

- **domain** - 의료 안전 규칙·판정·정적 지식. 외부 의존 없이 단위 테스트
- **application** - 4단계 파이프라인 오케스트레이션, 포트(인터페이스) 정의
- **infrastructure** - 외부 기술 어댑터, 포트 구현
- **interfaces** - Streamlit UI

### 파이프라인 (4단계)

```
단계 0  사용자 입력      성별·나이 (Streamlit 사이드바)
  ↓ ①  파싱·추출        pdfplumber → Claude Haiku JSON 구조화   [application + 포트]
  ↓ ②  정상범위 매칭     동의어 매핑 + rapidfuzz → 정상/주의/이상  [순수 도메인]
  ↓ ③  해석·설명        Claude Sonnet, 해설 dict 근거 인용       [application + 포트]
  ↓ ④  안전·요약        추적·면책·과잉표현 필터·응급 안내         [순수 도메인]
  ↓     화면 출력        원본 PDF(좌) / 해석 결과(우) split 뷰
```

## 기술 스택

| 레이어 | 선택 |
|--------|------|
| UI | Streamlit |
| PDF 파싱 | pdfplumber |
| PDF 렌더링 | pdf2image (poppler 필요) |
| 수치 구조화 | Pydantic v2 + Claude Haiku |
| 항목 매핑 | Python dict + rapidfuzz |
| LLM 해석 | Claude Sonnet |

## 프로젝트 구조

```
GoGoDoc/
├── app.py                          실행 진입점 (streamlit run app.py)
├── requirements.txt
├── .env.example
├── gogodoc/
│   ├── domain/                     순수 규칙 - 외부 의존 0
│   │   ├── models.py               엔티티·값객체 (Pydantic)
│   │   ├── policy.py               면책·가드레일 정책
│   │   ├── reference/              정적 지식 (동의어·해설 dict·패닉 밸류)
│   │   └── services/               정규화·판정·안전 규칙
│   ├── application/
│   │   ├── ports.py                LLMPort·PdfParserPort·RendererPort
│   │   ├── prompts.py              구조화·해석 프롬프트
│   │   └── pipeline.py             4단계 오케스트레이션
│   ├── infrastructure/
│   │   ├── config.py               환경 변수 로딩
│   │   ├── llm/anthropic_client.py LLMPort 구현
│   │   └── pdf/                     pdfplumber·pdf2image 어댑터
│   ├── interfaces/
│   │   └── streamlit_app.py        UI
│   └── composition.py              컴포지션 루트 (어댑터 주입)
└── tests/
    ├── domain/                     순수 규칙 테스트 (API 키 불필요)
    └── application/                가짜 어댑터로 파이프라인 검증
```

## 시작하기

### 사전 요구사항

- Python 3.11 또는 3.12 권장 (일부 의존성 wheel 호환성)
- poppler (PDF 렌더링용)
  - macOS `brew install poppler`
  - Ubuntu `sudo apt-get install poppler-utils`

### 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 에 ANTHROPIC_API_KEY 입력
```

### 실행

```bash
streamlit run app.py
```

### 테스트

```bash
pytest
```

도메인·애플리케이션 테스트는 API 키나 네트워크 없이 동작합니다.

## 데모 범위 (5일 MVP)

- 디지털 PDF·깨끗한 샘플 전제 (스캔본 OCR 제외)
- 핵심 10-15개 항목 (간수치, 혈당/당화혈색소, 콜레스테롤, 신장 등)
- 다년도 결과 비교 범위 외

## 데이터 출처

해설 dict 근거 - 건강보험심사평가원, 질병관리청 국가건강정보포털, 대한임상검사정도관리협회
