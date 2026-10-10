# Stage 1: build the patched unluac-rs CLI (Luau bytecode v3-v14).
FROM rust:1-bookworm AS build
WORKDIR /src
COPY unluac-rs/ ./unluac-rs/
WORKDIR /src/unluac-rs
RUN cargo build --release -p unluac-cli \
    && cp target/release/unluac-cli /usr/local/bin/unluac-cli

# Stage 2: tiny runtime with the HTTP front end (standard library only).
FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --no-create-home --shell /usr/sbin/nologin unluau
COPY --from=build /usr/local/bin/unluac-cli /usr/local/bin/unluac-cli
WORKDIR /app
COPY server.py ./
COPY unluau/ ./unluau/
USER unluau
ENV PORT=8080 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python3 -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=4)"
CMD ["python3", "/app/server.py"]
