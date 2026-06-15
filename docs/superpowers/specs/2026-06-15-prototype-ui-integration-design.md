# 프로토타입 UI 통합 설계

## 개요

`app.py`(프로토타입 UI)에서 실제 DB 인증·실제 파이프라인을 호출하도록 통합한다.
`styles.py`, `ui.py`, `sample_data.py`는 그대로 유지하며 대시보드는 샘플 데이터를 사용한다.

## 결정 사항

| 항목 | 결정 |
|------|------|
| 진입점 | `app.py` 유지 |
| 대시보드 데이터 | 샘플 데이터 유지 (추후 실제 데이터로 교체 가능) |
| 결과 렌더링 | 어댑터 방식 — FinalReport → ui.py 형식 변환 |
| gogodoc/interfaces/streamlit_app.py | 보관 (삭제 안 함) |

## 변경 범위

**수정:** `app.py`, `ui.py` (막대 그래프 None 처리 1줄)
**변경 없음:** `styles.py`, `ui.py`(막대 외), `sample_data.py`, `pipeline.py`, `gogodoc/` 전체

## 어댑터 — FinalReport → ui.py 형식

`app.py` 내부 `_report_to_items(report: FinalReport) -> list[dict]`

- `flag` → 상태 문자열: NORMAL→정상, CAUTION→주의, ABNORMAL→이상, EMERGENCY→응급, 나머지→주의
- `cat`: `reference_dict`에서 조회, 없으면 "기타"
- `low`, `high`: None (막대 그래프 생략)
- `value` None이면 `value_text = "-"`, `value = 0`

`ui.py`의 `result_card_html()`: `low`/`high` 모두 None이면 `bar_html()` 호출 생략.

## session_state 저장 형식

```python
session_state.result = {
    "items": [...],                          # 변환된 항목 리스트
    "counts": {"정상": N, "주의": N, "이상": N},
    "emergency": "문자열" or None,
    "tracked": ["항목명", ...]
}
```

## app.py 변경 상세

### 추가 임포트
```python
from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.db.init_db import init_db
from gogodoc.application.auth_service import login, register, AuthError, DuplicateNameError
from gogodoc.composition import build_pipeline, build_renderer
from gogodoc.infrastructure.pdf import (
    PdfValidationError, validate_uploaded_pdf_metadata, validate_digital_pdf,
)
from gogodoc.domain.models import UserProfile, Sex, Flag
from gogodoc.domain.reference import reference_dict
```

### main() 변경
- `settings = load_settings()` + `pool = init_db(settings)` 추가
- 실패 시 `st.error()` + `st.stop()`

### 인증 (render_login / render_signup)
- 로그인: `login(pool, name, pw)` → 성공 시 session_state + `go("dashboard")`
- 회원가입: `register(pool, name, pw, sex, age)` → 성공 시 자동 로그인 + `go("dashboard")`
- 로그아웃: `st.session_state.clear()` + `go("login")`
- 에러: AuthError → st.error, DuplicateNameError → st.error

### _run_and_store(file) 교체
- file=None → 기존 샘플 파이프라인 유지
- file 있음 → PDF 검증 → 임시 파일 → 실제 파이프라인 → 어댑터 변환 → session_state.result 저장

### _render_result() 변경
- `run_pipeline()` 호출 제거
- `session_state.result`에서 데이터 읽어 렌더링

## 에러 처리

| 상황 | 처리 |
|------|------|
| DB 연결 실패 | st.error + st.stop |
| PDF 검증 실패 | st.error, 업로드 화면 유지 |
| 파이프라인 실패 | st.error, 업로드 화면 복귀 |
| 로그인 실패 | st.error |
| 이름 중복 | st.error |
| 샘플 체험 | 더미 파이프라인 유지 |
