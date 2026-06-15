"""파이프라인 오류 타입 - 단계 실패 표준화"""


class PipelineError(Exception):
    """파이프라인 처리 오류 기반 클래스"""


class ParseError(PipelineError):
    """파싱·구조화 실패 - 복구 불가, 사용자 안내 대상"""
