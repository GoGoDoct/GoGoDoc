"""도메인 모델 - 엔티티 및 값객체 (Pydantic v2)"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Sex(str, Enum):
    """성별 - 정상범위 판정 기준"""

    MALE = "male"
    FEMALE = "female"


class Flag(str, Enum):
    """항목별 상태 플래그"""

    NORMAL = "normal"  # 정상
    CAUTION = "caution"  # 주의
    ABNORMAL = "abnormal"  # 이상
    EMERGENCY = "emergency"  # 응급 이상치 (패닉 밸류)
    CHECK_NEEDED = "check_needed"  # 확인필요 (수치 인식 불가)
    UNKNOWN = "unknown"  # 알수없음 (해설 기준 없음)


class UserProfile(BaseModel):
    """단계 0 - 사용자 기본 정보"""

    sex: Sex
    age: int = Field(ge=0, le=120)


class LabItem(BaseModel):
    """단계 1 - PDF에서 추출한 원시 검사 항목"""

    name: str  # 결과지 표기 항목명
    value: Optional[float] = None  # 측정값
    unit: Optional[str] = None  # 단위
    reference_range: Optional[str] = None  # 결과지 표기 참조범위 (원문)


class ParsedReport(BaseModel):
    """단계 1 출력 - 구조화된 검사 항목 목록"""

    items: list[LabItem] = Field(default_factory=list)


class MatchedItem(BaseModel):
    """단계 2 출력 - 정규화 및 정상범위 매칭 결과"""

    canonical_name: str  # 표준 항목명
    raw_name: str  # 원본 항목명
    value: Optional[float] = None
    unit: Optional[str] = None
    flag: Flag = Flag.UNKNOWN
    matched: bool = False  # 해설 dict 매칭 여부
    match_score: float = 0.0  # rapidfuzz 점수 (fallback 시)


class InterpretedItem(MatchedItem):
    """단계 3 출력 - 항목별 쉬운 해설"""

    explanation: str = ""  # 근거 인용 기반 해설
    source: Optional[str] = None  # 인용 출처


class GuideNote(BaseModel):
    """카테고리별 생활 가이드 - 근거 기반 관리법·추적·진료과 (CATEGORY_GUIDE 출처)"""

    category: str  # 간기능·혈당·지질 등
    lifestyle: str  # 생활수칙
    tracking: str  # 추적 권장
    department: str  # 권장 진료과 (F-006 매핑)
    source: str  # 출처


class Scope(str, Enum):
    """F-007 챗봇 질문 스코프 - 허용/비허용"""

    ALLOWED = "allowed"  # 허용 (수치 설명·생활습관·진료과 안내)
    BLOCKED = "blocked"  # 비허용 (진단·처방·복약 - 전문의 상담 라우팅)


class ScopeDecision(BaseModel):
    """F-007 질문분류 결과 - 스코프 판정 및 라우팅 여부"""

    scope: Scope
    routed: bool  # 전문의 상담으로 라우팅되었는지
    reason: str = ""  # 판정 근거 (rule | llm | llm_error)


class ChatMessage(BaseModel):
    """F-007 챗봇 메시지 (기능명세서 4.4 스키마)"""

    role: str  # user | assistant
    content: str
    scope_flag: Optional[Scope] = None  # 허용/비허용 (user 질문 판정)
    routed: bool = False  # 전문의 상담 라우팅 여부
    sources: list[str] = Field(default_factory=list)  # 답변 근거 출처
    context_item_names: list[str] = Field(default_factory=list)  # 참조한 검진 항목


class FinalReport(BaseModel):
    """단계 4 출력 - 안전 가드레일 적용 최종 결과"""

    items: list[InterpretedItem] = Field(default_factory=list)
    tracking_items: list[str] = Field(default_factory=list)  # 추적 권장 항목
    emergency_alerts: list[str] = Field(default_factory=list)  # 즉시 내원 안내
    summary: str = ""  # 직장인용 종합 요약 (근거 기반 LLM 생성)
    lifestyle_guide: list[GuideNote] = Field(default_factory=list)  # 카테고리별 생활 가이드 (결정적)
    disclaimer: str = ""  # 면책 문구
    notes: list[str] = Field(default_factory=list)  # 비치명적 처리 이슈 (부분 실패 등)
