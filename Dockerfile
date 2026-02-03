# -------------------------------------------------------------
#  Multi-stage build - thin runtime image
# -------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml poetry.lock requirements.txt ./
RUN pip install --upgrade pip \
    && pip install poetry \
    && poetry export -f requirements.txt --output reqs.txt --without-hashes \
    && pip install -r reqs.txt \
    && rm -rf /root/.cache

COPY . .

# -------------------------------------------------------------
#  Runtime image
# -------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
