"""Behavior tests for the release workflow scripts.

The scripts are extracted verbatim from ``.github/workflows/publish-container.yml``
and executed locally: the version check runs against a fake OCI registry, the
re-read step runs with bash the way GitHub Actions does.
"""

import ast
import json
import os
import re
import subprocess
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/publish-container.yml"
REPOSITORY = "xjoker/ghidra-mcp"
TAGS_PATH = f"/v2/{REPOSITORY}/tags/list"
FIRST_PAGE = f"{TAGS_PATH}?n=1000"
VERSION_CHECK = "Require a version newer than every published version"
ALLOWED_PUBLISH_ACTIONS = {
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
    "docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f",
    "docker/login-action@c94ce9fb468520275223c153574b00df6fe4bcc9",
    "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
}
THIRD_PARTY_RUNNERS = re.compile(
    r"\b(pipx|pip3?|uvx?|pytest|ruff|npx|npm|yarn|pnpm|node|deno|bun|poetry|pdm|hatch"
    r"|tox|nox|conda|mamba|gem|bundle|cargo|go|make)\b|\.ci-venv|python3?\s+(?!-c\b)"
)


@dataclass
class Step:
    name: str
    text: str
    run: str | None
    uses: str | None
    shell: str | None


def _jobs() -> dict[str, list[Step]]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs_text = workflow.split("\njobs:\n", 1)[1]
    jobs: dict[str, list[Step]] = {}
    for job_match in re.finditer(
        r"^  ([a-z][a-z0-9_-]*):\n(.*?)(?=^  [a-z]|\Z)", jobs_text, re.M | re.S
    ):
        steps_text = job_match.group(2).split("    steps:\n", 1)[1]
        chunks = re.split(r"^      - ", steps_text, flags=re.M)[1:]
        jobs[job_match.group(1)] = [_parse_step("        " + chunk) for chunk in chunks]
    return jobs


def _parse_step(text: str) -> Step:
    lines = text.splitlines()
    values: dict[str, str] = {}
    run: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^        ([a-z-]+): ?(.*)$", line)
        if match and match.group(1) == "run" and match.group(2) == "|":
            body = []
            index += 1
            while index < len(lines) and (
                not lines[index].strip() or lines[index].startswith(" " * 10)
            ):
                body.append(lines[index][10:])
                index += 1
            run = "\n".join(body).rstrip("\n") + "\n"
            continue
        if match:
            values[match.group(1)] = match.group(2)
            if match.group(1) == "run":
                run = match.group(2) + "\n"
        index += 1
    return Step(values["name"], text, run, values.get("uses"), values.get("shell"))


def _step(job: str, name: str) -> Step:
    matches = [step for step in _jobs()[job] if step.name == name]
    assert len(matches) == 1, name
    return matches[0]


