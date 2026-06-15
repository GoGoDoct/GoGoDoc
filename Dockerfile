# 베이스 이미지 - 의존성 wheel 호환 위해 3.12
FROM python:3.12-slim

# poppler - pdf2image 렌더링 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 레이어 캐시 - requirements 먼저 복사
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드
COPY . .

# 비루트 사용자 실행 - 보안 기본
RUN useradd -m appuser
USER appuser

EXPOSE 8501

# 헬스체크 - 스트림릿 상태 엔드포인트 (curl 미설치, urllib 사용)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# 컨테이너 외부 접근 위해 0.0.0.0 바인딩
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
