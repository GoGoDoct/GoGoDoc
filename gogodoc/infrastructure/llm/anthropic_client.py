"""Anthropic 어댑터 - LLMPort 구현

용도(LLMTask)별 모델·temperature 매핑을 어댑터가 캡슐화
파싱은 Haiku(저비용), 해석은 Sonnet(품질)
"""

from anthropic import Anthropic

from gogodoc.application.ports import LLMTask
from gogodoc.infrastructure.config import Settings

# 용도별 temperature·max_tokens
_TASK_PARAMS = {
    LLMTask.PARSE: {"temperature": 0.0, "max_tokens": 2048},  # 파싱 안정성
    LLMTask.INTERPRET: {"temperature": 0.3, "max_tokens": 1024},  # 신뢰성·자연스러움 균형
}


class AnthropicLLM:
    """Anthropic 기반 LLMPort 구현"""

    def __init__(self, settings: Settings) -> None:
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        # 용도별 모델 매핑
        self._models = {
            LLMTask.PARSE: settings.parse_model,
            LLMTask.INTERPRET: settings.interpret_model,
        }

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        """단일 턴 호출 - 응답 텍스트 반환"""
        params = _TASK_PARAMS[task]
        resp = self._client.messages.create(
            model=self._models[task],
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # 텍스트 블록 연결
        return "".join(block.text for block in resp.content if block.type == "text")
