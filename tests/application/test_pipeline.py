"""파이프라인 통합 테스트 - 가짜 어댑터 주입으로 API 호출 없이 검증

Ports & Adapters 구조 덕분에 LLM·PDF 없이 end-to-end 검증 가능
"""

from gogodoc.application.pipeline import Pipeline
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import UserProfile, Sex, Flag
from gogodoc.domain.reference import reference_dict


class FakeParser:
    """PdfParserPort 가짜 구현 - 고정 텍스트 반환"""

    def extract_text(self, pdf_path: str) -> str:
        return "검사항목 더미 텍스트"


class FakeRetriever:
    """ReferenceRetrieverPort 가짜 구현 - dict 조회"""

    def retrieve(self, canonical_name: str) -> dict | None:
        return reference_dict.lookup(canonical_name)


class FakeLLM:
    """LLMPort 가짜 구현 - 용도별 고정 응답"""

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        if task == LLMTask.PARSE:
            return '[{"name": "GPT", "value": 200, "unit": "U/L", "reference_range": "0-40"}]'
        return "쉬운 설명 예시"


def test_pipeline_end_to_end():
    # 가짜 어댑터로 전체 파이프라인 관통
    pipeline = Pipeline(parser=FakeParser(), llm=FakeLLM(), retriever=FakeRetriever())
    report = pipeline.run("dummy.pdf", UserProfile(sex=Sex.MALE, age=40))

    # GPT -> ALT 정규화, 200 -> 이상 판정
    assert report.items[0].canonical_name == "ALT"
    assert report.items[0].flag == Flag.ABNORMAL
    # 추적 항목·면책 포함
    assert "ALT" in report.tracking_items
    assert report.disclaimer