def _commands(script: str) -> list[str]:
    return [
        line.strip()
        for line in script.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


@dataclass
class Registry:
    pages: dict[str, tuple[int, object, str | None]] = field(default_factory=dict)
    token_status: int = 200
    token_body: object = field(default_factory=lambda: {"token": "fake-token"})
    requests: list[str] = field(default_factory=list)
    url: str = ""

    def page(
        self, path: str, tags: object, next_link: str | None = None, status: int = 200
    ) -> None:
        body = (
            tags if isinstance(tags, dict) or status != 200 else {"name": REPOSITORY, "tags": tags}
        )
        self.pages[path] = (status, body, next_link)


@pytest.fixture
def registry() -> Iterator[Registry]:
    state = Registry()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def _send(self, status: int, body: object, link: str | None = None) -> None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if link is not None:
                self.send_header("Link", f'<{link}>; rel="next"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            state.requests.append(self.path)
            if self.path.startswith("/token?"):
                assert self.path == f"/token?service=ghcr.io&scope=repository:{REPOSITORY}:pull"
                self._send(state.token_status, state.token_body)
                return
            assert self.headers["Authorization"] == "Bearer fake-token"
            if self.path not in state.pages:
                self._send(404, {"errors": [{"code": "NAME_UNKNOWN"}]})
                return
            self._send(*state.pages[self.path])

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def _version_check(
    registry: Registry, version: str, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    step = _step("publish", VERSION_CHECK)
    assert step.shell == "python3 {0}" and step.run is not None
    script = tmp_path / "version_check.py"
    script.write_text(step.run, encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "VERSION": version,
        "REGISTRY_URL": registry.url,
        "IMAGE_NAME": f"ghcr.io/{REPOSITORY}",
    }
    return subprocess.run(
        [sys.executable, str(script)], env=env, capture_output=True, text=True, timeout=60
    )


def _passes(result: subprocess.CompletedProcess[str]) -> bool:
    if result.returncode == 0:
        assert "is newer than published version" in result.stdout
        return True
    assert "Version check failed:" in result.stderr, result.stderr
    return False


@pytest.mark.parametrize(
    ("published", "candidate", "accepted"),
    [
        (["20261019.1", "latest", "sha-abc"], "20261019.2", True),
        (["20261019.1"], "20261020.1", True),
        (["20261019.1"], "20261019.1", False),
        (["20261019.1"], "20260722.7", False),
        (["20261019.1"], "20261018.9", False),
        (["20261019.9"], "20261019.10", True),
        (["20261019.9", "20261019.10"], "20261019.10", False),
        (["20261019.10"], "20261019.9", False),
        (["20251231.99", "20261019.1"], "20260101.1", False),
        (["20261019.1", "v20271231.1", "20271231.01", "20271231.0"], "20261019.2", True),
    ],
)
def test_version_check_compares_numerically(
    registry: Registry, tmp_path: Path, published: list[str], candidate: str, accepted: bool
) -> None:
    registry.page(FIRST_PAGE, published)

    assert _passes(_version_check(registry, candidate, tmp_path)) is accepted


def test_version_check_follows_every_page(registry: Registry, tmp_path: Path) -> None:
    registry.page(FIRST_PAGE, ["20261019.1"], f"{TAGS_PATH}?last=a&n=1000")
    registry.page(f"{TAGS_PATH}?last=a&n=1000", ["latest"], f"{TAGS_PATH}?last=b&n=1000")
    registry.page(f"{TAGS_PATH}?last=b&n=1000", ["20261019.9"])

    assert not _passes(_version_check(registry, "20261019.5", tmp_path))
    result = _version_check(registry, "20261019.10", tmp_path)
    assert _passes(result)
    assert "3 pages" in result.stdout


@pytest.mark.parametrize(
    ("pages", "message"),
    [
        ({FIRST_PAGE: ([], None)}, "no published version tags"),
        ({FIRST_PAGE: (["latest", "sha-abc"], None)}, "no published version tags"),
        ({FIRST_PAGE: ({"errors": [{"code": "DENIED"}]}, None)}, "has no list of tags"),
        ({FIRST_PAGE: ({"name": REPOSITORY, "tags": None}, None)}, "has no list of tags"),
        ({FIRST_PAGE: ({"name": REPOSITORY, "tags": "20261019.1"}, None)}, "has no list of tags"),
        ({FIRST_PAGE: ({"name": REPOSITORY, "tags": [20261019]}, None)}, "has no list of tags"),
        (
            {
                FIRST_PAGE: (["20261019.1"], f"{TAGS_PATH}?last=a&n=1000"),
                f"{TAGS_PATH}?last=a&n=1000": ({"errors": [{"code": "UNKNOWN"}]}, None),
            },
            "has no list of tags",
        ),
        ({FIRST_PAGE: (["20261019.1"], FIRST_PAGE)}, "pagination loops back"),
        (
            {
                FIRST_PAGE: (["20261019.1"], f"{TAGS_PATH}?last=a&n=1000"),
                f"{TAGS_PATH}?last=a&n=1000": (["latest"], FIRST_PAGE),
            },
            "pagination loops back",
        ),
        (
            {FIRST_PAGE: (["20261019.1"], "https://evil.example/v2/x/tags/list?n=1")},
            "unexpected pagination link",
        ),
        ({FIRST_PAGE: (["20261019.1"], f"{TAGS_PATH}?last=missing&n=1000")}, "returned HTTP 404"),
    ],
)
def test_version_check_fails_closed(
    registry: Registry, tmp_path: Path, pages: dict[str, tuple[object, str | None]], message: str
) -> None:
    for path, (tags, link) in pages.items():
        registry.page(path, tags, link)

    result = _version_check(registry, "20991231.1", tmp_path)

    assert result.returncode != 0
    assert message in result.stderr, result.stderr


def test_version_check_does_not_retry_client_errors(registry: Registry, tmp_path: Path) -> None:
    registry.page(FIRST_PAGE, ["20261019.1"], f"{TAGS_PATH}?last=missing&n=1000")

    result = _version_check(registry, "20991231.1", tmp_path)

    assert result.returncode != 0
    assert registry.requests.count(f"{TAGS_PATH}?last=missing&n=1000") == 1


def test_version_check_caps_the_number_of_pages(registry: Registry, tmp_path: Path) -> None:
    for page in range(60):
        path = FIRST_PAGE if page == 0 else f"{TAGS_PATH}?last={page}&n=1000"
        registry.page(path, ["20261019.1"], f"{TAGS_PATH}?last={page + 1}&n=1000")

    result = _version_check(registry, "20991231.1", tmp_path)

    assert result.returncode != 0
    assert "more than 50 tag pages" in result.stderr
    assert len([path for path in registry.requests if path.startswith(TAGS_PATH)]) == 50


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (401, {"errors": []}, "returned HTTP 401"),
        (200, {"access_token": "x"}, "has no token"),
        (200, {"token": ""}, "token is empty"),
    ],
)
def test_version_check_fails_without_a_registry_token(
    registry: Registry, tmp_path: Path, status: int, body: object, message: str
) -> None:
    registry.token_status = status
    registry.token_body = body
    registry.page(FIRST_PAGE, ["20261019.1"])

    result = _version_check(registry, "20991231.1", tmp_path)

    assert result.returncode != 0
    assert message in result.stderr


def test_version_check_rejects_a_malformed_candidate(registry: Registry, tmp_path: Path) -> None:
    registry.page(FIRST_PAGE, ["20261019.1"])

    result = _version_check(registry, "20991231.01", tmp_path)

    assert result.returncode != 0
    assert "is not a YYYYMMDD.N version" in result.stderr


def test_version_check_uses_only_the_standard_library() -> None:
    script = _step("publish", VERSION_CHECK).run
    assert script is not None
    imported = set()
    for node in ast.walk(ast.parse(script)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None
            imported.add(node.module)
    assert imported == {
        "json",
        "os",
        "re",
        "sys",
        "time",
        "typing",
        "urllib.error",
        "urllib.parse",
        "urllib.request",
    }


def _reread(tmp_path: Path, version_file: str, ref: str, tested: str, schema: str) -> int:
    step = _step("publish", "Re-read version and test outputs")
    assert step.shell == "bash" and step.run is not None
    (tmp_path / "VERSION").write_text(version_file + "\n", encoding="utf-8")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REF_NAME": ref,
        "TESTED_VERSION": tested,
        "TESTED_SCHEMA": schema,
    }
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step.run],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        assert output.read_text(encoding="utf-8") == f"value={tested}\nschema={schema}\n"
    return result.returncode


