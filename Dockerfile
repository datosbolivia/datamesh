# ==============================================================================
# Stage 1: Build Native Go Core Authority & C-Shared Library
# ==============================================================================
FROM golang:1.22-bookworm AS go-builder

WORKDIR /build

# Install CGO compilation dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY core-go/go.mod core-go/go.sum* ./core-go/
RUN cd core-go && go mod download || true

COPY core-go ./core-go

# 1. Build C-Shared Library for C-ABI Authority
RUN cd core-go && \
    CGO_ENABLED=1 go build -buildmode=c-shared -o libdatamesh.so ./adapters/inbound/cshared/exports.go

# 2. Build Native Static Go CLI
RUN cd core-go && \
    CGO_ENABLED=1 go build -ldflags="-s -w" -o datamesh-go ./adapters/inbound/cli

# ==============================================================================
# Stage 2: Python Runtime, DuckDB Analytical Engine & Sovereign Server
# ==============================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATAMESH_LIB_PATH=/usr/local/lib/libdatamesh.so \
    LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled native shared library and binary from Stage 1
COPY --from=go-builder /build/core-go/libdatamesh.so /usr/local/lib/libdatamesh.so
COPY --from=go-builder /build/core-go/datamesh-go /usr/local/bin/datamesh-go
RUN ldconfig

# Install Python SDK
COPY bindings/python /app/bindings/python
COPY specificacion_knowledge.md README.md LICENSE /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /app/bindings/python

# Create unprivileged application user
RUN useradd -m -u 1000 datamesh && \
    mkdir -p /home/datamesh/.datamesh/cache && \
    chown -R datamesh:datamesh /home/datamesh

USER datamesh
WORKDIR /home/datamesh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["datamesh", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
