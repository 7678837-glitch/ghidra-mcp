# Security policy

## Supported versions

Security fixes target the current `main` branch and the Ghidra security baseline documented in the README. Older commits, Ghidra releases below that baseline, and unmodified third-party components are outside the supported scope.

## Report a vulnerability

Do not disclose exploitable details, credentials, or sensitive binaries in public issues, discussions, logs, or test fixtures.

Use GitHub Private Vulnerability Reporting through the repository Security page and include:

- the affected version or Git commit;
- minimal reproduction steps and actual impact;
- redacted logs or sample characteristics when necessary;
- known mitigations.

If **Report a vulnerability** is not available, do not create a public issue or upload malicious samples, credentials, exploit details, or third-party data. First request a private reporting channel through the repository owner's GitHub profile.

## Deployment boundaries

- Use stdio only with a trusted client on the same machine.
- Streamable HTTP requires a random Bearer token of at least 32 UTF-8 bytes.
- Terminate TLS at a trusted reverse proxy for non-loopback access and restrict allowed sources.
- Mount only the analysis input directory at `GHIDRA_MCP_INPUT_ROOT`; use a read-only container mount and never expose sensitive host directories.
- Run Ghidra in a non-root, resource-limited container with minimal network access because it parses untrusted binaries.
- Treat the Bearer token as a deployment credential, not user-level authorization. Rotate it and restart the service after exposure.
- Back up the persistent project volume as sensitive data, restrict access, and verify restoration.

See the [operations runbook](https://github.com/xjoker/ghidra-mcp/wiki/Operations) for deployment, backup, recovery, and troubleshooting procedures.
