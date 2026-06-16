"""병원 추천 서비스 - 분석 결과 기반 HIRA 병원 조회"""

from __future__ import annotations

import json
import logging

from gogodoc.application.ports import LLMPort, LLMTask
from gogodoc.domain.reference.admin_code import location_to_codes
from gogodoc.infrastructure.config import Settings
from gogodoc.infrastructure.hira.hira_client import (
    HiraApiError,
    get_hospital_departments,
    get_hospitals_by_region,
)

logger = logging.getLogger(__name__)

_FLAG_SET = {"caution", "abnormal", "emergency"}

_DEPT_SYSTEM_PROMPT = (
    "당신은 건강검진 결과를 보고 필요한 진료과목을 추천하는 의료 도우미입니다. "
    "항목명과 상태를 보고 방문해야 할 진료과목을 JSON 배열로만 반환하세요. "
    '예: ["내분비내과", "심장내과"]'
)

_MAX_RESULTS = 5


def recommend_hospitals(
    result: dict,
    location: str,
    llm: LLMPort,
    settings: Settings,
) -> list[dict]:
    """분석 결과 기반 병원 추천 - 최대 5개 반환

    Args:
        result: session_state.result 또는 DB find_latest() 반환값
        location: users.location (예: "서울 강남구")
        llm: OpenAILLM 인스턴스
        settings: 앱 설정 (hira_api_key 포함)

    Returns:
        병원 정보 dict 리스트 (name, address, tel, url, departments)
        flag 항목 없거나 지역 코드 변환 실패 시 []
    """
    flagged = [
        it for it in result.get("items", [])
        if it.get("flag") in _FLAG_SET
    ]
    if not flagged:
        return []

    departments = _map_departments(flagged, llm)

    sido_cd, sggu_cd = location_to_codes(location)
    if not sido_cd:
        logger.warning("거주지 행정코드 변환 실패: %s", location)
        return []

    hospitals = _fetch_hospitals(settings.hira_api_key, sido_cd, sggu_cd)
    if not hospitals:
        return []

    hospitals = _attach_departments(settings.hira_api_key, hospitals)
    hospitals = _filter_by_departments(hospitals, departments)

    return hospitals[:_MAX_RESULTS]


def _map_departments(flagged_items: list[dict], llm: LLMPort) -> list[str]:
    """LLM으로 이상 항목 → 진료과목 매핑"""
    lines = "\n".join(
        f"- {it['name']}: {it['flag']}" for it in flagged_items
    )
    user_msg = f"다음 검진 항목에 대해 필요한 진료과목을 추천해주세요.\n{lines}"

    try:
        raw = llm.complete(_DEPT_SYSTEM_PROMPT, user_msg, LLMTask.RECOMMEND)
        result = json.loads(raw)
        return result if isinstance(result, list) else ["내과"]
    except Exception as e:
        logger.warning("진료과목 LLM 매핑 실패: %s", e)
        return ["내과"]  # 기본값


def _fetch_hospitals(api_key: str, sido_cd: str, sggu_cd: str) -> list[dict]:
    """HIRA 병원목록 조회 - 시군구 실패 시 시도 단위로 재조회"""
    try:
        hospitals = get_hospitals_by_region(api_key, sido_cd, sggu_cd)
        if not hospitals and sggu_cd:
            hospitals = get_hospitals_by_region(api_key, sido_cd)
        return hospitals
    except HiraApiError as e:
        logger.error("HIRA 병원목록 조회 실패: %s", e)
        return []


def _attach_departments(api_key: str, hospitals: list[dict]) -> list[dict]:
    """각 병원 진료과목 조회 후 departments 필드 채우기"""
    for hosp in hospitals:
        try:
            hosp["departments"] = get_hospital_departments(api_key, hosp["ykiho"])
        except HiraApiError:
            hosp["departments"] = []
    return hospitals


def _filter_by_departments(
    hospitals: list[dict], departments: list[str]
) -> list[dict]:
    """필요 진료과목 보유 병원 필터 - 없으면 전체 반환"""
    if not departments:
        return hospitals

    filtered = [
        h for h in hospitals
        if any(dept in h["departments"] for dept in departments)
    ]
    return filtered if filtered else hospitals
