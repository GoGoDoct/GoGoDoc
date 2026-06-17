"""F-007 챗봇 RAG - 허용 질문에 공인 출처 근거로 답변 생성

흐름: 질문에서 검진 항목·카테고리 식별 → 근거카드·생활가이드(+내 검진결과) 검색 → 근거 고정 LLM 답변
스코프 분류·라우팅(석준)은 chat_service, 본 모듈은 허용 질문의 RAG 답변(희정)만 담당
근거가 전부 공인 출처(reference_dict·category_guide)라 환각 없이 출처 인용 가능
"""

import re

from gogodoc.application.ports import LLMPort, LLMTask
from gogodoc.application import prompts
from gogodoc.domain.services import safety
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.reference import reference_dict, category_guide
from gogodoc.domain.reference.synonyms import SYNONYMS
from gogodoc.domain.models import ChatMessage, Flag, QuestionType, Scope

# 한글 표기(표준명·한글 동의어, 2자 이상) -> 표준명. 챗봇 질문에 substring 으로 안전 매칭
# (fuzzy 는 1글자 조사 '이' 가 '중성지방'에 오매칭하는 등 챗봇엔 부적합 - 정확 매칭만)
_HANGUL = re.compile(r"[가-힣]")
_KOREAN_TERMS = {
    term: canon
    for term, canon in ({**{n: n for n in reference_dict.REFERENCE}, **SYNONYMS}).items()
    if _HANGUL.search(term) and len(term) >= 2 and canon in reference_dict.REFERENCE
}

# 일반 용어 -> 카테고리 (특정 항목명에 안 걸리는 포괄 질문용)
_CATEGORY_KEYWORDS = {
    "콜레스테롤": "지질", "지질": "지질", "중성지방": "지질",
    "혈당": "혈당", "당뇨": "혈당",
    "혈압": "혈압", "고혈압": "혈압",
    "간수치": "간기능", "간기능": "간기능",
    "빈혈": "혈액",
    "신장": "신장", "콩팥": "신장",
    "통풍": "대사",
    "비만": "비만", "체중": "비만",
    "전해질": "전해질",
}

_NO_GROUNDING = (
    "검진 결과에서 질문과 관련된 항목을 찾지 못했습니다. "
    "일반적인 건강 정보나 구체적인 판단은 전문의와 상담하시길 권장합니다. 본 답변은 참고용입니다."
)
_FALLBACK = "답변 생성에 실패했습니다. 잠시 후 다시 시도하시거나 전문의 상담을 권장합니다. 본 답변은 참고용입니다."

_FLAG_PRIORITY = {Flag.EMERGENCY: 0, Flag.ABNORMAL: 1, Flag.CAUTION: 2}


def _match_items(question: str) -> list[str]:
    """질문에서 언급된 검진 항목 추출 - 영문은 정확 매칭, 한글은 표기 substring (순서 보존)"""
    found: list[str] = []
    # 영문·약어 토큰 - 정확 동의어 매칭만 (fuzzy 미사용, 'ALT가'는 영문/한글 분리로 'ALT' 추출)
    for tok in re.findall(r"[A-Za-z0-9\-]+", question):
        if len(tok) < 2:
            continue
        canon, score, matched = canonicalize(tok)
        if matched and score == 100 and canon in reference_dict.REFERENCE and canon not in found:
            found.append(canon)
    # 한글 표기 substring (조사 결합 대응: '혈색소가'에서 '혈색소' 매칭)
    for term, canon in _KOREAN_TERMS.items():
        if term in question and canon not in found:
            found.append(canon)
    return found


def _match_categories(question: str, item_names: list[str]) -> list[str]:
    """매칭된 항목의 카테고리 + 포괄 키워드 카테고리 (순서 보존·중복 제거)"""
    cats: list[str] = []
    for name in item_names:
        c = category_guide.category_of(name)
        if c and c not in cats:
            cats.append(c)
    for kw, c in _CATEGORY_KEYWORDS.items():
        if kw in question and c not in cats:
            cats.append(c)
    return cats


