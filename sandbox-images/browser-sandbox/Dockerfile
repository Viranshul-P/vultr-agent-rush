# Airlock browser sandbox: Playwright + Chromium, run under gVisor on an
# internal-only Docker network whose only exit is the egress proxy.
# Pin the tag to the current Playwright release at kickoff (keep python pkg == image version).
ARG PLAYWRIGHT_VERSION=1.48.0
FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-noble
ARG PLAYWRIGHT_VERSION
RUN pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}"

COPY harness.py /opt/harness.py
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER pwuser
WORKDIR /tmp
CMD ["python", "/opt/harness.py", "--help"]
