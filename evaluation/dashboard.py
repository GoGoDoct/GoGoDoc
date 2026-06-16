"""RAG 평가·테스트 대시보드 (Streamlit)

세 가지를 한 화면에서:
1. 단건 테스트 - 임의 항목명·수치를 넣어 정규화·검색·분류 결과를 즉시 확인
2. 골든 평가 - 골든셋 전체를 돌려 지표·케이스별 통과/실패 확인 + 기록
3. 추이 - history/runs.jsonl 누적 기록 시계열 그래프

실행
    streamlit run evaluation/dashboard.py
"""

import sys
from pathlib import Path

# streamlit run 시 저장소 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st

from evaluation import harness

st.set_page_config(page_title="GoGoDoc RAG 평가", layout="wide")
st.title("GoGoDoc RAG 성능 테스트")
st.caption(
    "지표 정의는 docs/RAG_METRICS.md, 데이터셋은 evaluation/datasets/rag_golden.jsonl 참고. "
    "dict 리트리버는 API 없이 즉시, pgvector 는 DB·색인·임베딩 필요."
)

# ── 사이드바: 리트리버 선택 ────────────────────────────────────────────
with st.sidebar:
    st.header("설정")
    kind = st.selectbox("리트리버", ["dict", "pgvector"], index=0)
    st.caption("pgvector 는 `docker compose up db` + `python -m scripts.index_reference` 후 사용")


@st.cache_resource
def _retriever(kind: str):
    """리트리버 1회 생성 캐시 - 위젯 조작마다 재생성 방지"""
    r, used = harness.build_retriever(kind)
    return r


retriever = _retriever(kind)

tab_probe, tab_eval, tab_trend = st.tabs(["🔍 단건 테스트", "📋 골든 평가", "📈 추이"])

# ════════════════════════════════════════════════════════════════════
# 단건 테스트
# ════════════════════════════════════════════════════════════════════
with tab_probe:
    st.subheader("항목 하나로 RAG 동작 확인")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    raw_name = c1.text_input("항목명 (원본 표기)", value="gpt", help="예: gpt, γ-GTP, Hb, 공복혈당, 백혈구")
    value_str = c2.text_input("측정값", value="55")
    sex = c3.selectbox("성별", ["male", "female"], index=0)
    age = c4.number_input("나이", min_value=1, max_value=120, value=40)

    try:
        value = float(value_str) if value_str.strip() else None
    except ValueError:
        value = None
        st.warning("측정값이 숫자가 아닙니다 - 분류는 확인필요로 처리됩니다.")

    p = harness.probe(raw_name, value, sex, age, retriever)

    m1, m2, m3 = st.columns(3)
    m1.metric("정규화 표준명", p["canonical"], help=f"매칭여부 {p['matched']} · 점수 {p['score']:.0f}")
    m2.metric("분류 flag", p["flag"])
    m3.metric("정상범위", str(p["reference_range"]) if p["reference_range"] else "-")

    st.markdown("**검색 결과 (근거)**")
    cp, cd = st.columns(2)
    with cp:
        st.markdown(f"파이프라인 경로 · `retrieve({p['canonical']!r})`")
        if p["pipeline"]:
            st.success(f"적중 · 출처: {p['pipeline'].get('source')}")
            st.write(p["pipeline"].get("explanation"))
        else:
            st.error("미적중 (None) → unknown/상담 안내")
    with cd:
        st.markdown(f"RAG 전용 경로 · `retrieve({p['raw_name']!r})` (정규화 우회)")
        if p["direct"]:
            st.success(f"적중 · 출처: {p['direct'].get('source')}")
            st.write(p["direct"].get("explanation"))
        else:
            st.error("미적중 (None) → OOV 또는 임계값 초과")

    if p["pipeline"] and value is not None:
        with st.expander("LLM 해설 생성 (OPENAI_API_KEY 필요 · API 비용 발생)"):
            if st.button("해설 생성"):
                with st.spinner("생성 중..."):
                    try:
                        from gogodoc.infrastructure.config import load_settings
                        from gogodoc.infrastructure.llm.openai_client import OpenAILLM
                        from gogodoc.domain.models import MatchedItem, Sex, UserProfile, Flag
                        from gogodoc.application import prompts
                        from gogodoc.application.ports import LLMTask

                        llm = OpenAILLM(load_settings())
                        item = MatchedItem(
                            canonical_name=p["canonical"], raw_name=raw_name, value=value,
                            unit=p["pipeline"].get("unit"), flag=Flag(p["flag"]), matched=True,
                        )
                        prof = UserProfile(sex=Sex(sex), age=int(age))
                        user = prompts.build_interpret_user(item, prof, p["pipeline"], p["reference_range"])
                        out = llm.complete(system=prompts.INTERPRET_SYSTEM, user=user, task=LLMTask.INTERPRET)
                        st.info(out.strip())
                    except Exception as e:
                        st.error(f"생성 실패: {e}")

    st.caption(
        "💡 변형명 테스트: `gpt`(→ALT 적중), `γ-GTP`/`Hb`(현재 known_gap), "
        "`백혈구`/`TSH`(OOV - 미적중이 정답)"
    )

