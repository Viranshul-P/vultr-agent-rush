# Airlock code sandbox image.
# Runs model-written Python under gVisor with no network, no env vars,
# a read-only root filesystem and a non-root user (see runner flags).
FROM python:3.12-slim

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY airlock_checks /opt/airlock_checks
ENV PYTHONPATH=/opt \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp

# Precompile so the read-only rootfs never needs .pyc writes.
RUN python -m compileall -q /opt/airlock_checks /usr/local/lib/python3.12

USER 65534:65534
WORKDIR /tmp
CMD ["python", "-c", "print('airlock py-sandbox ready')"]
