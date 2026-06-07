FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY neurodocops ./neurodocops
COPY packages ./packages
COPY services ./services

RUN pip install --no-cache-dir "setuptools>=69" wheel
RUN pip install --no-cache-dir --no-build-isolation -e .
RUN useradd --create-home --shell /usr/sbin/nologin neurodocops
USER neurodocops

CMD ["python", "-m", "services.worker.neurodocops_worker.main"]
