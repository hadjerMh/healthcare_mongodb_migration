FROM python:3.12-slim-bookworm

COPY --from=docker.io/astral/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml ./

RUN uv sync --no-dev

COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "main.py"]

