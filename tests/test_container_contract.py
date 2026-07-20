from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_container_is_pinned_multi_stage_non_root_and_health_checked() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("FROM ") >= 3
    assert dockerfile.count("FROM ubuntu:24.04@sha256:") == 3
    assert dockerfile.count("DEBIAN_FRONTEND=noninteractive") == 3
    assert "python3 -m venv /opt/build-venv" in dockerfile
    assert "apt-get install -y --no-install-recommends" in dockerfile and "python3" in dockerfile
    assert "GHIDRA_SHA256=" in dockerfile
    assert "--retry 5 --retry-all-errors --retry-max-time 300" in dockerfile
    assert "--continue-at -" in dockerfile
    assert "sha256sum -c" in dockerfile
    assert "USER ghidra-mcp" in dockerfile
    assert "JAVA_HOME_OVERRIDE=/usr/lib/jvm/java-21-openjdk-amd64" in dockerfile
    assert "TZ=UTC" in dockerfile
    assert "GHIDRA_MCP_TRANSPORT=streamable-http" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/health" in dockerfile
    assert "VOLUME" in dockerfile and "/data/projects" in dockerfile
    assert "COPY --from=" in dockerfile


def test_container_context_excludes_repository_and_local_secrets() -> None:
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".git" in ignored
    assert ".env" in ignored
    assert "tests/fixtures/generated" in ignored
