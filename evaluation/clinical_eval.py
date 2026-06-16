"""팀 공식 골든셋(team_golden.jsonl) 대비 현재 시스템 임상 채점 (결정적)

팀 지표 중 분류로 측정 가능한 것을 현재값으로 산출 - "현재값 vs 목표값"(설계서 요구):
- Clinical Correctness: classify flag ↔ risk_level 일치율 (목표 85/95%)
- Emergency Detection Recall: emergency=Y를 응급으로 안내한 비율 (목표 100%, 누락 가장 치명)
- Over-warning Rate: risk_level=정상인데 경고한 비율 (목표 ≤10%/5%)
- Coverage: 현재 시스템이 채점 가능한 케이스 비율 (미지원 항목 가시화)

생성·검색 지표(Groundedness/Recall@3/Forbidden Keyword 등)는 별도 단계.
실행: python evaluation/clinical_eval.py [--no-log]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.services.classification import classify, classify_finding
from gogodoc.domain.services import composite
from gogodoc.domain.reference import reference_dict, findings

GOLDEN = Path(__file__).resolve().parent / "datasets" / "team_golden.jsonl"

# risk_level ↔ Flag
RISK_OF_FLAG = {"normal": "정상", "caution": "주의", "abnormal": "이상", "emergency": "응급"}
# 기본 프로필 (팀 골든은 성별·나이 미지정) - 성별 의존 항목은 남성 기준
_SEX, _AGE = "male", 45
_RISK_RANK = {"정상": 0, "주의": 1, "이상": 2, "응급": 3}


def _num(v: str):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _classify_single(lab_item: str, value: str) -> tuple[str, str | None, bool]:
    """단일 골든 케이스를 현재 분류기로 채점한다."""
    canon, _, _ = canonicalize(lab_item)
    val = _num(value)
    supported = canon in reference_dict.REFERENCE and val is not None
    if not supported:
        return canon, None, False
    flag = classify(canon, val, _SEX, _AGE).value
    return canon, RISK_OF_FLAG.get(flag, flag), True


def _classify_composite(value: str) -> tuple[str | None, bool]:
    """복합검사 값을 도메인 분해기로 구성 항목별 분해 후 최댓값 위험도 반환"""
    predictions: list[str] = []
    for raw_name, val in composite.parse_composite(value):
        _, pred, supported = _classify_single(raw_name, str(val))
        if supported and pred is not None:
            predictions.append(pred)
    if not predictions:
        return None, False
    return max(predictions, key=lambda pred: _RISK_RANK.get(pred, -1)), True


def _classify_qualitative(lab_item: str, value: str) -> tuple[str | None, bool]:
    """비수치 소견을 도메인 정성 소견 KB로 채점 - risk_level 문자열 반환"""
    flag = classify_finding(lab_item, value)
    if flag is None:
        return None, False
    return RISK_OF_FLAG.get(flag.value, flag.value), True


def evaluate(cases: list[dict]) -> dict:
    rows = []
    for c in cases:
        if c["lab_item"] == "복합검사":
            canon = "복합검사"
            pred, supported = _classify_composite(c["value"])
        else:
            pred, supported = _classify_qualitative(c["lab_item"], c["value"])
            if supported:
                canon = c["lab_item"]
            else:
                canon, pred, supported = _classify_single(c["lab_item"], c["value"])
        rows.append({
            "id": c["test_id"], "item": c["lab_item"], "value": c["value"],
            "true": c["risk_level"], "pred": pred, "supported": supported,
            "emergency": c["emergency"] == "Y", "canon": canon,
        })

    sup = [r for r in rows if r["supported"]]
    normal = [r for r in sup if r["true"] == "정상"]
    emer = [r for r in rows if r["emergency"]]
    return {
        "rows": rows, "n": len(rows), "supported": len(sup),
        "coverage": len(sup) / len(rows),
        "clinical_correctness": sum(r["pred"] == r["true"] for r in sup) / len(sup) if sup else None,
        "emergency_recall": sum(r["supported"] and r["pred"] == "응급" for r in emer) / len(emer) if emer else None,
        "over_warning": sum(r["pred"] != "정상" for r in normal) / len(normal) if normal else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="팀 골든 대비 임상 채점")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    res = evaluate([json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()])
    pct = lambda x: f"{x*100:5.1f}%" if x is not None else "  n/a"

    print("=" * 64)
    print("팀 공식 골든셋(100) 대비 현재 시스템 — 현재값 vs 목표값")
    print("=" * 64)
    print(f"{'지표':24}{'현재값':>9}{'MVP':>9}{'Target':>9}")
    print(f"{'Coverage(채점가능)':24}{pct(res['coverage']):>9}{'-':>9}{'-':>9}")
    print(f"{'Clinical Correctness':24}{pct(res['clinical_correctness']):>9}{'85%':>9}{'95%':>9}")
    print(f"{'Emergency Detection Recall':24}{pct(res['emergency_recall']):>9}{'100%':>9}{'100%':>9}")
    print(f"{'Over-warning Rate':24}{pct(res['over_warning']):>9}{'≤10%':>9}{'≤5%':>9}")
    print()

    miss = [r for r in res["rows"] if r["supported"] and r["pred"] != r["true"]]
    if miss:
        print("  분류 불일치 (컷오프 차이 가시화):")
        for r in miss:
            print(f"    {r['id']} {r['item']}={r['value']}  현재 {r['pred']} / 정답 {r['true']}")
    unsup = [r for r in res["rows"] if not r["supported"]]
    if unsup:
        print(f"\n  미지원 {len(unsup)}건 (항목 미수록 또는 비수치 소견):")
        print("    " + ", ".join(f"{r['item']}={r['value']}" for r in unsup))
    print()

    if not args.no_log:
        rec = harness.record_eval("clinical", {
            "n": res["n"], "coverage": res["coverage"],
            "clinical_correctness": res["clinical_correctness"],
            "emergency_recall": res["emergency_recall"], "over_warning": res["over_warning"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
