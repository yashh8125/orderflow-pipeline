FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY orderflow ./orderflow

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && mkdir -p data reports && chown -R appuser /app
USER appuser

CMD ["python", "-m", "orderflow.pipeline", "--generate"]
