# =============================================================================
# FinPulse Intelligence Platform — Production Dockerfile
# Multi-stage build: compile dependencies in a builder layer, copy only the
# resulting wheels + app code into a slim runtime layer. Runs as non-root.
# =============================================================================

# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed only to compile wheels (not shipped in final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels into /build/wheels instead of installing directly —
# keeps the builder layer's pip cache out of the final image.
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# Metadata
LABEL org.opencontainers.image.title="FinPulse Intelligence Platform"
LABEL org.opencontainers.image.description="Multi-agent financial research API"

# Create a non-root user/group with no shell and no home-dir login
RUN groupadd --gid 1001 finpulse && \
    useradd --uid 1001 --gid finpulse --shell /usr/sbin/nologin --no-create-home finpulse

WORKDIR /app

# Install only the pre-built wheels — no compiler toolchain in this layer
COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels requirements.txt

# Copy application code last (maximises Docker layer cache hits on rebuilds)
COPY finpulse/ ./finpulse/
COPY main.py .

# Drop privileges
RUN chown -R finpulse:finpulse /app
USER finpulse

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FINPULSE_HOST=0.0.0.0 \
    FINPULSE_PORT=7777

EXPOSE 7777

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7777/docs')" || exit 1

CMD ["python", "main.py"]
