# Usage guide

[简体中文](usage.zh-CN.md)

This guide covers installation, MCP client connection, the normal analysis lifecycle, persistence, and container image availability.

## Choose a transport

- Use `stdio` when the MCP client and Ghidra run on the same trusted machine. The client launches and owns the server process; no token is required.
- Use `streamable-http` for remote or containerized access. It requires an input root, a public root URL, and a Bearer token of at least 32 UTF-8 bytes. Terminate TLS at a trusted reverse proxy for non-loopback access.

## Use the published container

After the GHCR package is public:

```bash
docker pull ghcr.io/xjoker/ghidra-mcp:latest
docker volume create ghidra-mcp-projects
(
read -rsp 'Ghidra MCP token: ' GHIDRA_MCP_AUTH_TOKEN && echo
export GHIDRA_MCP_AUTH_TOKEN
docker run -d --name ghidra-mcp \
  --platform linux/amd64 \
  -p 127.0.0.1:8765:8765 \
  -e GHIDRA_MCP_PUBLIC_URL=http://127.0.0.1:8765 \
  -e GHIDRA_MCP_AUTH_TOKEN \
  -v ghidra-mcp-projects:/data/projects \
  -v /absolute/path/to/binaries:/data/input:ro \
  ghcr.io/xjoker/ghidra-mcp:latest
)
```

The hidden prompt keeps the token value out of shell history. Anyone with Docker daemon access can still inspect container environment variables; restrict daemon access accordingly.

Use a version tag such as `20260722.5` for reproducible deployments. Use `latest` only when automatic upgrades are acceptable. Confirm the deployed `/health` response before testing functionality:

```bash
curl -fsS http://127.0.0.1:8765/health
```

Expected fields are `status`, `version`, `git_commit`, and `schema_version`. A healthy process does not prove that a binary can be imported; perform a real `program_open` check as well.

## Run from source over stdio

```bash
git clone https://github.com/xjoker/ghidra-mcp.git
cd ghidra-mcp
uv sync --locked
cp .env.example .env
```

Set `GHIDRA_INSTALL_DIR` to Ghidra 12.1.2 or later, then configure the MCP client to launch:

```text
uv --directory /absolute/path/to/ghidra-mcp run ghidra-mcp
```

Pass `GHIDRA_INSTALL_DIR=/absolute/path/to/ghidra` and `GHIDRA_MCP_TRANSPORT=stdio` in the client environment.

## Analysis lifecycle

The normal tool sequence is:

1. Call `program_open` with a binary path. HTTP mode accepts only regular files inside `GHIDRA_MCP_INPUT_ROOT`.
2. Keep the returned `program_id`; subsequent tools use it instead of reopening the binary.
3. Explore with `program_info`, `functions_list`, `instructions_list`, `references_list`, and `decompile_function`.
4. Use mutation tools only when intended. Writes run in Ghidra transactions and persist to the project store.
5. Call `program_close` when finished. It saves first and keeps the session open if saving fails.

Addresses are strings in Ghidra notation. `instructions_list` reports both the requested and effective start when Ghidra advances over undefined bytes. Detached continuation ranges are not function members until explicitly added with `function_body_add`.

## Persistence and backups

`GHIDRA_MCP_STORAGE_ROOT` contains persistent Ghidra projects. In containers, mount `/data/projects` as a dedicated volume and `/data/input` read-only. Never replace the only project volume during an upgrade.

Before backing up, stop writes and archive the project volume. Restore into a new volume, start a separate container, and verify saved names/comments before switching traffic. The complete procedure is in [operations.md](operations.md).

## Image publication status

The workflow at `.github/workflows/publish-container.yml` publishes on `main` pushes using the repository `GITHUB_TOKEN`. It creates version and `latest` tags, SBOM/provenance attestations, and verifies the pushed digest.

GitHub Container Registry package visibility is separate from workflow success. The package owner must set the package to public after its first publication. Anonymous availability is accepted only after this succeeds without `docker login`:

```bash
docker pull ghcr.io/xjoker/ghidra-mcp:<VERSION>
```

## Troubleshooting

- `401` from `/mcp`: the Bearer token is missing or incorrect.
- Public URL error: use the client-visible HTTP(S) root URL, not `0.0.0.0` or `::`.
- Input path rejected: place the file under `GHIDRA_MCP_INPUT_ROOT`; symlinks cannot escape it.
- Project lock error: another process still owns that project; close the program or stop the owner cleanly.
- Health commit mismatch: the running container is stale; stop functional testing and update the image/container first.

See [SECURITY.md](../SECURITY.md) before exposing HTTP beyond the local host.
