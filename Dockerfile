FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \ 
    UV_COMPILE_BYTECODE=0

WORKDIR /app/project

COPY requirements.txt /tmp/requirements.txt
RUN uv pip install -r /tmp/requirements.txt

COPY . /app
