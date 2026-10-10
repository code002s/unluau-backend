FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 https://github.com/atrexus/unluau.git /src/unluau
# The repository has a CLI project; resolve it dynamically so the service tracks the repo layout.
RUN CLI=$(find /src/unluau -name '*.csproj' -print | grep -E 'CLI|Cli' | head -1) && test -n "$CLI" && dotnet publish "$CLI" -c Release -o /opt/unluau

FROM mcr.microsoft.com/dotnet/runtime:8.0-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/unluau /opt/unluau
COPY server.py /app/server.py
ENV UNLUAU_BIN=/opt/unluau/Unluau.CLI
ENV HOST=0.0.0.0 PORT=8788
EXPOSE 8788
CMD ["python3", "/app/server.py"]
