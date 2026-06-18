"""F-007 챗봇 RAG - 허용 질문에 공인 출처 근거로 답변 생성

흐름: 질문에서 검진 항목·카테고리 식별 → 근거카드·생활가이드(+내 검진결과) 검색 → 근거 고정 LLM 답변
스코프 분류·라우팅(석준)은 chat_service, 본 모듈은 허용 질문의 RAG 답변(희정)만 담당
근거가 전부 공인 출처(reference_dict·category_guide)라 환각 없이 출처 인용 가능
"""

import re

from rapidfuzz import fuzz

from gogodoc.application.ports import LLMPort, LLMTask
from gogodoc.application import prompts
from gogodoc.domain.services import safety
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.reference import reference_dict, category_guide
from gogodoc.domain.reference.synonyms import SYNONYMS
from gogodoc.domain.models import ChatMessage, Flag, QuestionType, Scope

# 한글 표기(표준명·한글 동의어, 2자 이상) -> 표준명. 전역 substring 은 정확 매칭만 사용한다.
# typo fuzzy 는 최신 결과에 있는 후보로 제한한 _match_report_gated_items 에서만 수행한다.
_HANGUL = re.compile(r"[가-힣]")
_TOKEN = re.compile(r"[A-Za-z0-9가-힣γ]+")
_COMPACT_REMOVE = re.compile(r"[\s\-_/.()]+")
_TERM_CANONS = {**{n: n for n in reference_dict.REFERENCE}, **SYNONYMS}
_KOREAN_TERMS = {
    term: canon
    for term, canon in _TERM_CANONS.items()
    if _HANGUL.search(term) and len(term) >= 2 and canon in reference_dict.REFERENCE
}

_JOSA_SUFFIXES = (
    "에서는", "에서", "으로", "하고", "에게", "까지", "부터", "처럼", "보다",
    "은", "는", "이", "가", "을", "를", "도", "만", "랑", "와", "과", "의", "에", "로",
)
_JOINER_PARTICLES = ("랑", "와", "과")
_HEIGHT_KEYWORD_CONTEXT = re.compile(
    r"^\s*(이|은|는|도)?\s*(몇|[0-9]+(?:\.[0-9]+)?\s*(cm|센티)?|cm|센티)"
)
_BODY_ALIAS_NON_CHECKUP_CONTEXT = re.compile(
    r"운동|스트레칭|통증|아프|아픈|아파|저리|저린|저려|불편|붓|부었|부어|멍울|혹|염증|증상"
)

# 짧은 대화형 표현은 공식 동의어가 아니라, 최신 결과에 대상 항목이 있을 때만 허용한다.
_SHORT_ALIASES = {
    "감마": "감마지티피",
    "당화": "당화혈색소",
    "총콜": "총콜레스테롤",
    "중성": "중성지방",
    "크레아": "크레아티닌",
    "사구체": "eGFR",
    "허리": "허리둘레",
    "복부": "허리둘레",
    "갑상선": "TSH",
    "전립선": "PSA",
}
_BODY_PART_ALIASES = {"허리", "복부", "갑상선", "전립선"}

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
_ITEM_MATCH_UNCERTAIN = (
    "질문에서 검진 항목명을 정확히 특정하지 못했습니다. "
    "검진 결과지에 표시된 항목명을 포함해 다시 질문해 주세요. 본 답변은 참고용입니다."
)
_FALLBACK = "답변 생성에 실패했습니다. 잠시 후 다시 시도하시거나 전문의 상담을 권장합니다. 본 답변은 참고용입니다."

_FLAG_PRIORITY = {Flag.EMERGENCY: 0, Flag.ABNORMAL: 1, Flag.CAUTION: 2}
_REFERENCE_ONLY_NOTICE = (
    "최신 검진 결과에서 {names} 항목은 찾지 못했습니다. "
    "따라서 개인 수치 판정이 아니라 공인 출처 기반 일반 정보로 안내드립니다."
)
_REPORT_FALLBACK_NOTICE = (
    "질문에서 특정 검진 항목을 찾지 못해 최신 검진 결과의 주의·이상 항목을 기준으로 안내드립니다."
)
_REPORT_FALLBACK_TRIGGERS = (
    "어느 진료과", "어느 과", "무슨 과", "어떤 과", "진료과", "병원", "상담",
    "검진 결과", "전체", "전반", "확인해야 할 항목", "주의 항목", "이상 항목",
)


def _compact_key(text: str) -> str:
    """공백·구분자를 제거한 항목명 비교 key."""
    return _COMPACT_REMOVE.sub("", text).strip().lower()


