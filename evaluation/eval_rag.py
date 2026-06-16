"""RAG 골든 데이터셋 평가 CLI

결정적 평가(정규화·검색·분류)는 API 없이 채점하고, 실행마다 history/runs.jsonl 에 누적 기록한다
생성 충실도(--gen)는 실제 LLM 해설을 생성해 규칙 기반으로 채점한다

실행
    python evaluation/eval_rag.py            # 결정적 평가 + 기록
    python evaluation/eval_rag.py --no-log   # 기록 없이 평가만 (CI·실험용)
    RETRIEVER=pgvector python evaluation/eval_rag.py
    python evaluation/eval_rag.py --gen      # 생성 충실도 포함 (OPENAI_API_KEY 필요)
"""

import argparse
import re
import sys
from pathlib import Path

# 직접 실행(python evaluation/eval_rag.py) 시 저장소 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from evaluation.harness import canonicalize, classify


def _pct(x: float) -> str:
    return f"{100*x:5.1f}%"


def _print_metrics(label: str, m: dict) -> None:
    if not m.get("n"):
        return
    n = m["n"]
    print(f"  [{label}]  n={n}")
    print(f"    정규화 정확도 : {_pct(m['normalization'])}")
    print(f"    검색 정답률   : {_pct(m['retrieval_correct'])}   # 올바른 엔트리 기준")
    print(f"    오적중(FP)    : {m['false_pos']}건   # 엉뚱한 표준명/OOV 적중 (의료 안전 위험)")
    print(f"    분류 정확도   : {_pct(m['classification'])}")
    print(f"    출처 일치     : {_pct(m['source'])}")
    print(f"    전체 통과     : {_pct(m['all_pass'])}")


def report(summary: dict) -> None:
    rows = summary["rows"]
    core, gap = harness.split_core_gap(rows)

    print("=" * 64)
    print("RAG 골든 평가 - 결정적 (정규화 / 검색 / 분류)")
    print("=" * 64)
    _print_metrics("핵심 회귀 케이스", summary["core"])
    if gap:
        print()
        _print_metrics("known_gap (현재 실패 예상)", summary["gap"])

    fails = [r for r in core if not r["all_ok"]]
    if fails:
        print("\n  ✗ 핵심 케이스 실패 상세")
        for r in fails:
            diffs = []
            if not r["norm_ok"]:
                diffs.append(f"canon {r['got']['canon']!r}!={r['exp']['canon']!r}")
            if not r["hit_ok"]:
                diffs.append(f"hit {r['got']['hit']}!={r['exp']['hit']}")
            if not r["flag_ok"]:
                diffs.append(f"flag {r['got']['flag']}!={r['exp']['flag']}")
            if not r["src_ok"]:
                diffs.append("source mismatch")
            print(f"    {r['id']} {r['raw']!r} ({r['intent']}): {'; '.join(diffs)}")

    fps = [r for r in rows if r["false_pos"]]
    if fps:
        print("\n  ⚠ 오적중(false positive) - 엉뚱한 근거를 가져온 케이스 (의료 안전 위험)")
        for r in fps:
            print(f"    {r['id']} {r['raw']!r} -> {r['got']['canon']!r} (기대 {r['exp']['canon']!r})")
    print()


# ---- 생성 충실도 (--gen) ----------------------------------------------------

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# 응급 항목 해설이 긴급성을 전달하는지 - 토큰 부재 시 안전 약화
_URGENCY = ("즉시", "응급", "내원", "바로")


def _num_floats(text: str) -> set[float]:
    """텍스트 내 숫자를 float 집합으로 - 180 과 180.0 을 동일 취급 (포맷 오탐 방지)"""
    return {float(x) for x in _NUM_RE.findall(text or "")}


