#!/usr/bin/env python3
"""Probe Docker registry mirror candidates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


SUCCESS_STATUSES = {200, 301, 302, 307, 308, 401}
MANIFEST_ACCEPT = (
    "application/vnd.docker.distribution.manifest.v2+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json, "
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.oci.image.index.v1+json"
)


@dataclass
class ProbeResult:
    candidate: str
    ok: bool
    v2_status: int | None
    manifest_status: int | None
    elapsed_ms: int
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Docker registry mirror candidates.")
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Mirror base URL. Can be passed more than once.",
    )
    parser.add_argument(
        "--candidates-file",
        help="File containing one mirror base URL per line. Blank lines and # comments are ignored.",
    )
    parser.add_argument("--image", default="library/hello-world", help="Image repository to probe.")
    parser.add_argument("--tag", default="latest", help="Image tag to probe.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Per-request timeout in seconds.")
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Allow http:// candidates. HTTPS is required by default.",
    )
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args()


def normalize_candidate(candidate: str, allow_http: bool) -> str:
    trimmed = candidate.strip().rstrip("/")
    if not trimmed:
        raise ValueError("empty candidate")

    parsed = urlparse(trimmed)
    if not parsed.scheme:
        trimmed = f"https://{trimmed}"
        parsed = urlparse(trimmed)

    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"unsupported URL scheme: {parsed.scheme}")
    if parsed.scheme == "http" and not allow_http:
        raise ValueError("http candidate requires --allow-http")
    if not parsed.netloc:
        raise ValueError("candidate must include a host")

    return trimmed


def load_candidates(args: argparse.Namespace) -> list[str]:
    raw_candidates = list(args.candidate)
    if args.candidates_file:
        with open(args.candidates_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    raw_candidates.append(stripped)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_candidate in raw_candidates:
        try:
            candidate = normalize_candidate(raw_candidate, args.allow_http)
        except ValueError as error:
            print(f"Skipping {raw_candidate!r}: {error}", file=sys.stderr)
            continue
        if candidate not in seen:
            normalized.append(candidate)
            seen.add(candidate)

    return normalized


def request_status(url: str, timeout: float, method: str = "GET") -> int:
    request = Request(url, method=method, headers={"User-Agent": "docker-mirror-probe/1.0"})
    if "/manifests/" in url:
        request.add_header("Accept", MANIFEST_ACCEPT)

    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status
    except HTTPError as error:
        return error.code


def probe_candidate(candidate: str, image: str, tag: str, timeout: float) -> ProbeResult:
    start = time.monotonic()
    v2_status: int | None = None
    manifest_status: int | None = None
    error: str | None = None

    try:
        v2_url = urljoin(f"{candidate}/", "v2/")
        v2_status = request_status(v2_url, timeout)

        manifest_path = f"v2/{image.strip('/')}/manifests/{tag}"
        manifest_url = urljoin(f"{candidate}/", manifest_path)
        manifest_status = request_status(manifest_url, timeout, method="HEAD")
        if manifest_status == 405:
            manifest_status = request_status(manifest_url, timeout)
    except (TimeoutError, URLError, OSError) as request_error:
        error = str(request_error)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    ok = (
        error is None
        and v2_status in SUCCESS_STATUSES
        and manifest_status in SUCCESS_STATUSES
    )
    return ProbeResult(candidate, ok, v2_status, manifest_status, elapsed_ms, error)


def sort_results(results: Iterable[ProbeResult]) -> list[ProbeResult]:
    return sorted(results, key=lambda result: (not result.ok, result.elapsed_ms, result.candidate))


def print_text(results: list[ProbeResult]) -> None:
    print("OK  ELAPSED  V2   MANIFEST  CANDIDATE")
    for result in results:
        ok_text = "yes" if result.ok else "no "
        v2_text = "-" if result.v2_status is None else str(result.v2_status)
        manifest_text = "-" if result.manifest_status is None else str(result.manifest_status)
        print(
            f"{ok_text} {result.elapsed_ms:>6}ms {v2_text:>4} {manifest_text:>9}  {result.candidate}"
        )
        if result.error:
            print(f"    error: {result.error}")


def main() -> int:
    args = parse_args()
    candidates = load_candidates(args)
    if not candidates:
        print("No valid candidates to probe.", file=sys.stderr)
        return 2

    results = sort_results(
        probe_candidate(candidate, args.image, args.tag, args.timeout) for candidate in candidates
    )

    if args.output == "json":
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        print_text(results)

    return 0 if any(result.ok for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