def _unique_compact_terms(terms: dict[str, str]) -> dict[str, str]:
    """compact key가 한 표준항목에만 대응될 때만 안전 매칭 후보로 둔다."""
    compact_to_canon: dict[str, str | None] = {}
    for term, canon in terms.items():
        if canon not in reference_dict.REFERENCE:
            continue
        key = _compact_key(term)
        if len(key) < 3:
            continue
        if key in compact_to_canon and compact_to_canon[key] != canon:
            compact_to_canon[key] = None
        else:
            compact_to_canon[key] = canon
    return {key: canon for key, canon in compact_to_canon.items() if canon is not None}


_COMPACT_TERMS = _unique_compact_terms(_TERM_CANONS)


def _has_hangul(text: str) -> bool:
    return bool(_HANGUL.search(text))


def _strip_josa(text: str) -> str:
    """짧은 alias 비교 전 조사만 제거한다."""
    for suffix in _JOSA_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def _item_prefix_keys(item_names: list[str]) -> list[str]:
    """이미 질문에서 매칭된 항목의 공식명·동의어 compact prefix 후보."""
    prefixes = {
        _compact_key(term)
        for term, canon in _TERM_CANONS.items()
        if canon in item_names and len(_compact_key(term)) >= 2
    }
    return sorted(prefixes, key=len, reverse=True)


def _category_prefix_keys() -> list[str]:
    """카테고리 키워드 compact prefix 후보."""
    prefixes = {_compact_key(keyword) for keyword in _CATEGORY_KEYWORDS if len(_compact_key(keyword)) >= 2}
    return sorted(prefixes, key=len, reverse=True)


def _alias_guard_fragments(
    key: str,
    item_prefixes: list[str] | None = None,
    category_prefixes: list[str] | None = None,
) -> list[tuple[str, bool]]:
    """짧은 alias가 접속 조사 뒤에 붙어 있는 fragment까지 검사한다."""
    fragments = [(key, False)]
    for joiner in _JOINER_PARTICLES:
        parts = [part for part in key.split(joiner) if part]
        for part in parts[1:]:
            fragments.append((_strip_josa(part), True))
    for prefix in item_prefixes or []:
        if key.startswith(prefix) and len(key) > len(prefix):
            fragments.append((_strip_josa(key[len(prefix):]), True))
    for prefix in category_prefixes or []:
        if key.startswith(prefix) and len(key) > len(prefix):
            fragments.append((_strip_josa(key[len(prefix):]), True))
    return fragments


def _is_body_alias_non_checkup_context(question: str, alias_key: str) -> bool:
    """신체부위 alias가 운동·증상 문맥이면 검진 항목으로 확정하지 않는다."""
    return alias_key in _BODY_PART_ALIASES and bool(_BODY_ALIAS_NON_CHECKUP_CONTEXT.search(question))


def _contains_body_alias_non_checkup_context(question: str, key: str) -> bool:
    """fuzzy 후보 안에 신체부위 alias가 있고 비검진 문맥이면 후보에서 제외한다."""
    return bool(_BODY_ALIAS_NON_CHECKUP_CONTEXT.search(question)) and any(
        alias in key for alias in _BODY_PART_ALIASES
    )


def _question_windows(question: str, max_tokens: int = 3) -> list[tuple[int, int, str, str]]:
    """질문에서 1~3개 토큰을 붙인 compact 후보를 만든다."""
    tokens = list(_TOKEN.finditer(question))
    windows: list[tuple[int, int, str, str]] = []
    for i, start_token in enumerate(tokens):
        for size in range(1, max_tokens + 1):
            end_idx = i + size - 1
            if end_idx >= len(tokens):
                break
            end_token = tokens[end_idx]
            raw = question[start_token.start(): end_token.end()]
            windows.append((
                start_token.start(),
                end_token.end(),
                raw,
                _compact_key(raw),
            ))
    return windows


def _report_compact_terms(report_item_names: set[str]) -> dict[str, str]:
    """최신 검진 결과에 있는 항목의 공식명·동의어만 fuzzy 후보로 둔다."""
    terms = {
        term: canon
        for term, canon in _TERM_CANONS.items()
        if canon in report_item_names
    }
    return _unique_compact_terms(terms)


