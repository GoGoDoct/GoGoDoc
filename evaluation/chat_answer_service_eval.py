"""F-007 ChatAnswerService 통합 정책 평가.

분류기, 안전 라우팅, 최신 결과 변환, RAG 호출 정책을 ChatAnswerService 기준으로 검증한다.
실제 OpenAI API를 호출하지 않고 fake classifier와 counting answer LLM을 사용한다.

실행:
    python evaluation/chat_answer_service_eval.py --no-log
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
from gogodoc.domain.policy import DISCLAIMER


GOLDEN = Path(__file__).resolve().parent / "datasets" / "chat_answer_service_golden.jsonl"


class _CountingLLM:
    """호출 횟수와 입력을 기록하는 평가용 fake LLM."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task.value})
        return self.response


class _CaseClassifierLLM:
    """케이스별 구조화 분류 결과를 반환하는 fake classifier."""

    def __init__(self, responses: dict[str, dict[str, str]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task.value})
        response = self.responses.get(user)
        if response is None:
            return '{"scope":"blocked","question_type":"unknown","route_reason":"missing_fake_classifier"}'
        return json.dumps(response, ensure_ascii=False)


def load_cases(path: Path = GOLDEN) -> list[dict[str, Any]]:
    """JSONL 평가 케이스를 읽는다."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _baseline_latest_analysis() -> dict[str, Any]:
    """통합 평가용 최신 분석 결과 fixture."""
    return {
        "tracking_items": ["BMI", "ALT"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "BMI",
                "value": 27.1,
                "value_text": "27.1",
                "unit": "kg/m2",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            },
            {
                "name": "ALT",
                "value": 60,
                "value_text": "60",
                "unit": "U/L",
                "status": "주의",
                "explain": "간 건강을 보는 대표 지표입니다.",
                "source": "질병관리청 국가건강정보포털 간기능검사",
            },
        ],
    }


def _liver_latest_analysis() -> dict[str, Any]:
    """실제 말투 평가용 간기능 fixture."""
    return {
        "tracking_items": ["AST", "ALT", "감마지티피"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "AST",
                "value": 42,
                "value_text": "42",
                "unit": "U/L",
                "status": "주의",
                "explain": "간뿐 아니라 근육·심장에도 있는 효소입니다.",
                "source": "질병관리청 국가건강정보포털 간기능검사",
            },
            {
                "name": "ALT",
                "value": 60,
                "value_text": "60",
                "unit": "U/L",
                "status": "주의",
                "explain": "간 건강을 보는 대표 지표입니다.",
                "source": "질병관리청 국가건강정보포털 간기능검사",
            },
            {
                "name": "감마지티피",
                "value": 68,
                "value_text": "68",
                "unit": "U/L",
                "status": "주의",
                "explain": "간담도계 상태를 함께 보는 효소 지표입니다.",
                "source": "연세대 의과대학 건강정보 감마글루타밀전이효소",
            },
        ],
    }


def _rich_latest_analysis() -> dict[str, Any]:
    """실제 말투 평가용 혈당·지질·혈액 fixture."""
    return {
        "tracking_items": ["당화혈색소", "총콜레스테롤", "중성지방"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "당화혈색소",
                "value": 5.8,
                "value_text": "5.8",
                "unit": "%",
                "status": "주의",
                "explain": "최근 혈당 흐름을 보는 지표입니다.",
                "source": "대한당뇨병학회 당뇨병 진료지침",
            },
            {
                "name": "공복혈당",
                "value": 92,
                "value_text": "92",
                "unit": "mg/dL",
                "status": "정상",
                "explain": "공복 상태의 혈당을 보는 지표입니다.",
                "source": "대한당뇨병학회 당뇨병 진료지침",
            },
            {
                "name": "총콜레스테롤",
                "value": 225,
                "value_text": "225",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "혈중 전체 콜레스테롤 양을 보는 지표입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "중성지방",
                "value": 180,
                "value_text": "180",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "혈액 속 지방 성분입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "헤모글로빈",
                "value": 13.8,
                "value_text": "13.8",
                "unit": "g/dL",
                "status": "정상",
                "explain": "빈혈 여부를 보는 혈액 지표입니다.",
                "source": "서울아산병원 의료정보 일반혈액검사",
            },
        ],
    }


def _waist_latest_analysis() -> dict[str, Any]:
    """실제 말투 평가용 비만·허리둘레 fixture."""
    return {
        "tracking_items": ["BMI", "허리둘레"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "BMI",
                "value": 27.1,
                "value_text": "27.1",
                "unit": "kg/m2",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            },
            {
                "name": "허리둘레",
                "value": 92,
                "value_text": "92",
                "unit": "cm",
                "status": "주의",
                "explain": "복부비만 위험을 보는 지표입니다.",
                "source": "대한비만학회 비만 진료지침",
            },
        ],
    }


def _kidney_latest_analysis() -> dict[str, Any]:
    """실제 말투 평가용 신장 기능 fixture."""
    return {
        "tracking_items": ["크레아티닌", "eGFR"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "크레아티닌",
                "value": 1.3,
                "value_text": "1.3",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "신장 여과 기능을 보는 지표입니다.",
                "source": "서울아산병원 의료정보 크레아티닌",
            },
            {
                "name": "eGFR",
                "value": 75,
                "value_text": "75",
                "unit": "mL/min/1.73m2",
                "status": "주의",
                "explain": "신장 여과 기능을 종합적으로 보는 지표입니다.",
                "source": "서울아산병원 의료정보 신장기능검사",
            },
        ],
    }


def _latest_analysis(name: str) -> dict[str, Any] | None:
    """케이스 이름에 맞는 최신 분석 결과 fixture를 반환한다."""
    if name == "baseline":
        return _baseline_latest_analysis()
    if name == "liver":
        return _liver_latest_analysis()
    if name == "rich":
        return _rich_latest_analysis()
    if name == "waist":
        return _waist_latest_analysis()
    if name == "kidney":
        return _kidney_latest_analysis()
    if name == "empty":
        return {"tracking_items": [], "emergency_alerts": [], "items_json": []}
    if name == "none":
        return None
    raise ValueError(f"지원하지 않는 latest_analysis fixture: {name}")


def _contains_all(haystack: list[str] | str, needles: list[str]) -> bool:
    """문자열 또는 문자열 목록에 기대 조각이 모두 들어있는지 확인한다."""
    if isinstance(haystack, list):
        return all(any(needle in item for item in haystack) for needle in needles)
    return all(needle in haystack for needle in needles)


def _evaluate_case(case: dict[str, Any], service: ChatAnswerService, answer_llm: _CountingLLM) -> dict[str, Any]:
    """단일 케이스를 실행하고 기대값과 비교한다."""
    before_answer_calls = len(answer_llm.calls)
    latest = _latest_analysis(case.get("latest_analysis", "baseline"))
    msg = service.answer(case["question"], latest)
    answer_call_count = len(answer_llm.calls) - before_answer_calls
    expected = case["expected"]

    actual = {
        "scope_flag": msg.scope_flag.value if msg.scope_flag else None,
        "routed": msg.routed,
        "question_type": msg.question_type.value if msg.question_type else None,
        "route_reason": msg.route_reason,
        "answer_llm_call_count": answer_call_count,
        "context_item_names": list(msg.context_item_names),
        "sources": list(msg.sources),
        "content": msg.content,
    }

    failures: list[str] = []
    for field in ("scope_flag", "routed", "question_type", "route_reason", "answer_llm_call_count"):
        if field in expected and actual[field] != expected[field]:
            failures.append(f"{field}: expected {expected[field]!r}, got {actual[field]!r}")
    if "context_item_names" in expected and actual["context_item_names"] != expected["context_item_names"]:
        failures.append(
            f"context_item_names: expected {expected['context_item_names']!r}, got {actual['context_item_names']!r}"
        )
    if not _contains_all(actual["sources"], expected.get("sources_contains", [])):
        failures.append(f"sources_contains: missing {expected.get('sources_contains', [])!r}")
    if not _contains_all(actual["content"], expected.get("content_contains", [])):
        failures.append(f"content_contains: missing {expected.get('content_contains', [])!r}")
    if expected.get("requires_disclaimer") and DISCLAIMER not in actual["content"]:
        failures.append("requires_disclaimer: missing disclaimer")

    return {
        "id": case["id"],
        "question": case["question"],
        "ok": not failures,
        "failures": failures,
        "actual": actual,
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """통합 정책 평가를 실행한다."""
    classifier_responses = {
        case["question"]: case["classifier"]
        for case in cases
        if "classifier" in case
    }
    classifier_llm = _CaseClassifierLLM(classifier_responses)
    answer_llm = _CountingLLM("통합 평가용 답변입니다. 제공된 근거 안에서만 안내합니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )
    rows = [_evaluate_case(case, service, answer_llm) for case in cases]
    passed = sum(row["ok"] for row in rows)
    return {
        "n": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "accuracy": passed / len(rows) if rows else 0.0,
        "rows": rows,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="F-007 ChatAnswerService 통합 정책 평가")
    parser.add_argument("--no-log", action="store_true", help="history 기록 생략")
    args = parser.parse_args()

    result = evaluate(load_cases())

    print("=" * 56)
    print("F-007 ChatAnswerService 통합 정책 평가")
    print("=" * 56)
    for row in result["rows"]:
        mark = "✓" if row["ok"] else "✗"
        actual = row["actual"]
        print(
            f"  {mark} {row['id']} "
            f"[{actual['scope_flag']}/{actual['question_type']}/llm={actual['answer_llm_call_count']}] "
            f"{row['question']}"
        )
        for failure in row["failures"]:
            print(f"      - {failure}")
    print()
    print(f"  통합 정책 정확도: {result['accuracy']*100:5.1f}%  ({result['passed']}/{result['n']})")
    print()

    if not args.no_log:
        rec = harness.record_eval("chat_answer_service", {
            "n": result["n"],
            "accuracy": result["accuracy"],
            "failed": result["failed"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")

    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
