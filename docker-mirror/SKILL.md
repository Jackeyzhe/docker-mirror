---
name: docker-mirror
description: Find currently reachable Docker Hub registry mirrors, safely prepare Docker daemon registry-mirrors configuration, apply it only after explicit user confirmation, restart Docker, and verify pulls. Use when Docker image pulls fail or are slow because an existing mirror is unavailable, when Codex needs to update /etc/docker/daemon.json or Docker Desktop Engine JSON, or when a user asks to test Docker mirror availability.
---

# Docker Mirror

## Workflow

Use this skill to replace stale Docker Hub mirror settings with currently reachable mirrors. Do not hard-code or trust an old mirror list. Collect candidates from current web pages, official/team-provided notes, or user-provided URLs, then verify them live before changing Docker.

1. Inspect the local Docker environment:
   - Run `docker version` and `docker info` when Docker is available.
   - Identify whether the user is on Linux Docker Engine or Docker Desktop.
   - On Linux, use `/etc/docker/daemon.json` unless Docker reports another daemon config path.
   - On Docker Desktop, prefer the Docker Desktop Settings -> Docker Engine JSON editor. Do not edit private Docker Desktop files unless the user explicitly asks.
2. Gather candidate mirrors:
   - Search current sources or use user-provided URLs.
   - Prefer HTTPS URLs. Reject HTTP unless the user explicitly accepts insecure registry behavior.
   - Keep only registry mirror base URLs, not image names or web landing pages.
3. Probe candidates with `scripts/probe_mirrors.py`:
   - Use `--candidate URL` for ad hoc candidates or `--candidates-file PATH` for a newline-delimited list.
   - Use `--image library/hello-world --tag latest` by default, or a small image the user already needs.
   - Treat the script's sorted output as a reachability signal, then keep the fastest successful HTTPS mirrors.
4. Prepare Docker daemon configuration with `scripts/patch_daemon_json.py`:
   - Run dry-run first. Show the resulting JSON or diff to the user.
   - Use append mode by default to preserve existing mirrors; use replace mode only when stale mirrors should be removed.
   - Ask for explicit confirmation before `--write`, Docker restart, or Docker Desktop setting changes.
5. Apply and restart:
   - Linux: write the daemon JSON with elevated permissions, then restart Docker through the local service manager.
   - Docker Desktop: paste the generated JSON into Settings -> Docker Engine and let Docker Desktop apply/restart.
6. Verify:
   - Confirm `docker info` lists the intended Registry Mirrors.
   - Pull a small image such as `hello-world` or `alpine:latest`.
   - If verification fails, restore the backup or revert the Docker Desktop JSON and try the next successful candidate.

## Scripts

### Probe Mirrors

```bash
python3 docker-mirror/scripts/probe_mirrors.py \
  --candidate https://example-mirror.example.com \
  --image library/hello-world \
  --tag latest
```

Useful options:

- `--candidates-file PATH`: read candidates from a newline-delimited file. Blank lines and `#` comments are ignored.
- `--timeout SECONDS`: set per-request timeout.
- `--output json`: emit machine-readable sorted probe results.
- `--allow-http`: allow HTTP candidates only after the user accepts the risk.

### Patch Daemon JSON

Dry-run first:

```bash
python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com
```

Write only after confirmation:

```bash
sudo python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com \
  --write
```

Useful options:

- `--mode append`: preserve existing mirrors and append new verified mirrors.
- `--mode replace`: replace the mirror list with the verified mirrors.
- `--backup-dir PATH`: write backups somewhere other than the daemon JSON directory.
- `--allow-http`: allow HTTP mirror URLs only after explicit user confirmation.

## Safety Rules

- Never silently write Docker configuration or restart Docker. Confirm first.
- Always preserve unrelated daemon JSON keys.
- Always create a backup before writing over an existing daemon JSON file.
- If the Docker daemon JSON is invalid, stop and report the parse error; do not overwrite it.
- If every candidate fails probing, do not change Docker configuration.
