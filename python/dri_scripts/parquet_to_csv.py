"""Convert parquet files in python/dgos to CSV files in the same directory.

Examples:
    python3 dri_scripts/parquet_to_csv.py
    python3 dri_scripts/parquet_to_csv.py --input-dir ./dgos --overwrite
"""

import argparse
from pathlib import Path

import pandas as pd
from rsxml import Logger
from termcolor import colored

log = Logger("Parquet->CSV")


def default_dgos_dir() -> Path:
    """Return the default dgos directory from the python project root."""
    return Path(__file__).resolve().parents[1] / "dgos"


def collect_parquet_files(input_dir: Path, recursive: bool) -> list[Path]:
    """Find parquet files in the input directory."""
    pattern = "**/*.parquet" if recursive else "*.parquet"
    return sorted(p for p in input_dir.glob(pattern) if p.is_file())


def convert_parquet_to_csv(parquet_path: Path, csv_path: Path):
    """Read one parquet file and write one CSV file."""
    df = pd.read_parquet(parquet_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    return df.shape


def main():
    parser = argparse.ArgumentParser(description="Convert parquet files to CSV in the same directory.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=default_dgos_dir(),
        help="Directory containing .parquet files (default: ./python/dgos).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search for parquet files recursively.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing CSV files.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    parquet_files = collect_parquet_files(input_dir, recursive=args.recursive)
    if not parquet_files:
        log.warning(colored(f"No parquet files found in {input_dir}", "yellow"))
        return

    log.title("Converting Parquet Files")
    log.info(colored(f"Input directory: {input_dir}", "cyan"))
    log.info(colored(f"Parquet files found: {len(parquet_files)}", "cyan"))

    converted = 0
    skipped = 0
    failed = 0

    for index, parquet_path in enumerate(parquet_files, start=1):
        csv_path = parquet_path.with_suffix(".csv")
        rel = parquet_path.relative_to(input_dir)
        log.info(colored(f"[{index}/{len(parquet_files)}] {rel}", "cyan"))

        if csv_path.exists() and not args.overwrite:
            skipped += 1
            log.info(colored(f"Skipped existing CSV: {csv_path.name}", "yellow"))
            continue

        try:
            rows, cols = convert_parquet_to_csv(parquet_path, csv_path)
        except (OSError, ValueError, RuntimeError) as exc:
            failed += 1
            log.error(colored(f"Failed: {parquet_path.name} ({exc})", "red"))
            continue

        converted += 1
        log.info(colored(f"Wrote {csv_path.name} ({rows} rows, {cols} columns)", "green"))

    log.info(colored(f"Complete. converted={converted} skipped={skipped} failed={failed}", "green"))


if __name__ == "__main__":
    main()