def _match_korean_item_spans(question: str) -> list[tuple[int, int, str]]:
    """질문 안의 한글 항목명 span을 긴 용어 우선으로 겹치지 않게 선택한다."""
    candidates: list[tuple[int, int, str]] = []
    for term, canon in _KOREAN_TERMS.items():
        for match in re.finditer(re.escape(term), question):
            candidates.append((match.start(), match.end(), canon))

    selected: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, canon in sorted(candidates, key=lambda x: (-(x[1] - x[0]), x[0])):
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        selected.append((start, end, canon))
        occupied.append((start, end))

    return sorted(selected, key=lambda x: x[0])


def _extend_token_item_span(question: str, end: int, canon: str) -> int:
    """영문 약어 뒤에 붙은 한글 카테고리 라벨까지 같은 항목 span으로 본다."""
    category = category_guide.category_of(canon)
    if not category:
        return end

    pos = end
    while pos < len(question) and question[pos].isspace():
        pos += 1

    canonical_key = canon.replace(" ", "").lower()
    for keyword, keyword_category in sorted(_CATEGORY_KEYWORDS.items(), key=lambda x: -len(x[0])):
        keyword_key = keyword.replace(" ", "").lower()
        if (
            keyword_category == category
            and keyword_key in canonical_key
            and question.startswith(keyword, pos)
        ):
            return pos + len(keyword)
    return end


def _match_token_item_spans(question: str) -> list[tuple[int, int, str]]:
    """영문·약어 토큰의 정확 매칭 span을 추출한다."""
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[A-Za-z0-9\-]+", question):
        tok = match.group()
        if len(tok) < 2:
            continue
        canon, score, matched = canonicalize(tok)
        if matched and score == 100 and canon in reference_dict.REFERENCE:
            spans.append((
                match.start(),
                _extend_token_item_span(question, match.end(), canon),
                canon,
            ))
    return spans


def _match_compact_item_spans(question: str) -> list[tuple[int, int, str]]:
    """띄어쓰기·구분자만 다른 항목명을 compact exact로 매칭한다."""
    spans: list[tuple[int, int, str]] = []
    for start, end, _raw, key in _question_windows(question, max_tokens=5):
        for lookup_key in (key, _strip_josa(key)):
            canon = _COMPACT_TERMS.get(lookup_key)
            if canon:
                spans.append((start, end, canon))
                break

    selected: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, canon in sorted(spans, key=lambda x: (-(x[1] - x[0]), x[0])):
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        selected.append((start, end, canon))
        occupied.append((start, end))
    return sorted(selected, key=lambda x: x[0])


def _match_items(question: str) -> list[str]:
    """질문에서 언급된 검진 항목 추출 - exact·compact·한글 substring 매칭 (순서 보존)."""
    found: list[str] = []
    exact_spans = [
        *_match_token_item_spans(question),
        *_match_compact_item_spans(question),
    ]
    # 영문·약어 토큰 - 정확 동의어 매칭만 (fuzzy 미사용, 'ALT가'는 영문/한글 분리로 'ALT' 추출)
    for _, _, canon in sorted(exact_spans, key=lambda x: x[0]):
        if canon not in found:
            found.append(canon)
    # 한글 표기 substring (조사 결합 대응: '혈색소가'에서 '혈색소' 매칭)
    exact_ranges = [(start, end) for start, end, _ in exact_spans]
    for start, end, canon in _match_korean_item_spans(question):
        if _overlaps((start, end), exact_ranges):
            continue
        if canon not in found:
            found.append(canon)
    return found


