"""
Batch download DGO parquet data by HUC10 using fetchDGOParquetByHuc10.

Examples:
    uv run python -m scripts.fetch_dgos_batch production --huc10 1602020101
    uv run python -m scripts.fetch_dgos_batch production --huc10-file ./huc10_list.txt
"""

import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

import questionary
import requests
from rsxml import Logger
from termcolor import colored

from pyreports import ReportsAPI, ReportsAPIException

log = Logger("Fetch DGO Batch")
DEFAULT_HUC10 = "1602020101"
QUERY_NAME = "fetchDGOParquetByHuc10"


def parse_huc10_values(raw_values: list[str]) -> list[str]:
    """Parse repeated/comma-separated HUC10 values."""
    values = []
    for raw in raw_values:
        values.extend(v.strip() for v in raw.split(",") if v.strip())
    return values


def read_huc10_file(path: Path) -> list[str]:
    """Read HUC10 values from file (one per line and/or comma-separated)."""
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#"):
            continue
        values.extend(v.strip() for v in clean.split(",") if v.strip())
    return values


def unique_ordered(values: list[str]) -> list[str]:
    """Keep first occurrence order while removing duplicates."""
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def collect_huc10s(args) -> list[str]:
    """Collect HUC10 values from args/file or prompt once."""
    values = parse_huc10_values(args.huc10 or [])
    if args.huc10_file:
        values.extend(read_huc10_file(args.huc10_file))
    values = unique_ordered(values)
    if values:
        return values

    raw = questionary.text(
        "huc10 values (comma-separated):",
        default=DEFAULT_HUC10,
    ).ask()
    if not raw:
        return []
    return unique_ordered(parse_huc10_values([raw]))


def parquet_filename(url: str, huc10: str) -> str:
    """Infer local parquet filename from signed URL."""
    return Path(unquote(urlparse(url).path)).name or f"rme_{huc10}.parquet"


def fetch_signed_parquet_url(api: ReportsAPI, query: str, huc10: str) -> str | None:
    """Execute parquet query and return signed URL."""
    result = api.run_query(query, {"huc10": huc10})
    url = (result.get("data") or {}).get(QUERY_NAME)
    if not url:
        log.warning(colored(f"No parquet download URL returned for huc10={huc10}", "yellow"))
        print(json.dumps(result, indent=2))
    return url


def main():
    parser = argparse.ArgumentParser(description="Batch download DGO parquet files by HUC10.")
    parser.add_argument(
        "stage",
        choices=["staging", "production", "local"],
        help="API stage ('local' requires a local server on http://localhost:7016)",
    )
    parser.add_argument(
        "--huc10",
        action="append",
        default=[],
        help="HUC10 value(s). Repeat flag or provide comma-separated values.",
    )
    parser.add_argument(
        "--huc10-file",
        type=Path,
        help="Path to text file of HUC10 values (one per line and/or comma-separated).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dgos"),
        help="Directory where parquet files will be saved (default: ./dgos).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing parquet files.",
    )
    parser.add_argument(
        "--print-urls",
        action="store_true",
        help="Print signed URLs only (do not download files).",
    )
    args = parser.parse_args()

    huc10s = collect_huc10s(args)
    if not huc10s:
        log.warning(colored("No huc10 values provided.", "yellow"))
        return

    output_dir = args.output_dir.expanduser()
    log.title("Running: fetchDGOParquetByHuc10 (batch)")
    log.info(colored(f"HUC10 count: {len(huc10s)}", "cyan"))
    if not args.print_urls:
        log.info(colored(f"Output directory: {output_dir}", "cyan"))

    with ReportsAPI(stage=args.stage) as api:
        query = api.load_query(QUERY_NAME)

        downloaded = 0
        skipped = 0
        failed = 0

        for index, huc10 in enumerate(huc10s, start=1):
            log.info(colored(f"[{index}/{len(huc10s)}] huc10={huc10}", "cyan"))
            try:
                url = fetch_signed_parquet_url(api, query, huc10)
            except ReportsAPIException as exc:
                failed += 1
                log.error(colored(f"Query failed for {huc10}: {exc}", "red"))
                continue

            if not url:
                failed += 1
                continue

            if args.print_urls:
                print(f"{huc10}\t{url}")
                downloaded += 1
                continue

            local_path = output_dir / parquet_filename(url, huc10)
            try:
                did_download = api.download_file(url, str(local_path), force=args.overwrite)
            except (requests.RequestException, OSError, ReportsAPIException) as exc:
                failed += 1
                log.error(colored(f"Failed to download {huc10}: {exc}", "red"))
                continue

            if did_download:
                downloaded += 1
                log.info(colored(f"Saved parquet to {local_path}", "green"))
            else:
                skipped += 1
                log.info(colored(f"Skipped existing file: {local_path}", "yellow"))

    log.info(colored(f"Complete. downloaded={downloaded} skipped={skipped} failed={failed}", "green"))


if __name__ == "__main__":
    main()
