"""환경 변수 로딩 - 설정 값객체"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# .env 로딩
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """런타임 설정"""

    openai_api_key: str
    parse_model: str  # 파싱용 OpenAI 모델
    interpret_model: str  # 해석용 OpenAI 모델
    render_dpi: int


def load_settings() -> Settings:
    """환경 변수에서 설정 로딩 - 키 누락 시 빈 문자열 (UI 에서 검증)"""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        parse_model=os.getenv("PARSE_MODEL", "gpt-4o-mini"),
        interpret_model=os.getenv("INTERPRET_MODEL", "gpt-4o-mini"),
        render_dpi=int(os.getenv("RENDER_DPI", "150")),
    )
