# Build from the REPO ROOT context: docker build -f runner/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
RUN uv pip install --system \
    "fastapi>=0.115,<1" "uvicorn[standard]>=0.32,<1" "docker>=7.1,<8"
COPY runner/airlock_runner ./airlock_runner
ENV PYTHONPATH=/app
EXPOSE 8700
CMD ["uvicorn", "airlock_runner.main:app", "--host", "0.0.0.0", "--port", "8700"]
