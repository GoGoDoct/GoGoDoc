"""F-004 단정 표현 필터 적대적 평가 (결정적, API 불필요)

해석/요약 후처리 필터(safety.sanitize_text)가 진단 단정 표현을 중화하는지 측정:
- 단정 차단율: 단정 표현(should_filter=true)이 실제로 바뀐 비율 (안전, 100% 목표)
- 오차단율: 정상 표현(should_filter=false)을 잘못 바꾼 비율 (0% 목표)

정규식 2차 방어의 커버리지를 추적한다 (1차 방어는 LLM 가드레일). 패러프레이즈 단정 포함.

실행
    python evaluation/assertion_eval.py            # 결정적 측정 + history 기록
    python evaluation/assertion_eval.py --no-log
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from gogodoc.domain.services.safety import sanitize_text

GOLDEN = Path(__file__).resolve().parent / "datasets" / "assertion_golden.jsonl"


def load_cases(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate(cases: list[dict]) -> dict:
    """필터 적용 후 변경 여부로 차단/오차단 집계"""
    rows = []
    for c in cases:
        changed = sanitize_text(c["text"]) != c["text"]
        ok = changed == c["should_filter"]
        rows.append({**c, "changed": changed, "ok": ok})
    pos = [r for r in rows if r["should_filter"]]
    neg = [r for r in rows if not r["should_filter"]]
    return {
        "rows": rows,
        "n": len(rows),
        "block_rate": sum(r["changed"] for r in pos) / len(pos) if pos else None,
        "over_block": sum(r["changed"] for r in neg) / len(neg) if neg else None,
        "missed": [r["id"] for r in pos if not r["changed"]],
        "false_block": [r["id"] for r in neg if r["changed"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="F-004 단정 표현 필터 적대적 평가")
    ap.add_argument("--no-log", action="store_true", help="history 기록 생략")
    args = ap.parse_args()

    res = evaluate(load_cases())
    print("=" * 56)
    print("F-004 단정 표현 필터 적대적 평가")
    print("=" * 56)
    for r in res["rows"]:
        mark = "✓" if r["ok"] else "✗"
        tag = "차단" if r["changed"] else "통과"
        print(f"  {mark} {r['id']} [{tag}] ({r['intent']}) {r['text']!r}")
    print()
    pct = lambda x: f"{x*100:5.1f}%" if x is not None else "  n/a"
    print(f"  단정 차단율 : {pct(res['block_rate'])}   # 안전 - 100% 목표")
    print(f"  오차단율    : {pct(res['over_block'])}   # 정상표현 오차단 - 0% 목표")
    if res["missed"]:
        print(f"  ⚠ 미차단 단정: {res['missed']}")
    if res["false_block"]:
        print(f"  ⚠ 정상표현 오차단: {res['false_block']}")
    print()

    if not args.no_log:
        rec = harness.record_eval("assertion", {
            "n": res["n"], "block_rate": res["block_rate"], "over_block": res["over_block"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")

    # 단정 미차단 또는 정상 오차단이 있으면 실패 (안전 게이트)
    return 1 if (res["missed"] or res["false_block"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
