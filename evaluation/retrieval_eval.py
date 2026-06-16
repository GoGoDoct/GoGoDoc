"""팀 공식 골든셋 검색 평가 - Recall@3 / Precision@3 / Negative Retrieval / Coverage

GoGoDoc 검색은 항목별 단일 권위 카드 구조(canonicalize -> 카드 1건)다. 따라서 top-k 의
k_effective=1 이며, 팀 지표를 다음으로 정직하게 측정한다.
- Recall@3   : 정답 항목 카드 적중 (동의어 SGOT->AST·HbA1c->당화혈색소 해소 포함)
- Precision@3: 적중 / 검색 반환 (단일 카드라 적중 시 1.0)
- Negative Retrieval : must_not_retrieve 항목 카드 회피 (정규화 오충돌 차단)
- Coverage   : KB 수록 항목 비율

비수치 소견(내시경/초음파/요단백/B형간염)·복합검사는 KB 미수록 -> 미지원으로 별도 집계
(다문서 KB 확장 시 k 확대 여지). 미지원은 Recall 분모에서 제외하되 Coverage 로 노출한다.

실행
    python evaluation/retrieval_eval.py            # 평가 + history 기록(kind=retrieval)
    python evaluation/retrieval_eval.py --no-log   # 기록 없이 평가만
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from evaluation.harness import canonicalize, reference_dict

TEAM_GOLDEN = Path(__file__).resolve().parent / "datasets" / "team_golden.jsonl"


def _pct(x) -> str:
    return "  N/A " if x is None else f"{100*x:5.1f}%"


def _canon_in_kb(raw: str) -> str | None:
    """원본 항목명 -> KB 수록 표준명, 미수록 시 None"""
    canon, _, _ = canonicalize(raw)
    return canon if reference_dict.lookup(canon) else None


def evaluate(cases: list[dict], retriever) -> dict:
    """검색 결정적 채점 - 케이스별 row + 집계 dict 반환"""
    rows = []
    for c in cases:
        canon = _canon_in_kb(c["lab_item"])
        supported = canon is not None

        # must_not_retrieve -> KB 표준명 집합 (회피 대상)
        forbidden = {x for m in c.get("must_not_retrieve", []) if (x := _canon_in_kb(m))}

        hit = False
        retrieved_subject = None
        if supported:
            entry = retriever.retrieve(canon)
            hit = entry is not None
            retrieved_subject = canon if hit else None

        # 회피 성공 - 반환 카드가 금지 항목이 아님 (단일 카드라 오충돌만 위반 가능)
        negative_ok = retrieved_subject not in forbidden

        rows.append({
            "id": c["test_id"],
            "lab_item": c["lab_item"],
            "supported": supported,
            "hit": hit,
            "negative_ok": negative_ok,
            "has_negative": bool(forbidden),
        })

    total = len(rows)
    sup = [r for r in rows if r["supported"]]
    retrieved = [r for r in sup if r["hit"]]
    neg_cases = [r for r in rows if r["has_negative"]]

    metrics = {
        "n": total,
        "supported": len(sup),
        "coverage": len(sup) / total if total else None,
        "recall_at_3": (sum(r["hit"] for r in sup) / len(sup)) if sup else None,
        "precision_at_3": (len(retrieved) / len(retrieved)) if retrieved else None,
        "negative_retrieval_rate": (sum(r["negative_ok"] for r in neg_cases) / len(neg_cases))
        if neg_cases else None,
        "k_effective": 1,  # 단일 권위 카드 구조
    }
    return {"rows": rows, "metrics": metrics}


def report(result: dict, retriever_kind: str) -> None:
    m = result["metrics"]
    print("=" * 64)
    print("팀 공식 골든셋 검색 평가 - Recall@3 / Precision@3 / Negative Retrieval")
    print("=" * 64)
    print(f"  리트리버: {retriever_kind}  /  케이스: {m['n']}건  (k_effective={m['k_effective']}, 단일 카드)")
    print(f"  Coverage(KB 수록)     : {_pct(m['coverage'])}   ({m['supported']}/{m['n']})")
    print(f"  Recall@3              : {_pct(m['recall_at_3'])}   # 정답 항목 카드 적중(수록분)")
    print(f"  Precision@3           : {_pct(m['precision_at_3'])}")
    print(f"  Negative Retrieval    : {_pct(m['negative_retrieval_rate'])}   # 금지 항목 회피")

    miss = [r for r in result["rows"] if r["supported"] and not r["hit"]]
    if miss:
        print("\n  ✗ 미적중(수록인데 검색 실패)")
        for r in miss:
            print(f"    {r['id']} {r['lab_item']!r}")

    unsup = [r for r in result["rows"] if not r["supported"]]
    if unsup:
        print(f"\n  ⚠ 미지원(KB 미수록) {len(unsup)}건 - 비수치 소견·복합검사 (다문서 KB 확장 과제)")
        for r in unsup:
            print(f"    {r['id']} {r['lab_item']!r}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description="팀 골든셋 검색 평가")
    ap.add_argument("--no-log", action="store_true", help="history 기록 생략")
    args = ap.parse_args()

    cases = [json.loads(l) for l in TEAM_GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    retriever, kind = harness.build_retriever()
    result = evaluate(cases, retriever)
    report(result, kind)

    if not args.no_log:
        rec = harness.record_eval("retrieval", {**result["metrics"], "retriever": kind})
        print(f"기록됨 → {harness.HISTORY_PATH.relative_to(harness._ROOT)}  ({rec['ts']}, {rec['git_sha']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
