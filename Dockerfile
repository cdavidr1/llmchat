FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV LLMCHAT_CONFIG_DIR=/vault/secrets
ENV SECRET_FILE=/vault/secrets/oracle.json

COPY pyproject.toml README.md ./
COPY app ./app
COPY config.example ./config.example

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
