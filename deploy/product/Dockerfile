FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8000

# 使用 uv 安装依赖
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md /app/
RUN uv sync --system --no-dev

COPY app /app/app
COPY main.py /app/main.py

EXPOSE 8000

CMD ["sh", "-c", "uv run main.py"]
