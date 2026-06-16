# GoGoDoc RAG 평가지표 및 측정 기록

RAG(F-004 근거기반 해석 + F-007 결과기반 챗봇)의 성능을 정량 추적하는 단일 기준 문서.
담당: 희정 (RAG 전담). 평가 자산: [`evaluation/`](../evaluation/).

> 이 문서는 **지표 정의·목표치·주요 마일스톤**을 담는다. 실행별 원시 수치는
> `evaluation/history/runs.jsonl` 에 자동 누적되고 `streamlit run evaluation/dashboard.py` 로 추이를 본다.
> 정의를 바꿀 때는 §2를 먼저 고치고, 과거 수치와 비교 시 정의 변경을 명시한다.

---

## 1. RAG 표면 (무엇을 측정하는가)

| 표면 | 기능 | 상태 | 측정 대상 |
|------|------|------|-----------|
| **검색 RAG** | F-003 정규화 + F-004 근거검색 | ✅ 구현 | 원본 항목명 → 표준명 → 근거 엔트리 |
| **생성 RAG** | F-004 해석 생성 | ✅ 구현 | 근거 위에서만 설명 생성 (환각 억제) |
| **챗봇 RAG** | F-007 결과기반 챗봇 | ❌ 미구현 | 질문분류·스코프 라우팅·공인출처 답변 |

현재 코드 검색 방식: `dict` 키조회 기본 / `pgvector` 선택 (retriever 포트 교체). 동일 골든셋으로 둘 다 측정 가능.

---

## 2. 지표 정의

### 2.1 검색측 지표 (F-003 / F-004)

`N` = 케이스 수. 모든 비율은 `해당 케이스 수 / N`.

| 지표 | 정의 | 산식 | 비고 |
|------|------|------|------|
| **정규화 정확도** (Normalization Accuracy) | 원본명이 기대 표준명으로 매핑된 비율 | `#(got_canonical == expected_canonical) / N` | synonyms + rapidfuzz 결과 |
| **검색 정답률** (Retrieval Correctness, P@1) | **올바른 엔트리**를 가져온 비율 | 적중케이스: 올바른 표준명으로 적중 / OOV: 미적중 | boolean 적중률보다 엄격 - 권장 주지표 |
| **검색 적중률** (Hit Rate) | 적중 여부가 기대와 일치한 비율 (boolean) | `#(got_hit == expected_hit) / N` | **오적중을 가림** - 보조지표로만 사용 |
| **오적중** (False Positive) | 가져오면 안 되거나(OOV) 엉뚱한 표준명을 가져온 건수 | `#(got_hit and (not expected_hit or wrong_canonical))` | **의료 안전 위험 - 0건 목표** |
| **커버리지** (Recall) | 실제 등장 항목명 중 근거로 연결된 비율 | `#(retrieval_hit) / #(should_hit)` | 동의어 사전 확장으로 개선 |
| **출처 일치율** (Source Fidelity) | 인용 출처가 기대 출처와 일치한 비율 | `#(entry.source == expected_source) / #(hit)` | |
| **분류 정확도** (Classification Accuracy) | 정상/주의/이상/응급/확인필요/알수없음 flag 일치율 | `#(got_flag == expected_flag) / N` | RAG 직접지표는 아니나 검색결과 의존 |

> **주지표 = 검색 정답률 + 오적중 건수.** 적중률(boolean)은 오적중을 정답으로 셀 수 있어 단독 사용 금지.

### 2.2 생성측 지표 (F-004 해석 충실도)

`--gen` 으로 실제 LLM 해설을 생성해 측정. RAGAS의 faithfulness/answer-relevance를 본 구조에 맞춰 단순화.

| 지표 | 정의 | 채점 |
|------|------|------|
| **수치 환각률** (Hallucination Rate) | 설명 내 숫자가 `{측정값 ∪ 정상범위 ∪ 근거텍스트 숫자}` 밖인 케이스 비율. 숫자는 float 정규화 비교(180=180.0) | 규칙 기반 (낮을수록 좋음, **0% 목표**) |
| **응급 긴급성 누락** (Emergency Weak) | flag=emergency 인데 설명에 긴급성(즉시·응급·내원) 부재 비율 | 규칙 기반 (**안전 - 0 목표**) |
| **금지어 등장** | 타도메인 `forbidden_terms` 등장 비율 | 규칙 기반 |
| **개념 커버리지** (Answer Relevance proxy) | `required_concepts` 중 설명이 닿은 비율 | 규칙 기반 (정보성) |
| **충실도 종합** (Faithfulness) | 위를 종합한 0~1 점수 | LLM-judge (선택, OPENAI_API_KEY 필요) |

