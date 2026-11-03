# Build from the REPO ROOT context: docker build -f api/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
RUN uv pip install --system \
    "fastapi>=0.115,<1" "uvicorn[standard]>=0.32,<1" "sqlmodel>=0.0.22,<0.1" \
    "psycopg[binary]>=3.2,<4" "httpx>=0.27,<1" "openai>=1.54,<3" "sse-starlette>=2.1,<3" \
    "cryptography>=43" "boto3>=1.35,<2" "python-multipart>=0.0.12" "reportlab>=4.2,<5" "rapidfuzz>=3.10,<4" \
    "pdfplumber>=0.11,<0.12" "pypdf>=5,<6"
COPY api/airlock_api ./airlock_api
COPY sandbox-images/py-sandbox/airlock_checks ./airlock_checks
COPY seed ./seed
ENV PYTHONPATH=/app AIRLOCK_SEED_DIR=/app/seed
EXPOSE 8000
CMD ["uvicorn", "airlock_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
