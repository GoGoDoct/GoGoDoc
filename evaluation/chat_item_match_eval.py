"""F-007 챗봇 항목명 유사 입력 매칭 평가.

최신 검진 결과에 있는 항목 후보를 기준으로 compact exact, report-gated alias,
제한 fuzzy 매칭이 안전하게 동작하는지 fake LLM으로 검증한다.

실행:
    python evaluation/chat_item_match_eval.py --no-log
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.application.chat_rag_service import ChatRagService
from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.domain.reference import reference_dict


GOLDEN = Path(__file__).resolve().parent / "datasets" / "chat_item_match_golden.jsonl"


class _CountingLLM:
    """호출 횟수와 입력을 기록하는 평가용 fake LLM."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task.value})
        return self.response


def load_cases(path: Path = GOLDEN) -> list[dict[str, Any]]:
    """JSONL 평가 케이스를 읽는다."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _latest_analysis(report_items: list[str]) -> dict[str, Any]:
    """케이스별 report_items로 최신 분석 결과 fixture를 만든다."""
    items_json: list[dict[str, Any]] = []
    for name in report_items:
        entry = reference_dict.lookup(name)
        if not entry:
            continue
        ranges = entry.get("ranges") or []
        value = ranges[0]["high"] if ranges else 1
        items_json.append({
            "name": name,
            "value": value,
            "value_text": str(value),
            "unit": entry.get("unit"),
            "status": "주의",
            "explain": entry.get("explanation", ""),
            "source": entry.get("source"),
        })
    return {
        "tracking_items": report_items,
        "emergency_alerts": [],
        "items_json": items_json,
    }


def _evaluate_case(case: dict[str, Any], service: ChatAnswerService, answer_llm: _CountingLLM) -> dict[str, Any]:
    """단일 케이스를 실행하고 기대 항목·route·LLM 호출 수를 비교한다."""
    before_answer_calls = len(answer_llm.calls)
    msg = service.answer(case["question"], _latest_analysis(case["report_items"]))
    answer_call_count = len(answer_llm.calls) - before_answer_calls
    actual = {
        "route_reason": msg.route_reason,
        "context_item_names": list(msg.context_item_names),
        "answer_llm_call_count": answer_call_count,
        "sources": list(msg.sources),
    }

    failures: list[str] = []
    if actual["context_item_names"] != case["expected_items"]:
        failures.append(
            f"context_item_names: expected {case['expected_items']!r}, got {actual['context_item_names']!r}"
        )
    if actual["route_reason"] != case["expected_route_reason"]:
        failures.append(
            f"route_reason: expected {case['expected_route_reason']!r}, got {actual['route_reason']!r}"
        )
    if actual["answer_llm_call_count"] != case["expected_answer_llm_call_count"]:
        failures.append(
            "answer_llm_call_count: "
            f"expected {case['expected_answer_llm_call_count']!r}, got {actual['answer_llm_call_count']!r}"
        )

    return {
        "id": case["id"],
        "case_type": case.get("case_type", ""),
        "question": case["question"],
        "expected_items": case["expected_items"],
        "ok": not failures,
        "failures": failures,
        "actual": actual,
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """항목명 매칭 평가를 실행한다."""
    classifier_llm = _CountingLLM('{"scope":"allowed","question_type":"checkup_explanation","route_reason":"fake"}')
    answer_llm = _CountingLLM("항목 매칭 평가용 답변입니다. 제공된 근거 안에서만 안내합니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )
    rows = [_evaluate_case(case, service, answer_llm) for case in cases]
    matched_items = sum(row["actual"]["context_item_names"] == row["expected_items"] for row in rows)
    false_positive_count = sum(
        not row["expected_items"] and bool(row["actual"]["context_item_names"])
        for row in rows
    )
    blocked_answer_llm_call_count = sum(
        row["actual"]["answer_llm_call_count"]
        for row in rows
        if not row["expected_items"]
    )
    uncertain_routing_count = sum(row["actual"]["route_reason"] == "item_match_uncertain" for row in rows)
    passed = sum(row["ok"] for row in rows)
    return {
        "n": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "item_match_accuracy": matched_items / len(rows) if rows else 0.0,
        "false_positive_count": false_positive_count,
        "uncertain_routing_count": uncertain_routing_count,
        "blocked_answer_llm_call_count": blocked_answer_llm_call_count,
        "rows": rows,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="F-007 챗봇 항목명 유사 입력 매칭 평가")
    parser.add_argument("--no-log", action="store_true", help="history 기록 생략")
    parser.add_argument("--verbose", action="store_true", help="전체 케이스 출력")
    args = parser.parse_args()

    result = evaluate(load_cases())
    print("=" * 56)
    print("F-007 챗봇 항목명 유사 입력 매칭 평가")
    print("=" * 56)
    print(f"  케이스 수              : {result['n']}")
    print(f"  통과                  : {result['passed']}/{result['n']}")
    print(f"  item match accuracy   : {result['item_match_accuracy']*100:5.1f}%")
    print(f"  false positive count  : {result['false_positive_count']}")
    print(f"  uncertain routing     : {result['uncertain_routing_count']}")
    print(f"  blocked answer LLM call count: {result['blocked_answer_llm_call_count']}")
    print()

    failures = [row for row in result["rows"] if not row["ok"]]
    if args.verbose or failures:
        for row in result["rows"]:
            if not args.verbose and row["ok"]:
                continue
            mark = "✓" if row["ok"] else "✗"
            actual = row["actual"]
            print(
                f"  {mark} {row['id']} [{row['case_type']}] "
                f"route={actual['route_reason']} llm={actual['answer_llm_call_count']} "
                f"items={actual['context_item_names']} :: {row['question']}"
            )
            for failure in row["failures"]:
                print(f"      - {failure}")
        print()

    if not args.no_log:
        rec = harness.record_eval("chat_item_match", {
            "n": result["n"],
            "item_match_accuracy": result["item_match_accuracy"],
            "false_positive_count": result["false_positive_count"],
            "uncertain_routing_count": result["uncertain_routing_count"],
            "blocked_answer_llm_call_count": result["blocked_answer_llm_call_count"],
            "failed": result["failed"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")

    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