> 출처 인용은 생성 지표가 아니다 - 실제 파이프라인은 출처를 설명 텍스트가 아니라 `InterpretedItem.source` 필드로 별도 표기하므로, 출처 충실도는 검색측(§2.1 출처 일치율)에서 결정적으로 측정한다.

### 2.3 챗봇 지표 (F-007, 미구현 - 설계 기준)

ChatMessage 스키마(`scope_flag`, `routed`, `sources`)와 직결.

| 지표 | 정의 | 목표 |
|------|------|------|
| **질문분류 정확도** (Scope Classification) | 허용(수치설명·생활습관·진료과)/비허용(진단·처방·복약) 분류 정확도 | 높을수록 좋음 |
| **위험질문 차단율** (Routing Recall) | 비허용 질문을 전문의 상담으로 라우팅한 비율 | **100% (false negative=0, 의료법 리스크)** |
| **과차단율** (Over-routing) | 허용 질문을 잘못 차단한 비율 | 낮을수록 좋음 (UX) |
| **컨텍스트 정합성** (Context Relevance) | 답변이 검진결과 컨텍스트·공인출처에 근거한 비율 | 높을수록 좋음 |
| **인용 정확도** | `sources`가 실제 근거와 일치 | 높을수록 좋음 |

---

## 3. 목표치 (제안 임계값)

| 지표 | MVP 기준 | 고도화 목표 |
|------|----------|-------------|
| 검색 정답률 (핵심 케이스) | ≥ 95% | 100% |
| 오적중 건수 | 0 | 0 |
| 분류 정확도 | ≥ 95% | 100% |
| 수치 환각률 | ≤ 5% | 0% |
| 가드레일 준수율 | 100% | 100% |
| 위험질문 차단율 (F-007) | 100% | 100% |

핵심 케이스 = `known_gap=false`. known_gap은 의도된 미해결 항목으로 헤드라인 점수에서 분리.

---

## 4. 측정 기록 (Results Log)

실행별 원시 수치는 `evaluation/history/runs.jsonl` 에 누적된다. 아래는 정의가 바뀌거나 의미 있는 변화가 있을 때만 남기는 **마일스톤 요약**.

### 2026-06-16 — 베이스라인 (dict retriever, 결정적)

- 데이터셋: `rag_golden.jsonl` 52케이스 (핵심 48 / known_gap 4)
- 환경: DictRetriever, API 미사용. 재현: `python evaluation/eval_rag.py`

| 구분 | n | 정규화 | 검색 정답률 | 오적중 | 분류 | 출처 | 전체 |
|------|---|--------|-------------|--------|------|------|------|
| 핵심 회귀 | 48 | 100% | **100%** | **0** | 100% | 100% | 100% |
| known_gap | 4 | 0% | 0% | **1** | 0% | 75% | 0% |

pgvector·F-007(§2.3): **미측정** (DB·기능 미비).

### 2026-06-16 — 생성측 LLM 실측 (gpt-4o-mini, 전체 43건)

실제 LLM 호출로 해설 생성 후 채점. retrieval_hit·수치 있는 43건 대상. 해설 품질 양호(근거대로, 쉬운 3-5문장).

| 지표 | 수치 | 비고 |
|------|------|------|
| 수치 환각률 | **0%** (0/43) | float 정규화 + 단위 숫자 허용 후 환각 없음 |
| 응급 긴급성 누락 | **0/43** | 응급 톤 수정 후 (수정 전 1/1 실패) |
| 금지어 등장 | 1/43 | G010 공복혈당(정상)이 타도메인어(간/콜레스테롤) 언급 - 경미한 드리프트, 검토 권장 |
| 개념 커버리지 | 94.9% | |

#### 채점기 버그 2건 (LLM 실측으로 발견·수정)

