# The collector runner: every enabled screen's collector, each on its own interval.
# .dockerignore is an allowlist, so tests, fixtures and recordings never reach the image.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv

# tzdata makes TZ work: the collector reads "now" and "today" in local time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --no-create-home collector \
    && mkdir /state && chown collector /state

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/venv/bin:$PATH \
    STATE_DIR=/state \
    TZ=Etc/UTC

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-cache

# Run from source, not as an installed package: discovery finds screens/ next to collector/.
COPY collector collector
COPY screens screens
COPY scripts/deploy scripts/deploy

USER collector
VOLUME /state
CMD ["python", "-m", "collector"]
