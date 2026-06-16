"""F-007 챗봇 UI 세션 헬퍼."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from gogodoc.application.chat_ui_contract import ChatUiContract
from gogodoc.domain.models import Sex, UserProfile


ConnGetter = Callable[[Any], Any]
ConnPutter = Callable[[Any, Any], None]
_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_test_ui_enabled(value: str | None) -> bool:
    """테스트용 챗봇 UI 노출 여부를 환경값에서 판정한다."""
    return str(value or "").strip().lower() in _TRUE_VALUES


def profile_from_session(sex: str | None, age: Any) -> UserProfile:
    """Streamlit session 값을 챗봇 답변용 사용자 프로필로 변환한다."""
    normalized_sex = Sex.FEMALE if sex == Sex.FEMALE.value else Sex.MALE
    try:
        normalized_age = int(age)
    except (TypeError, ValueError):
        normalized_age = 40
    return UserProfile(sex=normalized_sex, age=normalized_age)


def submit_latest_question(
    *,
    contract: ChatUiContract,
    pool: Any,
    user_id: int,
    question: str,
    profile: UserProfile | None,
    get_conn_fn: ConnGetter,
    put_conn_fn: ConnPutter,
) -> dict[str, Any] | None:
    """질문 1건을 최신 검진 결과 기반 챗봇 계약으로 제출한다."""
    normalized_question = (question or "").strip()
    if not normalized_question:
        return None

    conn = get_conn_fn(pool)
    try:
        return contract.answer_latest(
            conn=conn,
            user_id=user_id,
            question=normalized_question,
            profile=profile,
        )
    finally:
        put_conn_fn(pool, conn)


def append_chat_exchange(
    history: Sequence[Mapping[str, Any]],
    question: str,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """기존 대화 이력에 사용자 질문과 챗봇 응답을 추가한다."""
    updated = [dict(message) for message in history]
    updated.append({"role": "user", "content": question})
    updated.append({
        "role": "assistant",
        "content": str(payload.get("content") or ""),
        "payload": dict(payload),
    })
    return updated