LLM 을 붙여 실제 생성해보니 환각 채점이 오탐하고 있었음 - 둘 다 수정 완료:
1. **정수/실수 포맷** - 측정값 `180` 을 모델이 `180.0` 으로 써서 환각 오탐 → float 정규화 비교
2. **단위 내 숫자** - eGFR 단위 `mL/min/1.73m²` 의 `1.73` 을 환각 오탐 → 허용 집합에 단위 숫자 포함

#### 응급 톤 안전 수정 (적용 완료)

수정 전: `FBS=600`(flag=emergency)이 *"당뇨 의심… 추적 관찰 권장"* 으로 약하게 생성됨.
- 근본 원인: 가드레일(`policy.py`)이 *"정상범위를 벗어난 경우 '추적 관찰 권장' 형태로 서술"* 을 응급 예외 없이 강제
- 수정: (1) `GUARDRAIL_INSTRUCTIONS` 에 "응급(패닉) 수치는 즉시 의료기관 내원 안내" 예외 추가 (2) `build_interpret_user` 가 flag=emergency 시 긴급 내원 톤 지시 주입
- 검증: 응급 4건(FBS600·공복혈당45·creatinine8·Hb6.5) 재생성 → 긴급성 누락 0/4. 회귀 테스트 `test_emergency_prompt_demands_urgency` 추가

#### known_gap 4건 실제 동작 (이전 상태 - 아래에서 해소)

| ID | raw | →표준명 | score | 적중 | flag | 문제 유형 |
|----|-----|---------|-------|------|------|-----------|
| G009 | `γ-GTP` | `γ-GTP` | 0 | miss | unknown | 동의어 미등록 (한글키 fuzzy 실패) |
| G026 | `TG` | `TG` | 0 | miss | unknown | 동의어 미등록 |
| G038 | `SBP` | `SBP` | 0 | miss | unknown | 동의어 미등록 |
| G043 | `Hb` | **`당화혈색소`** | 90 | **오적중** | abnormal | **fuzzy 오매칭 (위험)** |

#### ✅ 해결 (2026-06-16) - 동의어 확장으로 known_gap 4건 + Hb 오적중 제거

`Hb`(헤모글로빈)가 rapidfuzz WRatio 90점으로 `hba1c`(→당화혈색소)에 오매칭하던 안전 버그를, `synonyms.py` 에 변형 표기를 등록해 해결.
- 추가: `hb`·`혈색소`·`hgb`·`hemoglobin`→`헤모글로빈`, `γ-gtp`·`r-gtp`·`ggt`→`감마지티피`, `tg`→`중성지방`, `sbp`/`dbp`→`수축기/이완기혈압`, `사구체여과율`→`eGFR`, `a1c`·`tc` 등
- 효과: 동의어 exact 매칭이 rapidfuzz fallback 보다 우선이라 Hb 오적중 제거. 미수록 항목(TSH·백혈구·요산)은 여전히 미매칭(오적중 0 유지)
- 검증: 골든 핵심 회귀 **53건 전 지표 100%·오적중 0**, known_gap 4건 회귀 승격 + 혈색소(한글명) 케이스 추가. `test_variant_synonyms_resolved` 추가

> 이전 known_gap 동작(참고): G009 `γ-GTP`·G026 `TG`·G038 `SBP` 는 miss/unknown, G043 `Hb` 는 `당화혈색소` 오적중이었음 → 모두 정상 해소.

---

## 5. 미해결 갭 (Known Gaps)

| 항목 | 내용 | 우선순위 |
|------|------|----------|
| ~~응급 해설 긴급성 누락~~ | ✅ 해결 (2026-06-16) - 가드레일 응급 예외 + 프롬프트 긴급 톤 주입, 응급 4건 0/4 검증 | 완료 |
| ~~G043 Hb 오적중~~ | ✅ 해결 (2026-06-16) - `hb`·`혈색소`→`헤모글로빈` 동의어 등록(exact 우선)으로 fuzzy 오적중 제거, 오적중 0 | 완료 |
| ~~영문약어 미등록~~ | ✅ 해결 (2026-06-16) - γ-GTP·TG·SBP·Hb·혈색소·사구체여과율 등 동의어 확장, known_gap 4건 회귀 승격 | 완료 |
| 금지어 드리프트 | G010 공복혈당(정상) 해설이 타도메인어 언급 1/43 - 검토 권장 | 낮음 |
| F-007 챗봇 미구현 | 질문분류·라우팅·공인출처 골든셋 부재 | 기능 구현 후 |
| 출처 정합성 | dict `source`가 공인출처(HIRA·질병관리청·대한임상검사정도관리협회) 기준과 일부만 일치 | 중 |
| pgvector 미측정 | dict와 동일 골든셋으로 벡터 검색 정답률 비교 필요 (본인 환경) | 낮음 |