def _range_text(entry: dict, profile) -> str:
    """프로필 있으면 성별·나이 범위, 없으면 첫 룰 범위"""
    if profile is not None:
        rng = reference_dict.select_range(entry, profile.sex.value, profile.age)
        if rng:
            return str(rng)
    rules = entry.get("ranges") or []
    return f"({rules[0]['low']}, {rules[0]['high']})" if rules else "-"


def _report_fallback(report, profile):
    """RAG 키워드 미매칭 시 보고서의 이상·주의 항목을 근거로 활용."""
    if not report:
        return {"items": [], "guides": []}, [], []

    flagged = sorted(
        [it for it in report.items if it.flag in _FLAG_PRIORITY],
        key=lambda x: _FLAG_PRIORITY[x.flag],
    )

    items_grounding, item_names, sources = [], [], []
    seen_cats: set[str] = set()
    guides_grounding = []

    for mine in flagged[:6]:
        entry = reference_dict.lookup(mine.canonical_name)
        if not entry:
            continue
        items_grounding.append({
            "name": mine.canonical_name,
            "explanation": entry["explanation"],
            "caution": entry["caution"],
            "range": _range_text(entry, profile),
            "source": entry["source"],
            "in_report": True,
            "value": mine.value,
            "flag": mine.flag.value,
        })
        item_names.append(mine.canonical_name)
        if entry["source"] not in sources:
            sources.append(entry["source"])

        c = category_guide.category_of(mine.canonical_name)
        if c and c not in seen_cats:
            g = category_guide.guide_for(c)
            if g:
                guides_grounding.append({"category": c, **g})
                if g["source"] not in sources:
                    sources.append(g["source"])
                seen_cats.add(c)

    return {"items": items_grounding, "guides": guides_grounding}, item_names, sources


class ChatRagService:
    """검진 결과 컨텍스트 + 공인 출처 근거 기반 챗봇 답변 (F-007 RAG)"""

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def _retrieve(self, question: str, report, profile):
        """질문 관련 항목·카테고리 근거 수집 - (grounding, 참조항목명, 출처목록)"""
        item_names = _match_items(question)
        categories = _match_categories(question, item_names)

        # 내 검진결과에서 해당 항목 값·flag 매핑
        report_items = {it.canonical_name: it for it in (report.items if report else [])}

        items_grounding = []
        sources: list[str] = []
        for name in item_names:
            entry = reference_dict.lookup(name)
            if not entry:
                continue
            mine = report_items.get(name)
            items_grounding.append({
                "name": name,
                "explanation": entry["explanation"],
                "caution": entry["caution"],
                "range": _range_text(entry, profile),
                "source": entry["source"],
                "in_report": mine is not None,
                "value": mine.value if mine else None,
                "flag": mine.flag.value if mine else None,
            })
            if entry["source"] not in sources:
                sources.append(entry["source"])

        guides_grounding = []
        for c in categories:
            g = category_guide.guide_for(c)
            if not g:
                continue
            guides_grounding.append({"category": c, **g})
            if g["source"] not in sources:
                sources.append(g["source"])

        return {"items": items_grounding, "guides": guides_grounding}, item_names, sources

    def answer(self, question: str, report=None, profile=None) -> ChatMessage:
        """허용 질문에 근거 기반 답변 생성. 키워드 미매칭 시 보고서 이상·주의 항목으로 폴백."""
        grounding, item_names, sources = self._retrieve(question, report, profile)

        if not grounding["items"] and not grounding["guides"]:
            grounding, item_names, sources = _report_fallback(report, profile)

        if not grounding["items"] and not grounding["guides"]:
            return ChatMessage(
                role="assistant", content=_NO_GROUNDING, scope_flag=Scope.ALLOWED,
                sources=[], context_item_names=[],
                question_type=QuestionType.UNKNOWN, route_reason="no_grounding",
            )

        try:
            out = self._llm.complete(
                system=prompts.CHAT_ANSWER_SYSTEM,
                user=prompts.build_chat_answer_user(question, grounding),
                task=LLMTask.INTERPRET,
            ).strip()
            out = safety.sanitize_text(out)
        except Exception:
            out = _FALLBACK

        return ChatMessage(
            role="assistant", content=out, scope_flag=Scope.ALLOWED,
            sources=sources, context_item_names=item_names,
            route_reason="rag_answer",
        )
