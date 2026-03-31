# -*- coding: utf-8 -*-
"""
Upload output_ready/ to Bunny.net Storage (HTTP API).
Secrets only from environment variables — never hardcoded.

CLI: python app.py upload_bunny [--output DIR] [--report FILE] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

from config import (
    BUNNY_BASE_URL,
    BUNNY_ROOT_FOLDER,
    BUNNY_PUBLIC_BASE_URL,
    BUNNY_STORAGE_API_KEY,
    BUNNY_STORAGE_HOST,
    BUNNY_STORAGE_ZONE_NAME,
    OUTPUT_READY_ROOT,
)

from bunny_credentials import get_credentials_for_upload

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
    )


log = logging.getLogger("bunny_upload")

# ---------------------------------------------------------------------------
# Config (loaded from environment at import — see config.py)
# ---------------------------------------------------------------------------

def get_storage_config() -> Tuple[str, str, str]:
    """
    Returns (zone_name, api_key, storage_host).
    api_key is the Storage Zone password (FTP & API Access tab).
    """
    return BUNNY_STORAGE_ZONE_NAME, BUNNY_STORAGE_API_KEY, BUNNY_STORAGE_HOST


def get_public_base_url() -> str:
    """HTTPS origin for public URLs (Pull Zone)."""
    base = BUNNY_PUBLIC_BASE_URL or BUNNY_BASE_URL
    return base.rstrip("/")


# ---------------------------------------------------------------------------
# File collection
# ---------------------------------------------------------------------------

SKIP_NAMES = frozenset({"README.md", ".gitkeep", ".DS_Store", "Thumbs.db"})


def collect_files(output_root: Path, path_prefix: str) -> List[Tuple[Path, str]]:
    """
    Map local files under output_root to remote paths:
    {path_prefix}/{book_slug}/{chapter_slug}/...
    """
    if not output_root.is_dir():
        return []
    pp = path_prefix.strip().strip("/")
    out: List[Tuple[Path, str]] = []
    for f in output_root.rglob("*"):
        if not f.is_file():
            continue
        if f.name in SKIP_NAMES or f.name.startswith("."):
            continue
        rel = f.relative_to(output_root).as_posix()
        remote = f"{pp}/{rel}" if pp else rel
        out.append((f, remote))
    return sorted(out, key=lambda x: x[1])


def public_url_for_remote(public_base: str, remote_path: str) -> str:
    """https://host/books/... (encode path segments)."""
    base = public_base.rstrip("/")
    encoded = "/".join(quote(seg, safe="") for seg in remote_path.split("/"))
    return f"{base}/{encoded}"


# ---------------------------------------------------------------------------
# HTTP upload (Bunny Storage API)
# ---------------------------------------------------------------------------

SUCCESS_CODES = frozenset({200, 201, 204})
MAX_RETRIES = 4
RETRY_DELAY_SEC = 1.5


def _build_put_url(storage_host: str, zone_name: str, remote_path: str) -> str:
    """PUT https://storage.bunnycdn.com/{zone}/{encoded/path}"""
    # Encode each path segment; keep slashes
    parts = remote_path.strip("/").split("/")
    encoded_path = "/".join(quote(p, safe="") for p in parts)
    # Zone name is usually alphanumeric; still quote for safety
    z = quote(zone_name.strip(), safe="")
    host = storage_host.strip().lower()
    if not host.startswith("http"):
        netloc = host
        scheme = "https"
    else:
        u = urlsplit(storage_host)
        scheme, netloc = u.scheme or "https", u.netloc
    path = f"/{z}/{encoded_path}"
    return urlunsplit((scheme, netloc, path, "", ""))


def _guess_content_type(name: str) -> str:
    n = name.lower()
    if n.endswith(".html"):
        return "text/html; charset=utf-8"
    if n.endswith(".mp3"):
        return "audio/mpeg"
    return "application/octet-stream"


