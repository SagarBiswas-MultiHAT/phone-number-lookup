# file: Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user
RUN useradd -m -u 10001 phoneint

WORKDIR /home/phoneint/app

COPY pyproject.toml README.md LICENSE requirements.txt ./
COPY phoneint ./phoneint

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir .

USER phoneint

# Default cache path for containers (writable)
ENV PHONEINT_CACHE_PATH=/home/phoneint/.cache/phoneint.sqlite3

ENTRYPOINT ["phoneint"]
CMD ["--help"]

