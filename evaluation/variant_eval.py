"""하이브리드 효과 정량화 - 사전 미등록 변형명 구제율·오구제율 (DB 필요)

dict 동의어 사전이 못 잡는 현실적 변형명(`공복 혈당 수치`·`간 기능 검사` 등)을 하이브리드가
얼마나 정확히 구제하는지 측정한다. 핵심은 단순 구제율이 아니라 정밀도(오구제율) -
틀린 근거(간 기능→갑상선)는 의료 안전상 None(근거없음)보다 위험하다.

- 정확 구제: dict miss 변형을 기대 표준명 카드로 구제
- 오구제: dict miss 변형을 엉뚱한 카드로 구제 (위험 - 0 목표)
- OOV 차단: 잡담·미수록을 None 처리

RETRIEVER=hybrid 권장(폴백 임계값 0.50). 실행: RETRIEVER=hybrid python evaluation/variant_eval.py
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.reference import reference_dict, findings
from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever

GOLDEN = Path(__file__).resolve().parent / "datasets" / "variant_golden.jsonl"

# 표준명 해설 → 항목명 역색인 (검색 엔트리의 주체 식별)
_EXPL_TO_SUBJECT = {e.get("explanation"): name for name, e in reference_dict.REFERENCE.items()}
for _item, _spec in findings.FINDINGS.items():
    for _kws, _flag, _ex, _cau in _spec["findings"]:
        _EXPL_TO_SUBJECT.setdefault(_ex, _item)


def _subject_of(entry: dict | None) -> str | None:
    """검색 엔트리의 주체(표준명/소견 항목) - 해설 매칭, 미상이면 '?'"""
    if entry is None:
        return None
    return _EXPL_TO_SUBJECT.get(entry.get("explanation"), "?")


def evaluate(cases: list[dict], retriever) -> dict:
    dic = DictRetriever()
    rows = []
    for c in cases:
        raw = c["raw_name"]
        canon, _, _ = canonicalize(raw)
        dict_covered = dic.retrieve(canon) is not None
        subject = _subject_of(retriever.retrieve(canon))
        hit = subject is not None

        if c["oov"]:
            cls = "oov_block" if not hit else "oov_leak"
        elif dict_covered:
            cls = "dict_hit"
        elif hit:
            cls = "correct_rescue" if subject in c["expected_canonical"] else "wrong_rescue"
        else:
            cls = "miss"
        rows.append({"id": c["test_id"], "raw": raw, "subject": subject, "cls": cls,
                     "expected": c["expected_canonical"]})

    miss_variants = [r for r in rows if r["cls"] in ("correct_rescue", "wrong_rescue", "miss")]
    correct = sum(r["cls"] == "correct_rescue" for r in rows)
    wrong = sum(r["cls"] == "wrong_rescue" for r in rows)
    oov = [r for r in rows if r["cls"] in ("oov_block", "oov_leak")]
    rescued = correct + wrong
    return {
        "rows": rows,
        "n_variant": len(miss_variants),
        "dict_hit": sum(r["cls"] == "dict_hit" for r in rows),
        "correct_rescue": correct,
        "wrong_rescue": wrong,
        "miss": sum(r["cls"] == "miss" for r in rows),
        "rescue_precision": (correct / rescued) if rescued else None,
        "rescue_rate": (correct / len(miss_variants)) if miss_variants else None,
        "oov_block": sum(r["cls"] == "oov_block" for r in oov),
        "oov_total": len(oov),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="하이브리드 변형 구제 효과 정량화")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    cases = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    retriever, kind = harness.build_retriever()
    m = evaluate(cases, retriever)
    pct = lambda x: f"{x*100:5.1f}%" if x is not None else "  n/a"

    print("=" * 64)
    print(f"하이브리드 변형 구제 효과 - 리트리버: {kind}")
    print("=" * 64)
    print(f"  사전 미등록 변형        : {m['n_variant']}건 (+ 사전적중 {m['dict_hit']} + OOV {m['oov_total']})")
    print(f"  정확 구제               : {m['correct_rescue']}건  ({pct(m['rescue_rate'])} of 변형)")
    print(f"  오구제(틀린 근거)       : {m['wrong_rescue']}건   # 0 목표(안전)")
    print(f"  구제 정밀도             : {pct(m['rescue_precision'])}   # 정확/(정확+오구제)")
    print(f"  미구제(None)            : {m['miss']}건")
    print(f"  OOV 차단                : {m['oov_block']}/{m['oov_total']}")

    wrong = [r for r in m["rows"] if r["cls"] == "wrong_rescue"]
    if wrong:
        print("\n  ⚠ 오구제 상세 (틀린 근거 - 안전 위험)")
        for r in wrong:
            print(f"    {r['id']} {r['raw']!r} -> {r['subject']!r} (기대 {r['expected']})")
    leak = [r for r in m["rows"] if r["cls"] == "oov_leak"]
    if leak:
        print("\n  ⚠ OOV 오적중")
        for r in leak:
            print(f"    {r['id']} {r['raw']!r} -> {r['subject']!r}")
    print()

    if not args.no_log:
        rec = harness.record_eval("variant", {
            "retriever": kind, "n_variant": m["n_variant"],
            "correct_rescue": m["correct_rescue"], "wrong_rescue": m["wrong_rescue"],
            "rescue_precision": m["rescue_precision"], "rescue_rate": m["rescue_rate"],
            "oov_block": m["oov_block"], "oov_total": m["oov_total"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
