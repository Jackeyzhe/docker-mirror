#!/usr/bin/env python3
"""Safely prepare or apply Docker daemon registry mirror configuration."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_DAEMON_JSON = "/etc/docker/daemon.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch Docker daemon.json registry-mirrors safely."
    )
    parser.add_argument(
        "--daemon-json",
        default=DEFAULT_DAEMON_JSON,
        help=f"Path to daemon.json. Defaults to {DEFAULT_DAEMON_JSON}.",
    )
    parser.add_argument(
        "--mirror",
        action="append",
        default=[],
        help="Mirror URL to add. Can be passed more than once.",
    )
    parser.add_argument(
        "--mirrors-file",
        help="File containing one mirror URL per line. Blank lines and # comments are ignored.",
    )
    parser.add_argument(
        "--mode",
        choices=("append", "replace"),
        default="append",
        help="Append to existing mirrors or replace them.",
    )
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Allow http:// mirror URLs. HTTPS is required by default.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write changes and create a backup. Without this flag, only print the patched JSON.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Directory for backups. Defaults to the daemon.json directory.",
    )
    return parser.parse_args()


def normalize_mirror(mirror: str, allow_http: bool) -> str:
    trimmed = mirror.strip().rstrip("/")
    if not trimmed:
        raise ValueError("empty mirror URL")

    parsed = urlparse(trimmed)
    if not parsed.scheme:
        trimmed = f"https://{trimmed}"
        parsed = urlparse(trimmed)

    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"unsupported URL scheme: {parsed.scheme}")
    if parsed.scheme == "http" and not allow_http:
        raise ValueError("http mirror requires --allow-http")
    if not parsed.netloc:
        raise ValueError("mirror URL must include a host")

    return trimmed


def unique_values(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def load_mirrors(args: argparse.Namespace) -> list[str]:
    raw_mirrors = list(args.mirror)
    if args.mirrors_file:
        with open(args.mirrors_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    raw_mirrors.append(stripped)

    mirrors: list[str] = []
    for raw_mirror in raw_mirrors:
        mirrors.append(normalize_mirror(raw_mirror, args.allow_http))
    return unique_values(mirrors)


def read_daemon_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error

    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def patch_config(config: dict[str, Any], mirrors: list[str], mode: str) -> dict[str, Any]:
    existing_value = config.get("registry-mirrors", [])
    if not isinstance(existing_value, list) or not all(
        isinstance(item, str) for item in existing_value
    ):
        raise ValueError("existing registry-mirrors must be a list of strings")

    patched = dict(config)
    if mode == "replace":
        patched["registry-mirrors"] = mirrors
    else:
        patched["registry-mirrors"] = unique_values(existing_value + mirrors)
    return patched


def write_config(path: Path, config: dict[str, Any], backup_dir: Path | None) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None

    if path.exists():
        target_backup_dir = backup_dir or path.parent
        target_backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = target_backup_dir / f"{path.name}.{timestamp}.bak"
        shutil.copy2(path, backup_path)

    serialized = json.dumps(config, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
    ) as handle:
        handle.write(serialized)
        temp_name = handle.name

    os.replace(temp_name, path)
    return backup_path


def main() -> int:
    args = parse_args()
    daemon_path = Path(args.daemon_json)
    backup_dir = Path(args.backup_dir) if args.backup_dir else None

    try:
        mirrors = load_mirrors(args)
        if not mirrors:
            raise ValueError("at least one --mirror or --mirrors-file entry is required")
        config = read_daemon_config(daemon_path)
        patched = patch_config(config, mirrors, args.mode)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if not args.write:
        print(f"Dry run: {daemon_path} was not changed.")
        print(json.dumps(patched, indent=2, sort_keys=True))
        return 0

    try:
        backup_path = write_config(daemon_path, patched, backup_dir)
    except OSError as error:
        print(f"error: failed to write {daemon_path}: {error}", file=sys.stderr)
        return 2

    if backup_path:
        print(f"Backup written: {backup_path}")
    else:
        print("No existing daemon.json; no backup was needed.")
    print(f"Updated: {daemon_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
