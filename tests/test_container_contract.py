import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
UV_REQUIREMENTS = "tools/uv-requirements.txt"
UV_HASHED_INSTALL = f"--require-hashes -r {UV_REQUIREMENTS}"


def _publish_jobs() -> tuple[str, str]:
    workflow = (ROOT / ".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    head, jobs = workflow.split("\njobs:\n", 1)
    test_job, publish_job = jobs.split("\n  publish:\n", 1)
    assert "\n  test:\n" in test_job
    return test_job, publish_job


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
    assert "--retries 5 --timeout 60" in dockerfile
    assert "sha256sum -c" in dockerfile
    assert "USER ghidra-mcp" in dockerfile
    assert "JAVA_HOME_OVERRIDE=/usr/lib/jvm/java-21-openjdk-amd64" in dockerfile
    assert "TZ=UTC" in dockerfile
    assert "GHIDRA_MCP_TRANSPORT=streamable-http" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/health" in dockerfile
    assert "VOLUME" in dockerfile and "/data/projects" in dockerfile
    assert "COPY --from=" in dockerfile
    assert "COPY LICENSE NOTICE /app/" in dockerfile
    assert f"COPY {UV_REQUIREMENTS} ./{UV_REQUIREMENTS}" in dockerfile
    assert UV_HASHED_INSTALL in dockerfile
    assert "uv==" not in dockerfile


def test_container_context_excludes_repository_and_local_secrets() -> None:
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".git" in ignored
    assert ".env" in ignored
    assert ".ci-venv" in ignored
    assert ".ci-fixtures" in ignored
    assert "tests/fixtures/generated" in ignored


def test_release_tag_publishes_pinned_linux_amd64_image_to_ghcr() -> None:
    workflow = (ROOT / ".github/workflows/publish-container.yml").read_text(encoding="utf-8")

    assert 'tags: ["v[0-9]*"]' in workflow
    assert "branches:" not in workflow
    assert "pull_request" not in workflow
    assert '"$GITHUB_REF_NAME" != "v$VERSION"' in workflow
    assert "workflow_dispatch" not in workflow
    assert "packages: write" in workflow
    assert "ghcr.io/${{ github.repository }}" in workflow
    assert "platforms: linux/amd64" in workflow
    assert "no-cache: true" in workflow
    assert "push: true" in workflow
    assert "pytest -m 'not integration'" in workflow
    assert "ruff check ." in workflow
    assert "EXPECTED_SCHEMA=" in workflow
    assert "tests/fixtures/src/symbolic.c" in workflow
    assert "tests/integration/test_container_mcp.py" in workflow
    assert "GIT_COMMIT=${{ github.sha }}" in workflow
    assert "VERSION=${{ steps.version.outputs.value }}" in workflow
    assert "${{ env.IMAGE_NAME }}:sha-${{ github.sha }}" in workflow
    assert "Refuse to overwrite a released version" in workflow
    assert "docker manifest inspect" in workflow
    assert "manifest unknown|not found" in workflow
    assert "Could not prove that the version tag is unused" in workflow
    assert "Promote verified digest" in workflow
    assert '"${IMAGE_NAME}:${{ steps.version.outputs.value }}"' in workflow
    assert '"${IMAGE_NAME}:latest"' in workflow
    assert '"${IMAGE_NAME}@${{ steps.image.outputs.digest }}"' in workflow
    assert "provenance: true" in workflow
    assert "sbom: true" in workflow
    assert 'data == {"status": "ok"' in workflow
    assert '"schema_version": sys.argv[3]' in workflow
    assert "if: always()" in workflow
    assert "@11d5960a326750d5838078e36cf38b85af677262" in workflow
    assert "@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f" in workflow
    assert "@c94ce9fb468520275223c153574b00df6fe4bcc9" in workflow
    assert "@10e90e3645eae34f1e60eeb005ba3a3d33f178e8" in workflow


def test_pull_request_ci_runs_tests_and_lint_without_secrets() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "pull_request_target" not in workflow
    assert "branches: [main]" in workflow
    assert "contents: read" in workflow
    assert "write" not in workflow
    assert "secrets." not in workflow
    assert "persist-credentials: false" in workflow
    assert '["3.11", "3.12", "3.13"]' in workflow
    assert UV_HASHED_INSTALL in workflow
    assert "uv==" not in workflow
    assert "uv sync --locked --extra dev" in workflow
    assert "pytest -m 'not integration'" in workflow
    assert "ruff check ." in workflow
    assert "@11d5960a326750d5838078e36cf38b85af677262" in workflow


def test_uv_is_pinned_by_version_and_hash() -> None:
    lines = (ROOT / UV_REQUIREMENTS).read_text(encoding="utf-8").splitlines()
    entries = [line for line in lines if line and not line.startswith("#")]

    match = re.fullmatch(r"uv==(\d+)\.(\d+)\.(\d+) \\", entries[0])
    assert match is not None
    # 0.13.1 is the pinned release; older 0.12.x/0.11.x releases carry advisories.
    assert tuple(int(part) for part in match.groups()) >= (0, 13, 1)
    hashes = entries[1:]
    assert len(hashes) >= 2
    for index, line in enumerate(hashes):
        suffix = "" if index == len(hashes) - 1 else " \\"
        assert re.fullmatch(r"    --hash=sha256:[0-9a-f]{64}" + re.escape(suffix), line), line
    assert len(set(hashes)) == len(hashes)


def test_publish_workflow_is_serialized_and_gated_before_registry_login() -> None:
    workflow = (ROOT / ".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    test_job, publish_job = _publish_jobs()

    assert "concurrency:\n  group: publish-container\n  cancel-in-progress: false\n" in workflow
    assert "\npermissions: {}\n" in workflow
    assert workflow.count("persist-credentials: false") == workflow.count("actions/checkout@")

    assert "fetch-depth: 0" in test_job
    assert '"$GITHUB_REF_NAME" != "v$VERSION"' in test_job
    assert 'git merge-base --is-ancestor "$GITHUB_SHA" refs/remotes/origin/main' in test_job
    assert test_job.index("git merge-base --is-ancestor") < test_job.index(UV_HASHED_INSTALL)
    assert "Log in to GHCR" not in test_job
    assert "secrets." not in test_job
    assert "packages:" not in test_job
    assert "    permissions:\n      contents: read\n    outputs:" in test_job
    assert "pytest -m 'not integration'" in test_job
    assert "ruff check ." in test_job
    assert "tests/integration/test_container_mcp.py" in test_job
    assert "if: always()" in test_job

    assert "    needs: test\n" in publish_job
    assert "      contents: read\n      packages: write\n" in publish_job
    assert "Log in to GHCR" in publish_job
    assert "needs.test.outputs.version" in publish_job
    # Step-level checks (no third-party code, version check placement and
    # behavior) live in tests/test_publish_workflow_behavior.py.
