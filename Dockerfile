# Stage 1: build the patched unluac-rs CLI (Luau bytecode v3-v14).
FROM rust:1-bookworm AS build
WORKDIR /src
COPY unluac-rs/ ./unluac-rs/
WORKDIR /src/unluac-rs
RUN cargo build --release -p unluac-cli \
    && cp target/release/unluac-cli /usr/local/bin/unluac-cli

# Stage 2: tiny runtime with the HTTP front end.
FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/unluac-cli /usr/local/bin/unluac-cli
WORKDIR /app
COPY server.py luau_descramble.py ./
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "/app/server.py"]
