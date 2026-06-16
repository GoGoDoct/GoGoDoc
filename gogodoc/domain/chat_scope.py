"""F-007 챗봇 질문 스코프 판정 - 허용/비허용 규칙 (순수 도메인)

허용: 검진 수치 설명, 일반 생활습관, 진료과 안내
비허용: 진단 단정, 처방·복약, 수술 등 의료행위 -> 전문의 상담 라우팅

안전 원칙 (의료법 리스크 차단)
- 규칙은 고정밀 하드 차단 - 명백한 진단·처방·복약만 BLOCKED 로 단정
- 애매한 질문은 None 반환 -> 상위(LLM 분류)에 위임, 거기서 모호하면 비허용(보수적)
- 목표: 위험질문 통과율 0 (false negative 최소화)
"""

import re

from gogodoc.domain.models import Scope

# 비허용 하드 차단 패턴 - 매칭 시 즉시 BLOCKED
_BLOCK_PATTERNS = [
    # 처방·복약 (약 + 행위/용량)
    re.compile(r"무슨\s*약|어떤\s*약|약\s*(을|를|은|이|좀)?\s*(먹|복용|드시|바꾸|바꿔|끊|줄여|늘려)"),
    re.compile(r"처방|복용|투약|용량|몇\s*(알|정|mg|밀리그램)|증량|감량"),
    # 진단 단정 요청 (질환명 + 단정형 물음)
    re.compile(
        r"(암|종양|간암|위암|대장암|간경화|당뇨병|고혈압|갑상선암|신부전)\s*"
        r"(이에요|이예요|인가요|입니까|맞나요|인지|일까요|이라는|진단)"
    ),
    re.compile(r"무슨\s*병|병명|진단(해|받|명|을|이)|확진"),
    # 수술·시술 등 의료행위
    re.compile(r"수술|시술|항암|입원|주사\s*(맞|놓)"),
]

# 전문의 상담 라우팅 안내 (비허용 질문 응답)
ROUTING_MESSAGE = (
    "이 질문은 진단·처방·복약에 해당할 수 있어 정확한 답변을 드리기 어렵습니다. "
    "정확한 판단은 전문의와 상담하시길 권장합니다."
)


def classify_rule(question: str) -> Scope | None:
    """규칙 기반 하드 차단 - 명백한 비허용이면 BLOCKED, 아니면 None(LLM 위임)"""
    text = (question or "").strip()
    if not text:
        return Scope.BLOCKED  # 빈 질문은 보수적으로 차단
    for pattern in _BLOCK_PATTERNS:
        if pattern.search(text):
            return Scope.BLOCKED
    return None