def upload_file(
    local_path: Path,
    remote_path: str,
    zone_name: str,
    api_key: str,
    storage_host: str,
    dry_run: bool,
) -> Tuple[bool, str]:
    """
    Upload one file via Bunny Storage API.
    Returns (success, message).
    """
    data = local_path.read_bytes()
    url = _build_put_url(storage_host, zone_name, remote_path)
    if dry_run:
        log.info("[DRY-RUN] Would upload %s -> %s (%s bytes)", local_path, remote_path, len(data))
        return True, "dry-run"

    last_err: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url,
                data=data,
                method="PUT",
                headers={
                    "AccessKey": api_key,
                    "Content-Type": _guess_content_type(local_path.name),
                },
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                code = resp.getcode()
            if code in SUCCESS_CODES:
                return True, f"HTTP {code}"
            last_err = RuntimeError(f"Unexpected HTTP {code}")
        except urllib.error.HTTPError as e:
            last_err = e
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            log.warning(
                "HTTP error attempt %s/%s: %s %s %s",
                attempt,
                MAX_RETRIES,
                e.code,
                e.reason,
                body,
            )
            if e.code in (401, 403):
                return False, f"auth failed: HTTP {e.code} {e.reason}"
        except Exception as e:
            last_err = e
            log.warning("Upload attempt %s/%s failed: %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY_SEC * (2 ** (attempt - 1))
            log.info("Retrying in %.1fs...", delay)
            time.sleep(delay)

    return False, str(last_err) if last_err else "unknown error"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_upload(
    output_root: Path,
    path_prefix: str,
    report_path: Path,
    dry_run: bool,
    credentials: Optional[Dict[str, str]] = None,
) -> int:
    if credentials:
        zone = (credentials.get("storage_zone") or "").strip()
        key = (credentials.get("api_key") or "").strip()
        host = (credentials.get("storage_host") or "").strip() or "storage.bunnycdn.com"
        public_base = (credentials.get("pull_zone") or "").strip().rstrip("/") or BUNNY_BASE_URL.rstrip("/")
    else:
        zone, key, host = get_storage_config()
        public_base = get_public_base_url()

    if not dry_run:
        if not zone:
            log.error("Storage Zone name is required.")
            return 2
        if not key:
            log.error("API Key (Storage Zone password) is required.")
            return 2
        log.info("Storage zone: %s", zone)
        log.info("Storage host: %s", host)
        log.info("Public base:  %s", public_base)
    else:
        log.info("Dry-run mode (no uploads).")

    files = collect_files(output_root, path_prefix)
    if not files:
        log.error("No files to upload under %s", output_root)
        return 1

    chapters_report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_zone_base": public_base,
        "storage_host": host,
        "storage_zone": zone if zone else "(dry-run)",
        "path_prefix": path_prefix,
        "output_root": str(output_root.resolve()),
        "dry_run": dry_run,
        "chapters": [],
    }

    # Group by book_slug / chapter_slug (first two segments under path_prefix)
    by_chapter: Dict[str, Dict[str, Any]] = {}

    failed = 0
    for local_path, remote_path in files:
        log.info("Uploading %s -> %s", local_path, remote_path)
        ok, msg = upload_file(local_path, remote_path, zone, key, host, dry_run=dry_run)
        if ok:
            log.info("Success: %s (%s)", remote_path, msg)
        else:
            log.error("Failed: %s — %s", remote_path, msg)
            failed += 1

        parts = remote_path.split("/")
        # remote = books/book/chapter/...
        book_slug = parts[1] if len(parts) > 1 else ""
        chapter_slug = parts[2] if len(parts) > 2 else ""
        ch_key = f"{book_slug}/{chapter_slug}"

        entry = {
            "local_path": str(local_path.resolve()),
            "remote_path": remote_path,
            "public_url": public_url_for_remote(public_base, remote_path),
            "bytes": local_path.stat().st_size if local_path.is_file() else 0,
            "status": "ok" if ok else "error",
            "detail": msg,
        }

        if ch_key not in by_chapter:
            by_chapter[ch_key] = {
                "book_slug": book_slug,
                "chapter_slug": chapter_slug,
                "files": [],
            }
        by_chapter[ch_key]["files"].append(entry)

    chapters_report["chapters"] = list(by_chapter.values())
    chapters_report["summary"] = {
        "total_files": len(files),
        "failed": failed,
        "ok": len(files) - failed,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(chapters_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Wrote report: %s", report_path)

    return 1 if failed else 0


def main_cli(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Upload output_ready to Bunny Storage.")
    parser.add_argument(
        "--output",
        default=OUTPUT_READY_ROOT,
        help=f"Folder to upload (default: {OUTPUT_READY_ROOT})",
    )
    parser.add_argument(
        "--prefix",
        default=BUNNY_ROOT_FOLDER,
        help=f"Remote path prefix (default: {BUNNY_ROOT_FOLDER})",
    )
    parser.add_argument(
        "--report",
        default="upload_report.json",
        help="Write JSON report to this path (default: upload_report.json in cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List actions only, do not upload (skips credential prompt)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    credentials: Optional[Dict[str, str]] = None
    if not args.dry_run:
        creds = get_credentials_for_upload()
        if creds is None:
            log.info("Upload cancelled.")
            return 1
        credentials = creds
        log.info("Credentials loaded. Starting upload.")

    out = Path(args.output).resolve()
    report = Path(args.report).resolve()

    log.info("Upload started.")
    code = run_upload(out, args.prefix, report, dry_run=args.dry_run, credentials=credentials)
    if code == 0:
        log.info("Upload completed successfully.")
    else:
        log.error("Upload finished with errors.")
    return code


if __name__ == "__main__":
    sys.exit(main_cli())
