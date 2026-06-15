"""OpenAI 어댑터 - LLMPort 구현"""

from openai import OpenAI

from gogodoc.application.ports import LLMTask
from gogodoc.infrastructure.config import Settings


_TASK_PARAMS = {
    LLMTask.PARSE: {"temperature": 0.0, "max_tokens": 2048},
    LLMTask.INTERPRET: {"temperature": 0.3, "max_tokens": 1024},
}


class OpenAILLM:
    """OpenAI 기반 LLMPort 구현"""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._models = {
            LLMTask.PARSE: settings.parse_model,
            LLMTask.INTERPRET: settings.interpret_model,
        }

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        """단일 턴 호출 - 응답 텍스트 반환"""
        params = _TASK_PARAMS[task]
        response = self._client.chat.completions.create(
            model=self._models[task],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""