# ════════════════════════════════════════════════════════════════════
# 골든 평가
# ════════════════════════════════════════════════════════════════════
with tab_eval:
    st.subheader("골든셋 전체 평가")
    run_col, log_col = st.columns([1, 3])
    do_run = run_col.button("평가 실행", type="primary")
    direct_on = log_col.checkbox("RAG 전용 경로(--direct)도 측정", value=(kind == "pgvector"))

    if do_run:
        cases = harness.load_cases()
        with st.spinner("평가 실행 중..."):
            summary = harness.run(kind=kind, cases=cases)
            direct = (
                harness.direct_metrics(harness.eval_retrieval_direct(cases, retriever))
                if direct_on else None
            )
            rec = harness.record_run(summary, direct=direct)
        st.session_state["last_eval"] = {"summary": summary, "direct": direct, "rec": rec}

    last = st.session_state.get("last_eval")
    if not last:
        st.info("**평가 실행**을 눌러 골든셋 전체를 채점하세요. 결과는 기록(history)에도 누적됩니다.")
    else:
        summary, direct, rec = last["summary"], last["direct"], last["rec"]
        core = summary["core"]
        st.success(f"기록됨 — {rec['ts']} · `{rec['git_sha']}` · {summary['retriever']}")

        k = st.columns(5)
        k[0].metric("검색 정답률", f"{core['retrieval_correct']*100:.1f}%")
        k[1].metric("정규화", f"{core['normalization']*100:.1f}%")
        k[2].metric("분류", f"{core['classification']*100:.1f}%")
        k[3].metric("전체 통과", f"{core['all_pass']*100:.1f}%")
        k[4].metric("오적중", f"{core['false_pos']}건", help="0 목표")
        if direct:
            st.caption(
                f"RAG 전용: 검색 정답률 {direct['retrieval_correct']*100:.1f}% · "
                f"OOV 차단 {(direct['oov_rejected'] or 0)*100:.0f}% · 오적중 {direct['false_pos']}건"
            )

        rows = summary["rows"]
        view = st.radio("보기", ["실패·오적중만", "전체"], horizontal=True)
        table = []
        for r in rows:
            ok = r["all_ok"]
            if view == "실패·오적중만" and ok and not r["false_pos"]:
                continue
            table.append({
                "id": r["id"], "원본명": r["raw"], "intent": r["intent"],
                "표준명(검출/기대)": f"{r['got']['canon']} / {r['exp']['canon']}",
                "flag(검출/기대)": f"{r['got']['flag']} / {r['exp']['flag']}",
                "통과": "✅" if ok else "❌",
                "오적중": "⚠️" if r["false_pos"] else "",
                "known_gap": "·" if r["known_gap"] else "",
            })
        if table:
            st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        else:
            st.success("표시할 실패/오적중 케이스가 없습니다 (핵심 전부 통과).")

# ════════════════════════════════════════════════════════════════════
# 추이
# ════════════════════════════════════════════════════════════════════
def _chart(records, ts_key, cols_map, pct=True):
    """records 리스트에서 (ts + 지정 컬럼) DataFrame 생성 - 시간순"""
    rows = [{"ts": r.get(ts_key), **{label: get(r) for label, get in cols_map.items()}} for r in records]
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    if pct:
        for c in cols_map:
            df[c] = df[c].apply(lambda v: v * 100 if isinstance(v, (int, float)) else v)
    return df


with tab_trend:
    records = harness.load_history()
    golden = [r for r in records if r.get("kind", "golden") == "golden"]
    scope = [r for r in records if r.get("kind") == "chat_scope"]
    answer = [r for r in records if r.get("kind") == "chat_answer"]

    if not records:
        st.info("아직 기록이 없습니다. **골든 평가** 탭 또는 `chat_eval`/`chat_answer_eval`을 실행하세요.")

    # ── 검색·분류 (골든) ──────────────────────────────
    if golden:
        st.subheader("F-004 검색·분류 추이 (골든 핵심 케이스)")
        g = _chart(golden, "ts", {
            "정규화": lambda r: (r.get("core") or {}).get("normalization"),
            "검색정답률": lambda r: (r.get("core") or {}).get("retrieval_correct"),
            "분류정확도": lambda r: (r.get("core") or {}).get("classification"),
            "전체통과": lambda r: (r.get("core") or {}).get("all_pass"),
        })
        st.line_chart(g.set_index("ts"), y_label="정확도 (%)")
        fp = _chart(golden, "ts", {"오적중_핵심": lambda r: (r.get("core") or {}).get("false_pos")}, pct=False)
        st.line_chart(fp.set_index("ts"), y_label="오적중 건수")

    # ── 챗봇 스코프 분류 (F-007) ───────────────────────
    if scope:
        st.subheader("F-007 챗봇 스코프 분류 추이")
        s = _chart(scope, "ts", {
            "분류정확도": lambda r: r["metrics"].get("accuracy"),
            "위험질문차단율": lambda r: r["metrics"].get("block_recall"),
            "과차단율": lambda r: r["metrics"].get("over_block"),
        })
        st.line_chart(s.set_index("ts"), y_label="비율 (%)")
        st.caption("위험질문 차단율 100% 유지가 안전 핵심 (의료법 리스크).")

    # ── 챗봇 RAG 답변 (F-007) ─────────────────────────
    if answer:
        st.subheader("F-007 챗봇 RAG 답변 충실도 추이")
        a = _chart(answer, "ts", {
            "근거적중률": lambda r: r["metrics"].get("ground_accuracy"),
            "출처인용률": lambda r: r["metrics"].get("cite_rate"),
            "수치환각률": lambda r: r["metrics"].get("halluc_rate"),
        })
        st.line_chart(a.set_index("ts"), y_label="비율 (%)")

    if records:
        st.subheader("전체 실행 기록 (kind별)")
        st.dataframe(
            pd.DataFrame([{
                "ts": r.get("ts"), "kind": r.get("kind", "golden"), "sha": r.get("git_sha"),
                "요약": (f"검색 {(r.get('core') or {}).get('retrieval_correct')}·오적중 {(r.get('core') or {}).get('false_pos')}"
                         if r.get("kind", "golden") == "golden"
                         else str(r.get("metrics"))),
            } for r in records]),
            use_container_width=True, hide_index=True,
        )
