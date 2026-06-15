"""OpenAI 임베딩 어댑터 - 텍스트 → 벡터"""

from openai import OpenAI


class OpenAIEmbedder:
    """OpenAI 임베딩 모델 래퍼 (text-embedding-3-small 등)"""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 벡터 반환"""
        resp = self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding
