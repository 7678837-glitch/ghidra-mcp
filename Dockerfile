FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 AS ghidra

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

ARG GHIDRA_URL=https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.2_build/ghidra_12.1.2_PUBLIC_20260605.zip
ARG GHIDRA_SHA256=b62e81a0390618466c019c60d8c2f796ced2509c4c1aea4a37644a77272cf99d

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL --retry 5 --retry-all-errors --retry-max-time 300 \
        "$GHIDRA_URL" -o /tmp/ghidra.zip \
    && echo "$GHIDRA_SHA256  /tmp/ghidra.zip" | sha256sum -c - \
    && unzip -q /tmp/ghidra.zip -d /opt \
    && mv /opt/ghidra_*_PUBLIC /opt/ghidra \
    && rm /tmp/ghidra.zip

FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 AS wheels

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC

WORKDIR /src
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/build-venv
ENV PATH=/opt/build-venv/bin:$PATH
COPY pyproject.toml uv.lock README.md VERSION ./
COPY src ./src
RUN pip install --no-cache-dir uv==0.8.0 \
    && uv export --locked --no-dev --no-emit-project --output-file requirements.txt \
    && uv build --wheel --out-dir /dist \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONUNBUFFERED=1 \
    GHIDRA_INSTALL_DIR=/opt/ghidra \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
    JAVA_HOME_OVERRIDE=/usr/lib/jvm/java-21-openjdk-amd64 \
    GHIDRA_MCP_TRANSPORT=streamable-http \
    GHIDRA_MCP_HOST=0.0.0.0 \
    GHIDRA_MCP_PORT=8765 \
    GHIDRA_MCP_STORAGE_ROOT=/data/projects \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openjdk-21-jre-headless python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 ghidra-mcp \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin ghidra-mcp \
    && python3 -m venv /opt/venv

COPY --from=ghidra /opt/ghidra /opt/ghidra
COPY --from=wheels /wheels /tmp/wheels
COPY --from=wheels /dist /tmp/dist
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels /tmp/dist/*.whl \
    && rm -rf /tmp/wheels /tmp/dist \
    && mkdir -p /data/projects /data/input /app \
    && chown -R ghidra-mcp:ghidra-mcp /data /app

WORKDIR /app
COPY VERSION /app/VERSION

ARG GIT_COMMIT=unknown
ENV GHIDRA_MCP_GIT_COMMIT=$GIT_COMMIT

USER ghidra-mcp
VOLUME ["/data/projects", "/data/input"]
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).read()"]

ENTRYPOINT ["ghidra-mcp"]
