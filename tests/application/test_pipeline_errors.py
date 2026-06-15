"""파이프라인 에러 핸들링·폴백 테스트 (D3)

가짜 어댑터로 실패 시나리오 주입 - 치명/비치명 구분 검증
"""

import pytest

from gogodoc.application.pipeline import Pipeline
from gogodoc.application.ports import LLMTask
from gogodoc.application.errors import ParseError
from gogodoc.domain.models import UserProfile, Sex, Flag
from gogodoc.domain.reference import reference_dict


def _profile():
    return UserProfile(sex=Sex.MALE, age=40)


class _Retriever:
    """ReferenceRetrieverPort 가짜 구현 - dict 조회"""

    def retrieve(self, canonical_name: str) -> dict | None:
        return reference_dict.lookup(canonical_name)


class _Parser:
    """고정 텍스트 반환 파서"""

    def __init__(self, text="더미 텍스트"):
        self._text = text

    def extract_text(self, pdf_path: str) -> str:
        return self._text


class _LLM:
    """용도별 응답·예외 주입 가능한 가짜 LLM"""

    def __init__(self, parse_out='[{"name": "GPT", "value": 20, "unit": "U/L"}]', interpret_raises=False):
        self._parse_out = parse_out
        self._interpret_raises = interpret_raises

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        if task == LLMTask.PARSE:
            return self._parse_out
        if self._interpret_raises:
            raise RuntimeError("LLM 호출 실패")
        return "쉬운 설명 예시"


def test_empty_text_raises_parse_error():
    # 텍스트 추출 실패 - 치명 오류
    pipeline = Pipeline(parser=_Parser(""), llm=_LLM(), retriever=_Retriever())
    with pytest.raises(ParseError):
        pipeline.run("dummy.pdf", _profile())


def test_bad_json_raises_parse_error():
    # 구조화 JSON 파싱 실패 - 치명 오류
    pipeline = Pipeline(parser=_Parser(), llm=_LLM(parse_out="JSON 아님"), retriever=_Retriever())
    with pytest.raises(ParseError):
        pipeline.run("dummy.pdf", _profile())


def test_invalid_row_skipped():
    # 필수 필드 누락 행은 건너뛰고 정상 행만 처리 - 비치명
    parse_out = '[{"name": "GPT", "value": 20}, {"value": 99}]'
    pipeline = Pipeline(parser=_Parser(), llm=_LLM(parse_out=parse_out), retriever=_Retriever())
    report = pipeline.run("dummy.pdf", _profile())
    assert len(report.items) == 1
    assert report.items[0].canonical_name == "ALT"


def test_interpret_failure_is_resilient():
    # 개별 해석 실패는 폴백 처리, 전체 중단 없음 - 비치명
    pipeline = Pipeline(parser=_Parser(), llm=_LLM(interpret_raises=True), retriever=_Retriever())
    report = pipeline.run("dummy.pdf", _profile())
    assert "실패" in report.items[0].explanation
    assert report.notes  # 부분 실패 보고


def test_check_needed_for_null_value():
    # 수치 null 항목 - 확인필요 플래그, LLM 미호출 확인 안내
    pipeline = Pipeline(
        parser=_Parser(),
        llm=_LLM(parse_out='[{"name": "GPT", "value": null, "unit": "U/L"}]'),
        retriever=_Retriever(),
    )
    report = pipeline.run("dummy.pdf", _profile())
    assert report.items[0].flag == Flag.CHECK_NEEDED
    assert "확인" in report.items[0].explanation
