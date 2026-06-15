"""오케스트레이션 - 4단계 파이프라인 (포트 의존, 도메인 규칙 호출)

단계 0(사용자 입력)은 interfaces 에서 수집
단계 ①③ 은 외부 기술(PDF·LLM) - 포트 주입
단계 ②④ 는 순수 도메인 규칙 - 포트 불필요
"""

import json

from pydantic import ValidationError

from gogodoc.application.ports import LLMPort, PdfParserPort, LLMTask
from gogodoc.application import prompts
from gogodoc.application.errors import ParseError
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
        """전체 파이프라인 실행 - 단계 1 실패는 ParseError 로 전파"""
        parsed = self._parse_extract(pdf_path)
        matched = self._match_range(parsed, profile)
        interpreted, notes = self._interpret(matched, profile)
        report = safety.summarize(interpreted)
        report.notes = notes
        return report

    def _parse_extract(self, pdf_path: str) -> ParsedReport:
        """단계 1 - 파싱·추출 (PDF 포트 + LLM 포트)

        텍스트 추출 실패·JSON 파싱 실패는 ParseError, 개별 행 오류는 건너뜀
        """
        raw_text = self._parser.extract_text(pdf_path)
        if not raw_text.strip():
            raise ParseError("PDF에서 텍스트를 추출하지 못했습니다")

        out = self._llm.complete(
            system=prompts.STRUCTURING_SYSTEM,
            user=raw_text,
            task=LLMTask.PARSE,
        )
        # JSON 대괄호 구간 추출
        start, end = out.find("["), out.rfind("]")
        if start == -1 or end == -1:
            raise ParseError("검사 항목 구조화에 실패했습니다")
        try:
            rows = json.loads(out[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ParseError("검사 항목 구조화에 실패했습니다") from exc

        # 개별 행 검증 실패는 건너뛰고 정상 행만 수집
        items: list[LabItem] = []
        for row in rows:
            try:
                items.append(LabItem.model_validate(row))
            except ValidationError:
                continue
        return ParsedReport(items=items)

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
    ) -> tuple[list[InterpretedItem], list[str]]:
        """단계 3 - 해석·설명 (LLM 포트, 근거 고정)

        개별 항목 LLM 실패는 전체 중단 없이 폴백 처리, 부분 실패는 notes 로 보고
        반환: (해석 항목 리스트, 비치명적 이슈 노트)
        """
        results: list[InterpretedItem] = []
        failed = 0
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

            # 개별 LLM 호출 실패는 폴백 - 전체 파이프라인 보호
            try:
                explanation = self._llm.complete(
                    system=prompts.INTERPRET_SYSTEM,
                    user=prompts.build_interpret_user(item, profile, grounding, rng),
                    task=LLMTask.INTERPRET,
                ).strip()
            except Exception:
                explanation = "해석 생성에 실패한 항목 - 의료진 상담 권장"
                failed += 1

            results.append(
                InterpretedItem(
                    **item.model_dump(),
                    explanation=explanation,
                    source=grounding.get("source"),
                )
            )

        notes = [f"{failed}개 항목 해석 생성 실패"] if failed else []
        return results, notes