def eval_generation(cases: list[dict], retriever) -> dict:
    """실제 해설 생성 후 규칙 기반 충실도 채점 - 집계 dict 반환"""
    from gogodoc.infrastructure.config import load_settings
    from gogodoc.infrastructure.llm.openai_client import OpenAILLM
    from gogodoc.domain.models import MatchedItem, Sex, UserProfile
    from gogodoc.domain.reference import reference_dict
    from gogodoc.application import prompts
    from gogodoc.application.ports import LLMTask

    s = load_settings()
    llm = OpenAILLM(s)

    print("=" * 64)
    print("RAG 골든 평가 - 생성 충실도 (--gen)")
    print("=" * 64)

    judged = halluc = forbid = emergency_weak = 0
    concept_hits = concept_total = 0

    for c in cases:
        exp = c["expected"]
        if not exp["retrieval_hit"] or c["value"] is None:
            continue
        got_canon, _, _ = canonicalize(c["raw_name"])
        grounding = retriever.retrieve(got_canon)
        if grounding is None:
            continue
        prof = c["profile"]
        rng = reference_dict.select_range(grounding, prof["sex"], prof["age"])
        flag = classify(got_canon, c["value"], prof["sex"], prof["age"])
        item = MatchedItem(
            canonical_name=got_canon,
            raw_name=c["raw_name"],
            value=c["value"],
            unit=c.get("unit"),
            flag=flag,
            matched=True,
        )
        profile = UserProfile(sex=Sex(prof["sex"]), age=prof["age"])
        user = prompts.build_interpret_user(item, profile, grounding, rng)
        explanation = llm.complete(
            system=prompts.INTERPRET_SYSTEM, user=user, task=LLMTask.INTERPRET
        ).strip()

        # 수치 환각 - float 정규화 비교 (180 == 180.0). 근거·정상범위·측정값·단위 밖 숫자만 환각
        allowed = _num_floats(grounding.get("explanation")) | _num_floats(grounding.get("caution"))
        allowed |= _num_floats(grounding.get("unit"))  # 단위 내 숫자 (예: eGFR "mL/min/1.73m²")
        allowed |= {float(c["value"])}
        if rng:
            allowed |= {float(rng[0]), float(rng[1])}
        extra = _num_floats(explanation) - allowed
        has_halluc = bool(extra)
        # 출처는 InterpretedItem.source 필드로 별도 표기되므로 설명 텍스트에서 검사하지 않음
        gd = c.get("groundedness", {})
        has_forbidden = any(t in explanation for t in gd.get("forbidden_terms", []))
        concepts = gd.get("required_concepts", [])
        # 응급 항목인데 긴급성(즉시·내원 등)을 전달하지 못하면 안전 약화
        is_weak_emergency = flag.value == "emergency" and not any(t in explanation for t in _URGENCY)

        judged += 1
        halluc += has_halluc
        forbid += has_forbidden
        emergency_weak += is_weak_emergency
        concept_hits += sum(1 for t in concepts if t in explanation)
        concept_total += len(concepts)

        mark = "✓" if not (has_halluc or has_forbidden or is_weak_emergency) else "✗"
        detail = []
        if has_halluc:
            detail.append(f"근거밖숫자={sorted(extra)}")
        if has_forbidden:
            detail.append("금지어")
        if is_weak_emergency:
            detail.append("응급긴급성누락")
        print(f"  {mark} {c['id']} {c['raw_name']!r} flag={flag.value}  {' '.join(detail)}")

    print()
    gen = None
    if judged:
        gen = {
            "judged": judged,
            "hallucination_rate": halluc / judged,
            "forbidden": forbid,
            "emergency_weak": emergency_weak,
            "concept_coverage": (concept_hits / concept_total) if concept_total else None,
        }
        print(f"  생성 평가 케이스: {judged}")
        print(f"    수치 환각률     : {_pct(gen['hallucination_rate'])}  ({halluc}/{judged})")
        print(f"    금지어 등장     : {forbid}/{judged}")
        print(f"    응급 긴급성 누락: {emergency_weak}/{judged}   # 안전 - 0 목표")
        if concept_total:
            print(f"    개념 커버리지   : {_pct(gen['concept_coverage'])}  ({concept_hits}/{concept_total})")
    print()
    return gen


def _print_direct(m: dict) -> None:
    print("=" * 64)
    print("RAG 전용 경로 (--direct) - 원본명을 정규화 없이 직접 벡터 검색")
    print("=" * 64)
    if not m.get("n"):
        return
    print(f"  검색 정답률(올바른 엔트리) : {_pct(m['retrieval_correct'])}")
    print(f"  오적중(FP)                 : {m['false_pos']}건")
    if m["oov_rejected"] is not None:
        print(f"  OOV 차단율                 : {_pct(m['oov_rejected'])}  (n={m['oov_n']})   # 미수록을 None 처리")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="RAG 골든 데이터셋 평가")
    ap.add_argument("--gen", action="store_true", help="생성 충실도까지 평가 (OPENAI_API_KEY 필요)")
    ap.add_argument("--direct", action="store_true", help="RAG 전용 경로 평가 - 원본명 직접 검색 (정규화 우회)")
    ap.add_argument("--no-log", action="store_true", help="history 기록 생략 (CI·실험용)")
    args = ap.parse_args()

    cases = harness.load_cases()
    summary = harness.run(cases=cases)
    print(f"\n리트리버: {summary['retriever']}  /  케이스: {summary['n_cases']}건\n")
    report(summary)

    direct = None
    if args.direct:
        retriever, _ = harness.build_retriever()
        direct = harness.direct_metrics(harness.eval_retrieval_direct(cases, retriever))
        _print_direct(direct)

    gen = None
    if args.gen:
        retriever, _ = harness.build_retriever()
        gen = eval_generation(cases, retriever)

    if not args.no_log:
        rec = harness.record_run(summary, gen=gen, direct=direct)
        print(f"기록됨 → {harness.HISTORY_PATH.relative_to(harness._ROOT)}  ({rec['ts']}, {rec['git_sha']})\n")

    core_fail = [r for r in summary["rows"] if not r["known_gap"] and not r["all_ok"]]
    return 1 if core_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