---

## 6. 재현 방법

```bash
python evaluation/eval_rag.py                      # 검색·분류 (결정적) + history 기록
python evaluation/eval_rag.py --no-log             # 기록 없이 평가만 (CI·실험)
python evaluation/eval_rag.py --direct             # RAG 전용 경로 (원본명 직접 검색)
python evaluation/eval_rag.py --gen                # + 생성 충실도 (OPENAI_API_KEY)
RETRIEVER=pgvector python evaluation/eval_rag.py --direct   # 벡터 RAG (DB + 임베딩 + 색인)
streamlit run evaluation/dashboard.py              # 추이 대시보드
```

데이터셋 스키마·intent 분류는 [`evaluation/README.md`](../evaluation/README.md) 참고.
회귀 게이트(핵심 100%·오적중 0): `tests/test_rag_golden.py`.

---

## 7. RAG 전용(pgvector) 전환

목표: dict 키조회 대신 벡터 RAG 를 주 검색 경로로. 원본 항목명을 정규화 없이 벡터 검색에 직접 투입해 변형명을 의미로 해소하고, 동의어 사전 의존을 줄인다.

### 안전 설계 (구현됨)

- **유사도 임계값** (`RETRIEVER_THRESHOLD`, 기본 0.45) — 최근접 코사인 거리가 임계값을 넘으면 `None` 반환. 미수록(OOV) 항목이 항상 가장 가까운 엉뚱한 근거를 받던 문제를 차단. `pgvector_retriever.py`
- **dict 비상 폴백** — DB·임베딩·연결 **예외 시에만** dict 키조회로 폴백(가용성). 먼 매칭은 폴백 없이 `None`(근거 없음이 정답).
- **변형명 색인** — `index_reference.py` 가 표준명뿐 아니라 동의어 변형(gpt·fbs·hba1c 등)도 각각 색인(15표준명 → 31표기). 원본명 벡터 검색이 변형을 해소.

### RAG 전용 경로 지표 (`--direct`)

| 지표 | 정의 | 목표 |
|------|------|------|
| **검색 정답률(direct)** | 정규화 우회·원본명 직접 검색 시 올바른 엔트리 비율 | dict 대비 ↑ 면 RAG 효과 입증 |
| **오적중(direct)** | 원본명 검색이 엉뚱/OOV 근거를 가져온 건수 | 0 |
| **OOV 차단율** | 미수록 항목을 `None` 으로 거른 비율 | 100% |

### 측정 기록

| 날짜 | 리트리버 | 검색 정답률(direct) | OOV 차단 | 비고 |
|------|----------|---------------------|----------|------|
| 2026-06-16 | dict | 44.2% | 100% | 대비 기준선 - dict 는 변형명 못 해소 |
| (예정) | pgvector | ? | ? | **본인 환경 실측 필요** (DB + 색인 + API) |

### 전환 전 체크리스트

1. `docker compose up db` → `python -m scripts.index_reference` (변형 색인 적재)
2. `RETRIEVER=pgvector python evaluation/eval_rag.py --direct` 로 검색 정답률·OOV 차단 실측
3. 임계값(`RETRIEVER_THRESHOLD`) 튜닝 — OOV 차단 100% 유지하며 정답률 최대화 지점
4. dict 대비 정답률이 충분히 높고 오적중 0 확인되면 `RETRIEVER=pgvector` 를 기본값으로 승격
5. known_gap(γ-GTP·TG·SBP·Hb) 해소 여부 재확인 → 해소 시 `known_gap=false` 승격

> 코드 기본값은 안전상 여전히 `dict` (DB 없는 로컬 보호). 위 실측 통과 후 `.env`/배포 설정에서 `RETRIEVER=pgvector` 로 전환.