@pytest.mark.parametrize(
    ("version_file", "ref", "tested", "schema", "accepted"),
    [
        ("20261019.2", "v20261019.2", "20261019.2", "7f776a2cc7e60136", True),
        ("20261019.2", "v20261019.2", "20261019.1", "7f776a2cc7e60136", False),
        ("20261019.2", "v20261019.2", "", "7f776a2cc7e60136", False),
        ("20261019.2", "v20261019.3", "20261019.2", "7f776a2cc7e60136", False),
        ("20261019.02", "v20261019.02", "20261019.02", "7f776a2cc7e60136", False),
        ("20261019.2", "v20261019.2", "20261019.2", "", False),
        ("20261019.2", "v20261019.2", "20261019.2", "7f776a2cc7e6013G", False),
    ],
)
def test_publish_rereads_version_and_matches_test_job_outputs(
    tmp_path: Path, version_file: str, ref: str, tested: str, schema: str, accepted: bool
) -> None:
    assert (_reread(tmp_path, version_file, ref, tested, schema) == 0) is accepted


def test_publish_checks_version_before_login_and_build() -> None:
    names = [step.name for step in _jobs()["publish"]]

    assert names.index("Re-read version and test outputs") < names.index(VERSION_CHECK)
    assert names.index(VERSION_CHECK) < names.index("Log in to GHCR")
    assert names.index(VERSION_CHECK) < names.index("Build and publish commit candidate")
    assert names.index("Verify the candidate digest") < names.index("Promote verified digest")


def test_publish_job_runs_no_third_party_code() -> None:
    steps = _jobs()["publish"]

    assert steps[0].uses is not None and steps[0].uses.startswith("actions/checkout@")
    for step in steps:
        if step.uses is not None:
            assert step.uses in ALLOWED_PUBLISH_ACTIONS, step.uses
            assert step.run is None
            continue
        assert step.run is not None, step.name
        if step.name == VERSION_CHECK:
            assert step.shell == "python3 {0}"
            assert "subprocess" not in step.run and "os.system" not in step.run
            continue
        assert step.shell in (None, "bash"), step.name
        for command in _commands(step.run):
            assert not THIRD_PARTY_RUNNERS.search(command), (step.name, command)
            assert "|| true" not in command or command in {
                'HEALTH="$(curl -fsS http://127.0.0.1:8765/health || true)"',
                "docker rm -f ghidra-mcp-ci 2>/dev/null || true",
            }, (step.name, command)


def test_release_test_job_really_runs_the_container_e2e_test() -> None:
    step = _step("test", "Run container MCP end-to-end test")
    assert step.run is not None
    commands = _commands(step.run)

    pytest_line = commands.index(
        ".ci-venv/bin/uv run pytest tests/integration/test_container_mcp.py"
    )
    assert commands[pytest_line - 2].startswith(
        "GHIDRA_MCP_CONTAINER_URL=http://127.0.0.1:8765/mcp"
    )
    assert commands[pytest_line - 1].startswith('GHIDRA_MCP_CONTAINER_TOKEN="$TOKEN"')
    assert any(line.startswith("ghidra-mcp-release-test:local") for line in commands)


def test_release_steps_cannot_ignore_failures() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "continue-on-error" not in workflow
    for steps in _jobs().values():
        for step in steps:
            assert "if: always()" not in step.text or step.name.startswith("Remove "), step.name


def test_release_jobs_have_timeouts() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    timeouts = [int(value) for value in re.findall(r"^    timeout-minutes: (\d+)$", workflow, re.M)]

    assert len(timeouts) == len(_jobs()) == 2
    assert all(10 <= value <= 60 for value in timeouts)
