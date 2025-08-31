#!/usr/bin/env python3
"""
Query Moonraker for gcode_metadata, keep the N most recent files, and archive
the rest. Recency is computed as max(modified, print_start_time).

Usage examples:
  # Common usage: execute moves (default)
  python3 fetch_gcode_metadata.py

  # Preview only (no changes):
  python3 fetch_gcode_metadata.py --keep 17 --dry-run

  # Verbose listing of keep/archive sets:
  python3 fetch_gcode_metadata.py --keep 100 --verbose

  # Explicit server and directories:
  python3 fetch_gcode_metadata.py \
    --host localhost --port 7125 \
    --endpoint /server/database/item?namespace=gcode_metadata \
    --gcode-dir ~/printer_data/gcode \
    --archive-dir ~/printer_data/gcode/archive \
    --keep 42

Archiving: moves files from gcode_dir to archive_dir. Default is to execute
moves; pass --dry-run to only print the corresponding mv commands. Use
--verbose for detailed output.
"""

import argparse
import json
import os
import shutil
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 7125
DEFAULT_ENDPOINT = "/server/database/item?namespace=gcode_metadata"


def build_url(host: str, port: int, endpoint: str) -> str:
    """Construct an HTTP URL from host, port, and endpoint path."""
    ep = endpoint if endpoint.startswith("/") else "/" + endpoint
    return f"http://{host}:{port}{ep}"


def fetch_json(url: str, timeout_seconds: float) -> dict:
    """Fetch a URL and parse its JSON payload.

    Raises an exception if the HTTP request fails or the payload is not valid JSON.
    """
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:
        # Prefer server-declared charset; default to utf-8
        charset = response.headers.get_content_charset() or "utf-8"
        raw_text = response.read().decode(charset, errors="replace")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        snippet = raw_text[:2000]
        raise RuntimeError(
            f"Response was not valid JSON: {exc}. Partial body: {snippet!r}"
        ) from exc


def unwrap_moonraker_result(payload):
    """Moonraker commonly wraps results inside a 'result' field.

    This function unwraps that layer if present, otherwise returns the payload unchanged.
    """
    if isinstance(payload, dict) and "result" in payload:
        return payload["result"]
    return payload


def extract_gcode_index(content):
    """Return a mapping of filename -> metadata from Moonraker content.

    Moonraker database item responses typically look like:
      { "namespace": "gcode_metadata", "key": null, "value": { ...files... } }
    This function returns that inner value if present, else the content itself
    if it already looks like a filename->metadata mapping.
    """
    if isinstance(content, dict) and "value" in content and isinstance(content["value"], dict):
        return content["value"]
    return content


def compute_recency_seconds(file_metadata: dict) -> float:
    """Determine the recency metric for a file as max(modified, print_start_time)."""
    modified = file_metadata.get("modified")
    started = file_metadata.get("print_start_time")
    candidates = [t for t in (modified, started) if isinstance(t, (int, float))]
    if not candidates:
        return -1.0
    return float(max(candidates))


def select_keep_and_archive(filename_to_metadata: dict, keep_count: int):
    """Return (keep_list, archive_list) based on recency descending.

    Each list item is a (filename, recency_seconds) tuple.
    """
    scored = []
    for filename, metadata in filename_to_metadata.items():
        recency = compute_recency_seconds(metadata if isinstance(metadata, dict) else {})
        scored.append((filename, recency))

    # Newest first, unknown timestamps at the end (recency=-1)
    scored.sort(key=lambda item: item[1], reverse=True)

    keep = scored[: max(keep_count, 0)] if keep_count is not None else scored
    archive = scored[max(keep_count, 0) :] if keep_count is not None else []
    return keep, archive


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Moonraker gcode_metadata; optionally compute keep/archive sets"
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Moonraker host (default: localhost)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Moonraker port (default: 7125)")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Moonraker endpoint path (default: /server/database/item?namespace=gcode_metadata)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=42,
        help="Number of most-recent files to keep; others will be listed as archive (default: 42)",
    )
    parser.add_argument(
        "--gcode-dir",
        default=os.path.expanduser("~/printer_data/gcode"),
        help="Directory containing G-code files (default: ~/printer_data/gcode)",
    )
    parser.add_argument(
        "--archive-dir",
        default=os.path.expanduser("~/printer_data/gcode/archive"),
        help="Directory to move archived files into (default: ~/printer_data/gcode/archive)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print mv commands without moving files (default: execute moves)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed information including keep/archive lists",
    )
    args = parser.parse_args()

    # Always fetch from the Moonraker server
    try:
        url = build_url(args.host, args.port, args.endpoint)
        payload = fetch_json(url, args.timeout)
    except HTTPError as exc:
        print(f"HTTP error: {exc.code} {exc.reason}", file=sys.stderr)
        return 2
    except URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    content = unwrap_moonraker_result(payload)
    # Build keep/archive sets
    filename_to_metadata = extract_gcode_index(content)
    if not isinstance(filename_to_metadata, dict):
        print("Unexpected payload format: expected a mapping of filename to metadata", file=sys.stderr)
        return 1

    keep, archive = select_keep_and_archive(filename_to_metadata, args.keep)

    if args.verbose:
        print(f"Recency metric = max(modified, print_start_time)")
        print(f"Keeping {len(keep)} files:")
        for name, recency in keep:
            print(f"  KEEP   {recency:.3f}  {name}")
        print("")
        print(f"Archiving {len(archive)} files:")
        for name, recency in archive:
            # For unknown times, recency will be -1
            if recency < 0:
                print(f"  ARCH   unknown   {name}")
            else:
                print(f"  ARCH   {recency:.3f}  {name}")

    # Print or execute move commands
    gcode_dir = os.path.expanduser(args.gcode_dir)
    archive_dir = os.path.expanduser(args.archive_dir)
    print("")
    if not args.dry_run:
        if args.verbose:
            print(f"Executing moves to archive: {archive_dir}")
        for name, _ in archive:
            src = os.path.join(gcode_dir, name)
            dst = os.path.join(archive_dir, name)
            dst_parent = os.path.dirname(dst)
            try:
                os.makedirs(dst_parent, exist_ok=True)
                # Use shutil.move for robustness across filesystems
                shutil.move(src, dst)
                print(f"moved: {src} -> {dst}")
            except FileNotFoundError:
                if args.verbose:
                    print(f"skip (missing): {src}")
            except Exception as exc:  # noqa: BLE001 - CLI entrypoint
                print(f"error moving {src} -> {dst}: {exc}")
    else:
        if args.verbose:
            print("Dry run. The following commands would be executed:")
        for name, _ in archive:
            src = os.path.join(gcode_dir, name)
            dst = os.path.join(archive_dir, name)
            print(f'mv -n "{src}" "{dst}"')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
