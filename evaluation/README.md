# RAG 평가 (evaluation/)

GoGoDoc RAG 파이프라인의 end-to-end 성능을 측정·추적하는 평가 자산 일체.
지표 정의·목표치·측정 기록은 [`docs/RAG_METRICS.md`](../docs/RAG_METRICS.md) 참고.

## 구성

```
evaluation/
  datasets/rag_golden.jsonl   RAG 골든 케이스 69건 (한 줄당 한 케이스)
  datasets/team_golden.jsonl  팀 골든셋 임상 채점 100건
  datasets/chat_*.jsonl       F-007 챗봇 분류·답변·통합 정책 골든셋
  harness.py                  코어 - 로드·채점·지표 산출·기록 (CLI·대시보드·테스트 공통)
  eval_rag.py                 CLI - 평가 실행·출력·history 누적 기록
  dashboard.py                Streamlit 추이 대시보드
  history/runs.jsonl          실행마다 1줄 누적되는 시계열 기록 (자동 생성)
```

회귀 게이트는 `tests/test_rag_golden.py` 가 `evaluation.harness` 를 import 해 담당한다.

## 측정 대상

현재 RAG는 자유 질의 top-k 검색이 아니라 다음 3단계 체인이다

```
원본 항목명  --[정규화: synonyms + rapidfuzz]-->  표준명
표준명       --[검색: DictRetriever / PgvectorRetriever]-->  근거 엔트리
항목+근거    --[생성: LLM 해설]-->  쉬운 설명
```

골든 데이터셋은 세 지점을 모두 라벨링한다

| 지표 | 무엇을 보는가 | 채점 방식 |
|------|--------------|-----------|
| **정규화 정확도** | 원본명이 올바른 표준명으로 매핑되는가 | 결정적 - `canonical_name` 비교 |
| **검색 적중 정확도** | 근거 엔트리를 가져와야 할 때 가져오고, 없어야 할 때 안 가져오는가 | 결정적 - `retrieval_hit` 비교 |
| **분류 정확도** | 정상범위/패닉 기준 flag가 맞는가 | 결정적 - `flag` 비교 |
| **생성 충실도(groundedness)** | 설명이 근거 밖 수치·진단·치료를 만들어내지 않는가 | 규칙 기반(수치) + 선택적 LLM-judge |

## 케이스 스키마

```jsonc
{
  "id": "G002",
  "category": "간기능",
  "raw_name": "GPT",              // 결과지에 찍히는 원본 표기 (검색 입력)
  "value": 55,                    // 측정값 (null 이면 인식 불가)
  "unit": "U/L",
  "profile": { "sex": "male", "age": 40 },
  "intent": "synonym_exact",      // 이 케이스가 노리는 시나리오 (아래 표)
  "expected": {
    "canonical_name": "ALT",      // 정규화가 도달해야 할 표준명 (정답)
    "retrieval_hit": true,        // 근거 엔트리를 가져와야 하는가
    "flag": "caution",            // 기대 분류 (normal/caution/abnormal/emergency/check_needed/unknown)
    "grounding_source": "질병관리청 국가건강정보포털 간기능검사"  // 적중 시 기대 출처, 미적중 시 null
  },
  "groundedness": {
    "required_concepts": ["간", "효소"],  // 충실한 설명이라면 닿아야 할 개념어 (recall 힌트)
    "forbidden_terms": ["당뇨"]           // 이 항목 설명에 나오면 환각인 타도메인 용어
  },
  "known_gap": false,             // true 면 "이상적 정답"이며 현재 구현은 실패가 예상되는 케이스
  "notes": "55>40 dev=0.375 -> caution"
}
```

### intent 종류

| intent | 시나리오 |
|--------|---------|
| `canonical_exact` | 표준명 그대로 입력 |
| `canonical_raw_no_synonym` | 동의어 미등록이나 원본==표준명이라 적중 (감마지티피, 중성지방, 수축기/이완기혈압, 헤모글로빈) |
| `synonym_exact` / `synonym_multiword` / `synonym_caseinsensitive` | 동의어 사전 직접 매칭 |
| `fuzzy_typo_recovery` / `fuzzy_parenthetical` / `whitespace_normalization` | rapidfuzz·정규화로 회복 |
| `sex_specific_range` | 동일 수치가 성별에 따라 다른 flag |
| `boundary_*` | dev 0.5 경계 등 분류 경계값 |
| `panic_high` / `panic_low` | 패닉 밸류 -> emergency |
| `panic_only_*` | 패닉 사전에만 있고 REFERENCE 없는 항목(나트륨·칼륨·칼슘) |
| `oov_miss` | 지식베이스 미수록 -> 검색 미적중·unknown 이 정답(환각 금지) |
| `fuzzy_false_positive_guard` | 미수록 항목이 엉뚱한 표준명으로 오매칭되면 안 됨 |
| `check_needed_null_value` | 측정값 null -> check_needed |
| `known_gap_no_synonym` | 과거 영문약어(γ-GTP, TG, SBP, Hb) 동의어 미등록 회귀 설명용. 현재 대표 케이스는 회귀 승격됨 |

