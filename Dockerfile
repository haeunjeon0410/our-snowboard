# 공개 서버용 (Hugging Face Spaces 'Docker' 또는 Render/Fly 같은 곳). 내 컴퓨터에서 쓸 때는 필요 없음.
FROM python:3.12-slim

# PDF 결과물에 쓸 한글 글꼴(나눔고딕, OFL)
RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY --chown=user . /app
RUN mkdir -p /app/output /app/server/.cache/llm && chown -R user /app/output /app/server/.cache
USER user

# 공개 서버 설정. 키와 접속 코드는 여기에 쓰지 말고 호스팅 서비스의 Secrets 에 넣는다.
#   GATEWAY_API_KEY, ACCESS_CODE (Secrets)  /  PUBLIC_URL (Variable, 예: https://아이디-our-snowboard.hf.space)
ENV PORT=7860 \
    DATA_TTL_HOURS=6 \
    DAILY_AI_LIMIT=300 \
    PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["sh", "-c", "uvicorn server.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
