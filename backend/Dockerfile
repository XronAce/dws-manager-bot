FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so a code-only change reuses this layer.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations

# Never run as root: the container needs no privileges beyond outbound HTTPS.
RUN useradd --create-home --uid 10001 dws && chown -R dws:dws /app
USER dws

EXPOSE 8000

# Migrations run at start-up. Safe because the deployment is pinned to a single
# replica, so two pods can never race on the same Alembic upgrade.
CMD ["sh", "-c", "alembic upgrade head && python -m dwsbot.main"]