def _match_report_gated_items(
    question: str,
    report_item_names: set[str],
    known_spans: list[tuple[int, int]] | None = None,
    known_item_names: list[str] | None = None,
) -> tuple[list[str], bool]:
    """최신 결과 항목으로 제한한 alias·typo 매칭. 불확실하면 LLM 답변으로 넘기지 않는다."""
    if not report_item_names:
        report_item_names = set()

    matched: list[str] = [
        name
        for name in (known_item_names or [])
        if name in report_item_names
    ]
    uncertain = False
    windows = _question_windows(question)
    exact_windows = _question_windows(question, max_tokens=5)
    covered_spans: list[tuple[int, int]] = list(known_spans or [])

    for start, end, _raw, key in windows:
        alias_key = _strip_josa(key)
        target = _SHORT_ALIASES.get(alias_key)
        if not target:
            continue
        if _is_body_alias_non_checkup_context(question, alias_key):
            continue
        if target in report_item_names:
            if target not in matched:
                matched.append(target)
            covered_spans.append((start, end))
        elif target not in report_item_names:
            uncertain = True

    report_terms = _report_compact_terms(report_item_names)
    for start, end, _raw, key in exact_windows:
        if _overlaps((start, end), covered_spans):
            continue
        canon = report_terms.get(key)
        if canon:
            if canon not in matched:
                matched.append(canon)
            covered_spans.append((start, end))

    best_by_canon: dict[str, float] = {}
    best_score = 0.0
    for start, end, _raw, key in windows:
        if _overlaps((start, end), covered_spans):
            continue
        if _contains_body_alias_non_checkup_context(question, key):
            continue
        fuzzy_keys = [key]
        stripped_key = _strip_josa(key)
        if stripped_key != key and _has_hangul(stripped_key) and len(stripped_key) >= 3:
            fuzzy_keys.append(stripped_key)

        for compare_key in fuzzy_keys:
            if not compare_key:
                continue
            contains_hangul = _has_hangul(compare_key)
            if contains_hangul and len(compare_key) < 3:
                continue
            if not contains_hangul and len(compare_key) < 6:
                continue
            threshold = 80.0 if contains_hangul else 88.0
            can_match = len(compare_key) >= 4 if contains_hangul else len(compare_key) >= 6
            for candidate_key, canon in report_terms.items():
                score = float(fuzz.ratio(compare_key, candidate_key))
                best_score = max(best_score, score)
                if can_match and score >= threshold:
                    best_by_canon[canon] = max(best_by_canon.get(canon, 0.0), score)

    if best_by_canon:
        if len(best_by_canon) == 1:
            winner = next(iter(best_by_canon))
            if winner not in matched:
                matched.append(winner)
        else:
            uncertain = True
    elif best_score >= 50.0:
        uncertain = True

    known_item_names = known_item_names or []
    category_keys = {_compact_key(keyword) for keyword in _CATEGORY_KEYWORDS}
    item_prefixes = _item_prefix_keys([*matched, *known_item_names])
    category_prefixes = _category_prefix_keys()
    for token in _TOKEN.finditer(question):
        key = _strip_josa(_compact_key(token.group()))
        contains_category = any(category_key and category_key in key for category_key in category_keys)
        fragments = _alias_guard_fragments(key, item_prefixes, category_prefixes)
        if contains_category:
            fragments = [(fragment, after_joiner) for fragment, after_joiner in fragments if after_joiner]
        for fragment, after_joiner in fragments:
            for alias, target in _SHORT_ALIASES.items():
                if target in matched or target in known_item_names:
                    continue
                if not fragment.startswith(alias):
                    continue
                if after_joiner or len(fragment) > len(alias):
                    uncertain = True

    return matched, uncertain


def _overlaps(span: tuple[int, int], blocked_spans: list[tuple[int, int]]) -> bool:
    """두 span이 한 글자라도 겹치면 True."""
    start, end = span
    return any(start < blocked_end and end > blocked_start for blocked_start, blocked_end in blocked_spans)


def _is_height_context_for_keyword(question: str, end: int) -> bool:
    """`신장`이 키/몸길이 의미로 쓰인 바로 뒤 문맥만 제외한다."""
    return bool(_HEIGHT_KEYWORD_CONTEXT.search(question[end:end + 16]))


def _match_category_keywords(
    question: str,
    blocked_spans: list[tuple[int, int]] | None = None,
) -> list[str]:
    """특정 항목명이 아닌 포괄 카테고리 키워드만 추출."""
    return [category for _, _, category in _match_category_keyword_spans(question, blocked_spans)]


def _match_category_keyword_spans(
    question: str,
    blocked_spans: list[tuple[int, int]] | None = None,
) -> list[tuple[int, int, str]]:
    """포괄 카테고리 키워드와 span을 함께 추출한다."""
    blocked_spans = blocked_spans or []
    matches: list[tuple[int, int, str]] = []
    cats: list[str] = []
    for kw, c in _CATEGORY_KEYWORDS.items():
        for match in re.finditer(re.escape(kw), question):
            if kw == "신장" and _is_height_context_for_keyword(question, match.end()):
                continue
            token = next(
                (
                    token_match.group()
                    for token_match in _TOKEN.finditer(question)
                    if token_match.start() <= match.start() and token_match.end() >= match.end()
                ),
                "",
            )
            token_key = _compact_key(token)
            if kw == "체중" and token_key.startswith("체중계"):
                continue
            if _overlaps((match.start(), match.end()), blocked_spans):
                continue
            if c not in cats:
                cats.append(c)
                matches.append((match.start(), match.end(), c))
            break
    return matches


def _merge_categories(item_names: list[str], direct_categories: list[str]) -> list[str]:
    """매칭된 항목의 카테고리 + 직접 카테고리 키워드 (순서 보존·중복 제거)."""
    cats: list[str] = []
    for name in item_names:
        c = category_guide.category_of(name)
        if c and c not in cats:
            cats.append(c)
    for c in direct_categories:
        if c not in cats:
            cats.append(c)
    return cats