## known_gap 케이스

`known_gap: true` 케이스는 **현재 코드가 통과하지 못할 것으로 예상되는** 의도적 미해결 케이스를 뜻한다. 하니스는 이들을 headline 점수에서 분리해 별도 집계한다.

과거 G009 `γ-GTP`, G026 `TG`, G038 `SBP`, G043 `Hb` 는 영문약어 동의어 미등록과 Hb 오적중을 드러내기 위한 known gap이었다. 현재는 동의어 확장으로 회귀 케이스로 승격되었고, 최신 데이터셋 기준 `rag_golden.jsonl`은 69건이다.

현재 대표 known gap은 활성 상태가 아니다. 새 미해결 케이스를 추가할 때만 `known_gap: true` 로 분리하고, 해소 후에는 플래그를 내려 회귀 테스트로 승격한다.

## F-007 챗봇 평가

F-007은 최신 검진 결과 1건을 근거로 수치 설명, 일반 생활습관, 진료과 안내만 제공하는 제한형 챗봇이다. 진단, 처방, 복약, 용량, 응급 증상, 일반 증상 상담, 범위 밖 질문은 답변 생성 전에 라우팅한다.

| 평가기 | 데이터셋 | 목적 |
|--------|----------|------|
| `chat_eval.py` | `chat_scope_golden.jsonl` 89건 | 질문 분류, 위험질문 차단율, 응급 라우팅 |
| `chat_answer_eval.py` | `chat_answer_golden.jsonl` 10건 | 허용 질문의 RAG 답변 근거성, 출처, 환각 방지 |
| `chat_answer_service_eval.py` | `chat_answer_service_golden.jsonl` 24건 | 최신 결과 연결, `question_type`·`route_reason`, answer LLM 호출 정책 |
| `chat_item_match_eval.py` | `chat_item_match_golden.jsonl` 430건 | 띄어쓰기·오타·짧은 alias·혼합 질문 항목명 매칭, false positive 방지 |
| `chat_answer_smoke.py` | 로컬 DB 최신 `analysis_results` | Streamlit 없이 실제 DB row와 답변 서비스 연결 확인 |

## 생성 충실도 채점 규칙

`--gen` 으로 실제 해설을 생성할 때 적용하는 규칙

1. **수치 환각 금지** — 설명에 등장하는 모든 숫자는 `{측정값} ∪ {정상범위 하한/상한} ∪ {근거 텍스트(explanation/caution) 내 숫자}` 집합에 있어야 한다. 그 외 숫자는 환각으로 감점.
2. **출처 일치** — 인용 출처가 `expected.grounding_source` 와 일치해야 한다.
3. **타도메인 용어 금지** — `forbidden_terms` 가 등장하면 감점.
4. **개념 커버리지** — `required_concepts` 중 닿은 비율 (정보성 지표, pass/fail 아님).
5. (선택) **LLM-judge** — 위를 종합해 0~1 충실도 점수. `OPENAI_API_KEY` 필요.

## 실행

```bash
# 결정적 평가 + history 기록 (API 키 불필요)
python evaluation/eval_rag.py

# 기록 없이 평가만 (CI·실험용)
python evaluation/eval_rag.py --no-log

# RAG 전용 경로 - 원본명을 정규화 없이 직접 벡터 검색 (변형명 해소·OOV 차단 측정)
python evaluation/eval_rag.py --direct

# pgvector 리트리버로 검색 평가 (DB + 색인 + 임베딩 필요)
RETRIEVER=pgvector python evaluation/eval_rag.py --direct

# 생성 충실도까지 (OPENAI_API_KEY 필요)
python evaluation/eval_rag.py --gen

# F-007 질문 라우팅·위험질문 차단율
python evaluation/chat_eval.py --no-log

# F-007 챗봇 RAG 답변 근거성
python evaluation/chat_answer_eval.py --no-log

# F-007 최신 결과 연결·LLM 호출 정책
python evaluation/chat_answer_service_eval.py --no-log

# F-007 항목명 유사 입력 매칭
python evaluation/chat_item_match_eval.py --no-log

# F-007 로컬 DB 스모크
python evaluation/chat_answer_smoke.py --user-id 1 --question "BMI가 높으면 어떻게 관리해요?" --mode fake

# 추이 대시보드
streamlit run evaluation/dashboard.py
```

## 유지보수

- 동의어/참조 데이터를 확장하면 해당 `known_gap` 케이스의 플래그를 내려 회귀 테스트로 승격한다.
- 실제 검진 결과지에서 새 표기 변형을 발견하면 케이스를 추가한다 (D1 TODO와 연동).
- 라벨은 `classification.py`의 문서화된 규칙(dev≤0.5 → caution)으로 손계산했다. 규칙이 바뀌면 라벨도 갱신한다.
