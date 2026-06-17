"""F-007 챗봇 답변 서비스 스모크 검증 CLI.

UI를 건드리지 않고 DB 최신 analysis_results 1건을 ChatAnswerService에 연결해 확인한다.
기본 fake 모드는 OpenAI API를 호출하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.application.chat_rag_service import ChatRagService
from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.composition import build_chat_answer_service
from gogodoc.domain.models import ChatMessage, QuestionType
from gogodoc.infrastructure.config import Settings, load_settings
from gogodoc.infrastructure.db.analysis_repository import find_latest


EXIT_DB_ERROR = 1
EXIT_NO_ANALYSIS = 2


class NoAnalysisError(RuntimeError):
    """해당 사용자 최신 분석 결과가 없을 때 발생."""


class _CountingLLM:
    """스모크 검증용 fake LLM."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task.value})
        return self.response


class _FakeClassifierLLM:
    """질문별 구조화 라벨을 반환하는 스모크용 fake classifier."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task.value})
        if any(token in user for token in ("요약", "전반적", "전체적", "제일 문제")):
            return '{"scope":"allowed","question_type":"checkup_summary","route_reason":"fake_summary"}'
        if any(token in user for token in ("음식", "식단", "운동", "술", "체중", "관리")):
            return '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"fake_lifestyle"}'
        if "과" in user or "상담" in user:
            return '{"scope":"allowed","question_type":"department_guide","route_reason":"fake_department"}'
        return '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"fake_explanation"}'


def _message_to_result(
    message: ChatMessage,
    *,
    answer_llm_called: bool,
    answer_llm_call_count: int,
    mode: str,
    preview_chars: int,
) -> dict[str, Any]:
    """ChatMessage를 CLI 출력용 JSON dict로 변환한다."""
    return {
        "mode": mode,
        "scope_flag": message.scope_flag.value if message.scope_flag else None,
        "routed": message.routed,
        "question_type": message.question_type.value if message.question_type else None,
        "route_reason": message.route_reason,
        "context_item_names": message.context_item_names,
        "sources": message.sources,
        "answer_llm_called": answer_llm_called,
        "answer_llm_call_count": answer_llm_call_count,
        "answer_preview": message.content[:preview_chars],
    }


def _fake_service() -> tuple[ChatAnswerService, _CountingLLM]:
    """OpenAI 호출 없는 스모크용 서비스와 answer LLM counter를 만든다."""
    classifier_llm = _FakeClassifierLLM()
    answer_llm = _CountingLLM("스모크 확인용 답변입니다. 출처: 대한비만학회. 참고용입니다.")
    return (
        ChatAnswerService(
            router=ChatService(classifier_llm),
            rag=ChatRagService(answer_llm),
        ),
        answer_llm,
    )


def _real_service(settings: Settings | None = None) -> ChatAnswerService:
    """실제 설정 기반 서비스 생성."""
    return build_chat_answer_service(settings or load_settings())


def _infer_real_answer_llm_called(message: ChatMessage) -> bool:
    """real 모드에서는 내부 LLM 호출을 계측하지 못하므로 근거 존재 여부로 추정한다."""
    if message.scope_flag and message.scope_flag.value == "blocked":
        return False
    if message.question_type == QuestionType.CHECKUP_SUMMARY:
        return False
    return bool(message.context_item_names or message.sources)


def run_smoke(
    *,
    question: str,
    latest_analysis: dict[str, Any] | None,
    mode: str = "fake",
    preview_chars: int = 500,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """최신 분석 결과 1건으로 챗봇 답변 서비스를 실행하고 출력 dict를 반환한다."""
    if mode == "fake":
        service, answer_llm = _fake_service()
        decision = service.classify(question)
        routed = service.route_decision(decision)
        if routed is not None:
            message = routed
        else:
            if latest_analysis is None:
                raise NoAnalysisError("해당 user_id의 analysis_results 없음")
            message = service.answer_allowed(question, latest_analysis, decision=decision)
        answer_llm_call_count = len(answer_llm.calls)
        answer_llm_called = bool(answer_llm_call_count)
    elif mode == "real":
        service = _real_service(settings)
        decision = service.classify(question)
        routed = service.route_decision(decision)
        if routed is not None:
            message = routed
        else:
            if latest_analysis is None:
                raise NoAnalysisError("해당 user_id의 analysis_results 없음")
            message = service.answer_allowed(question, latest_analysis, decision=decision)
        answer_llm_call_count = 1 if _infer_real_answer_llm_called(message) else 0
        answer_llm_called = _infer_real_answer_llm_called(message)
    else:
        raise ValueError(f"지원하지 않는 mode: {mode}")

    return _message_to_result(
        message,
        answer_llm_called=answer_llm_called,
        answer_llm_call_count=answer_llm_call_count,
        mode=mode,
        preview_chars=preview_chars,
    )


def load_latest_analysis(user_id: int, settings: Settings | None = None) -> dict[str, Any] | None:
    """DB에서 최신 analysis_results 1건을 읽는다."""
    settings = settings or load_settings()
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )
    try:
        return find_latest(conn, user_id)
    finally:
        conn.close()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F-007 챗봇 답변 서비스 스모크 검증")
    parser.add_argument("--user-id", type=int, required=True, help="조회할 사용자 id")
    parser.add_argument("--question", required=True, help="챗봇에 입력할 질문")
    parser.add_argument(
        "--mode",
        choices=("fake", "real"),
        default="fake",
        help="fake는 OpenAI 호출 없음, real은 실제 설정으로 호출",
    )
    parser.add_argument("--preview-chars", type=int, default=500, help="답변 미리보기 길이")
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    latest_loader: Callable[[int], dict[str, Any] | None] | None = None,
) -> int:
    """CLI entrypoint. 테스트에서는 latest_loader를 주입한다."""
    args = _parse_args(argv)
    loader = latest_loader or load_latest_analysis

    try:
        latest = loader(args.user_id)
    except Exception as exc:
        print(f"DB 연결 또는 조회 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_DB_ERROR

    try:
        result = run_smoke(
            question=args.question,
            latest_analysis=latest,
            mode=args.mode,
            preview_chars=args.preview_chars,
        )
    except NoAnalysisError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NO_ANALYSIS
    except Exception as exc:
        print(f"스모크 검증 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_DB_ERROR

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
