"""오케스트레이션 - 4단계 파이프라인 (포트 의존, 도메인 규칙 호출)

단계 0(사용자 입력)은 interfaces 에서 수집
단계 ①③ 은 외부 기술(PDF·LLM) - 포트 주입
단계 ②④ 는 순수 도메인 규칙 - 포트 불필요
"""

import json

from gogodoc.application.ports import LLMPort, PdfParserPort, LLMTask
from gogodoc.application import prompts
from gogodoc.domain.models import (
    UserProfile,
    ParsedReport,
    LabItem,
    MatchedItem,
    InterpretedItem,
    FinalReport,
)
from gogodoc.domain.services import normalization, classification, safety
from gogodoc.domain.reference import reference_dict


class Pipeline:
    """검진 결과 해석 파이프라인 - 어댑터 주입 후 실행"""

    def __init__(self, parser: PdfParserPort, llm: LLMPort) -> None:
        self._parser = parser
        self._llm = llm

    def run(self, pdf_path: str, profile: UserProfile) -> FinalReport:
        """전체 파이프라인 실행"""
        parsed = self._parse_extract(pdf_path)
        matched = self._match_range(parsed, profile)
        interpreted = self._interpret(matched, profile)
        return safety.summarize(interpreted)

    def _parse_extract(self, pdf_path: str) -> ParsedReport:
        """단계 1 - 파싱·추출 (PDF 포트 + LLM 포트)"""
        raw_text = self._parser.extract_text(pdf_path)
        out = self._llm.complete(
            system=prompts.STRUCTURING_SYSTEM,
            user=raw_text,
            task=LLMTask.PARSE,
        )
        # 견고성 위해 JSON 대괄호 구간 추출
        start, end = out.find("["), out.rfind("]")
        payload = out[start : end + 1] if start != -1 and end != -1 else "[]"
        rows = json.loads(payload)
        return ParsedReport(items=[LabItem.model_validate(r) for r in rows])

    def _match_range(
        self, parsed: ParsedReport, profile: UserProfile
    ) -> list[MatchedItem]:
        """단계 2 - 정상범위 매칭 (순수 도메인)"""
        results: list[MatchedItem] = []
        for item in parsed.items:
            canonical, score, matched = normalization.canonicalize(item.name)
            flag = classification.classify(
                canonical, item.value, profile.sex.value, profile.age
            )
            results.append(
                MatchedItem(
                    canonical_name=canonical,
                    raw_name=item.name,
                    value=item.value,
                    unit=item.unit,
                    flag=flag,
                    matched=matched,
                    match_score=score,
                )
            )
        return results

    def _interpret(
        self, matched: list[MatchedItem], profile: UserProfile
    ) -> list[InterpretedItem]:
        """단계 3 - 해석·설명 (LLM 포트, 근거 고정)"""
        results: list[InterpretedItem] = []
        for item in matched:
            grounding = reference_dict.lookup(item.canonical_name)
            rng = (
                reference_dict.select_range(grounding, profile.sex.value, profile.age)
                if grounding
                else None
            )

            # 미매칭·기준 미해당 항목 - LLM 호출 없이 상담 안내
            if not grounding or rng is None:
                msg = (
                    "해설 기준이 없는 항목 - 의료진 상담 권장"
                    if not grounding
                    else "성인(19세 이상) 기준만 제공 - 의료진 상담 권장"
                )
                results.append(
                    InterpretedItem(
                        **item.model_dump(),
                        explanation=msg,
                        source=grounding.get("source") if grounding else None,
                    )
                )
                continue

            explanation = self._llm.complete(
                system=prompts.INTERPRET_SYSTEM,
                user=prompts.build_interpret_user(item, profile, grounding, rng),
                task=LLMTask.INTERPRET,
            )
            results.append(
                InterpretedItem(
                    **item.model_dump(),
                    explanation=explanation.strip(),
                    source=grounding.get("source"),
                )
            )
        return results
