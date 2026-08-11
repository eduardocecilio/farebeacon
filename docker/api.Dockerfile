FROM python:3.12.13-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml requirements-build.lock requirements.lock README.md LICENSE ./
RUN python -m pip install --require-hashes --requirement requirements-build.lock
RUN python -m pip wheel --require-hashes --wheel-dir /wheels --requirement requirements.lock \
    && python -m pip check
COPY src ./src
RUN python -m pip wheel --no-build-isolation --no-deps --wheel-dir /wheels .

FROM python:3.12.13-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/farebeacon/.local/bin:$PATH

RUN addgroup -S -g 10001 farebeacon \
    && adduser -S -D -u 10001 -G farebeacon -h /home/farebeacon farebeacon \
    && mkdir -p /var/lib/farebeacon/artifacts \
    && chown -R farebeacon:farebeacon /var/lib/farebeacon

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels farebeacon \
    && python -m pip uninstall --yes pip setuptools wheel \
    && rm -rf /wheels

WORKDIR /app
COPY --chown=farebeacon:farebeacon alembic.ini ./
COPY --chown=farebeacon:farebeacon migrations ./migrations

USER farebeacon
EXPOSE 8000

CMD ["uvicorn", "farebeacon.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS test
USER root
ENV RUFF_CACHE_DIR=/home/farebeacon/.cache/ruff
ENV FAREBEACON_ENV=test
COPY --chown=farebeacon:farebeacon pyproject.toml requirements-build.lock requirements-dev.lock README.md LICENSE ./
COPY --chown=farebeacon:farebeacon src ./src
COPY --chown=farebeacon:farebeacon tests ./tests
RUN python -m ensurepip --upgrade \
    && python -m pip install --require-hashes --requirement requirements-build.lock \
    && python -m pip install --require-hashes --requirement requirements-dev.lock \
    && python -m pip check \
    && python -m pip uninstall --yes pip setuptools wheel \
    && mkdir -p /app/.test \
    && chown farebeacon:farebeacon /app/.test
USER farebeacon
CMD ["pytest"]
