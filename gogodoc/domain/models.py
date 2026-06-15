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


class FinalReport(BaseModel):
    """단계 4 출력 - 안전 가드레일 적용 최종 결과"""

    items: list[InterpretedItem] = Field(default_factory=list)
    tracking_items: list[str] = Field(default_factory=list)  # 추적 권장 항목
    emergency_alerts: list[str] = Field(default_factory=list)  # 즉시 내원 안내
    disclaimer: str = ""  # 면책 문구
    notes: list[str] = Field(default_factory=list)  # 비치명적 처리 이슈 (부분 실패 등)