def _match_categories(question: str, item_names: list[str]) -> list[str]:
    """매칭된 항목의 카테고리 + 포괄 키워드 카테고리 (순서 보존·중복 제거)"""
    return _merge_categories(item_names, _match_category_keywords(question))


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
                guides_grounding.append({"category": c, "in_report": True, **g})
                if g["source"] not in sources:
                    sources.append(g["source"])
                seen_cats.add(c)

    return {"items": items_grounding, "guides": guides_grounding}, item_names, sources


def _reference_only_names(grounding: dict) -> list[str]:
    """공인 근거는 있으나 최신 검진 결과에는 없는 항목·카테고리 이름."""
    names: list[str] = []
    for item in grounding.get("items", []):
        if not item.get("in_report") and item.get("name") not in names:
            names.append(item["name"])
    for guide in grounding.get("guides", []):
        if not guide.get("in_report") and guide.get("category") not in names:
            names.append(guide["category"])
    return names


def _should_use_report_fallback(question: str) -> bool:
    """특정 항목 없이 최신 결과 요약·진료과 방향을 묻는 질문만 보고서 폴백을 허용한다."""
    return any(trigger in question for trigger in _REPORT_FALLBACK_TRIGGERS)


class ChatRagService:
    """검진 결과 컨텍스트 + 공인 출처 근거 기반 챗봇 답변 (F-007 RAG)"""

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def _retrieve(self, question: str, report, profile):
        """질문 관련 항목·카테고리 근거 수집 - (grounding, 참조항목명, 출처목록, 불확실여부)"""
        item_names = _match_items(question)
        matched_spans = [
            *_match_token_item_spans(question),
            *_match_korean_item_spans(question),
            *_match_compact_item_spans(question),
        ]
        item_spans = [(start, end) for start, end, _ in matched_spans]
        category_matches = _match_category_keyword_spans(question, blocked_spans=item_spans)
        category_spans = [(start, end) for start, end, _ in category_matches]
        direct_categories = [category for _, _, category in category_matches]

        # 내 검진결과에서 해당 항목 값·flag 매핑
        report_items = {it.canonical_name: it for it in (report.items if report else [])}
        report_gated_items, uncertain = _match_report_gated_items(
            question,
            set(report_items),
            known_spans=[*item_spans, *category_spans],
            known_item_names=item_names,
        )
        for name in report_gated_items:
            if name not in item_names:
                item_names.append(name)

        for name in report_items:
            if (
                category_guide.category_of(name) in direct_categories
                and name not in item_names
            ):
                item_names.append(name)

        categories = _merge_categories(item_names, direct_categories)
        report_categories = {
            c
            for c in (category_guide.category_of(name) for name in report_items)
            if c
        }
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
            guides_grounding.append({"category": c, "in_report": c in report_categories, **g})
            if g["source"] not in sources:
                sources.append(g["source"])

        return {"items": items_grounding, "guides": guides_grounding}, item_names, sources, uncertain

    def answer(self, question: str, report=None, profile=None) -> ChatMessage:
        """허용 질문에 근거 기반 답변 생성. 키워드 미매칭 시 보고서 이상·주의 항목으로 폴백."""
        grounding, item_names, sources, uncertain = self._retrieve(question, report, profile)
        fallback_used = False

        if uncertain:
            return ChatMessage(
                role="assistant", content=_ITEM_MATCH_UNCERTAIN, scope_flag=Scope.ALLOWED,
                sources=[], context_item_names=[],
                question_type=QuestionType.UNKNOWN, route_reason="item_match_uncertain",
            )

        if not grounding["items"] and not grounding["guides"]:
            if _should_use_report_fallback(question):
                grounding, item_names, sources = _report_fallback(report, profile)
                fallback_used = bool(grounding["items"] or grounding["guides"])

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

        route_reason = "rag_answer"
        reference_only = _reference_only_names(grounding)
        if fallback_used:
            out = f"{_REPORT_FALLBACK_NOTICE}\n\n{out}"
            route_reason = "report_fallback_answer"
        elif reference_only:
            out = f"{_REFERENCE_ONLY_NOTICE.format(names=', '.join(reference_only))}\n\n{out}"
            route_reason = "reference_only_answer"

        return ChatMessage(
            role="assistant", content=out, scope_flag=Scope.ALLOWED,
            sources=sources, context_item_names=item_names,
            route_reason=route_reason,
        )
