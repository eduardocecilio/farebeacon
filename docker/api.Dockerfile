FROM python:3.12.7-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12.7-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/farebeacon/.local/bin:$PATH

RUN groupadd --gid 10001 farebeacon \
    && useradd --uid 10001 --gid farebeacon --create-home farebeacon \
    && mkdir -p /var/lib/farebeacon/artifacts \
    && chown -R farebeacon:farebeacon /var/lib/farebeacon

COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/* && rm -rf /wheels

WORKDIR /app
COPY --chown=farebeacon:farebeacon alembic.ini ./
COPY --chown=farebeacon:farebeacon migrations ./migrations

USER farebeacon
EXPOSE 8000

CMD ["uvicorn", "farebeacon.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
ENV RUFF_CACHE_DIR=/home/farebeacon/.cache/ruff
COPY --chown=farebeacon:farebeacon pyproject.toml README.md LICENSE ./
COPY --chown=farebeacon:farebeacon src ./src
COPY --chown=farebeacon:farebeacon tests ./tests
RUN python -m pip install ".[dev]" \
    && mkdir -p /app/.test \
    && chown farebeacon:farebeacon /app/.test
USER farebeacon
CMD ["pytest"]
