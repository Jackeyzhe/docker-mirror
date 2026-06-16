# Docker Mirror Skill

[中文说明](README.zh-CN.md)

Docker Mirror is a Codex skill for recovering from stale or unreachable Docker Hub registry mirrors. It helps an agent find current mirror candidates, probe them live, prepare a safe Docker daemon configuration change, and verify that Docker pulls work after the change.

The skill is intentionally conservative: it does not hard-code long-lived mirror lists, silently edit Docker configuration, or restart Docker without confirmation.

## What It Does

- Finds current Docker Hub mirror candidates from live sources or user-provided URLs.
- Probes candidate mirrors through `/v2/` and a small image manifest request.
- Generates a dry-run Docker daemon JSON patch for `registry-mirrors`.
- Writes configuration only when explicitly requested.
- Creates a backup before overwriting an existing daemon JSON file.
- Preserves unrelated Docker daemon settings.
- Verifies the result with `docker info` and a small `docker pull`.

## Installation

Install the skill with the open skills CLI:

```bash
npx skills add Jackeyzhe/docker-mirror --skill docker-mirror -g
```

Or clone the repository and link/copy the skill folder into your agent skills directory:

```bash
git clone git@github.com:Jackeyzhe/docker-mirror.git
cp -R docker-mirror/docker-mirror ~/.codex/skills/docker-mirror
```

If you manage skills through `skills-mgr`, use `~/.agents/skills` as the source of truth and then sync:

```bash
cp -R docker-mirror/docker-mirror ~/.agents/skills/docker-mirror
skills-mgr sync
```

Restart Codex after installing new skills.

## Usage

Ask Codex to use the skill:

```text
Use $docker-mirror to find available Docker registry mirrors, update my Docker configuration safely, and verify docker pull.
```

The expected workflow is:

1. Inspect the local Docker environment.
2. Gather current mirror candidates.
3. Probe candidates and keep successful HTTPS mirrors.
4. Generate a dry-run daemon JSON change.
5. Ask for confirmation before writing or restarting Docker.
6. Verify `docker info` and pull a small image.

## Scripts

### Probe Mirror Candidates

```bash
python3 docker-mirror/scripts/probe_mirrors.py \
  --candidate https://example-mirror.example.com \
  --image library/hello-world \
  --tag latest
```

Read candidates from a file:

```bash
python3 docker-mirror/scripts/probe_mirrors.py \
  --candidates-file mirrors.txt \
  --output json
```

HTTP mirrors are rejected by default. Use `--allow-http` only after accepting the insecure-registry risk.

### Patch Docker daemon.json

Dry-run only:

```bash
python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com
```

Write after confirmation:

```bash
sudo python3 docker-mirror/scripts/patch_daemon_json.py \
  --daemon-json /etc/docker/daemon.json \
  --mirror https://example-mirror.example.com \
  --write
```

Use `--mode append` to preserve existing mirrors, or `--mode replace` to replace stale mirrors with the verified list.

## Platform Notes

- Linux Docker Engine: use `/etc/docker/daemon.json` unless Docker reports another daemon config path.
- Docker Desktop: prefer Settings -> Docker Engine and paste the generated JSON there. Do not edit Docker Desktop private files unless you explicitly choose to.

## Development

Run the tests:

```bash
python3 -m unittest discover -s tests
```

Validate the skill structure:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py docker-mirror
```

## License

MIT
