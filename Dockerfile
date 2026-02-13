FROM ghcr.io/astral-sh/uv:python3.12-slim

WORKDIR /app

COPY pyproject.toml ./

RUN uv sync --no-dev

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "main.py"]

