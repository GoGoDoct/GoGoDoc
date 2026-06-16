"""애플리케이션 포트 - 외부 어댑터 인터페이스 (Protocol)

도메인·애플리케이션은 이 추상에만 의존, 구체 구현은 infrastructure 에서 주입
"""

from enum import Enum
from typing import Protocol, runtime_checkable


class LLMTask(str, Enum):
    """LLM 호출 용도 - 어댑터가 용도별 모델·temperature 선택"""

    PARSE = "parse"  # 파싱 텍스트 JSON 구조화
    INTERPRET = "interpret"  # 항목 해석 생성
    RECOMMEND = "recommend"  # 진료과목 추천 (F-006)
    CLASSIFY = "classify"  # 챗봇 질문 스코프 분류 (F-007)
    JUDGE = "judge"  # 생성 답변 근거성·환각 심판 (평가 - 결정적)


@runtime_checkable
class LLMPort(Protocol):
    """LLM 호출 포트"""

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        """단일 턴 호출 - 응답 텍스트 반환"""
        ...


@runtime_checkable
class PdfParserPort(Protocol):
    """PDF 텍스트·표 추출 포트"""

    def extract_text(self, pdf_path: str) -> str:
        """표 추출 우선, 실패 시 텍스트 폴백"""
        ...


@runtime_checkable
class RendererPort(Protocol):
    """PDF 렌더링 포트 - split 뷰 원본 표시용"""

    def render_pages(self, pdf_path: str) -> list:
        """페이지를 이미지 목록으로 변환"""
        ...


@runtime_checkable
class ReferenceRetrieverPort(Protocol):
    """해설 근거 검색 포트 - dict 조회 또는 벡터 유사도 검색"""

    def retrieve(self, canonical_name: str) -> dict | None:
        """표준 항목명에 해당하는 해설 근거 엔트리 반환 (없으면 None)"""
        ...
