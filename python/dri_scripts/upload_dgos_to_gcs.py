"""Upload DGO CSV files from python/dgos to ce-riverscapes/dgos on GCS.

This script uses `gcloud storage cp`, so make sure:
1. gcloud SDK is installed
2. You are authenticated (`gcloud auth login` or ADC)
3. You have write access to project `climate-engine-pro`

Examples:
    python3 dri_scripts/upload_dgos_to_gcs.py
    python3 dri_scripts/upload_dgos_to_gcs.py --source-dir ./dgos --pattern "*.csv"
    python3 dri_scripts/upload_dgos_to_gcs.py --dry-run
"""

import argparse
import shlex
import shutil
import subprocess
from pathlib import Path

from rsxml import Logger
from termcolor import colored

log = Logger("Upload DGOs to GCS")


def default_dgos_dir() -> Path:
    """Return the default dgos directory from the python project root."""
    return Path(__file__).resolve().parents[1] / "dgos"


def collect_files(source_dir: Path, pattern: str, recursive: bool) -> list[Path]:
    """Collect files to upload from source directory."""
    if recursive:
        files = [p for p in source_dir.rglob(pattern) if p.is_file()]
    else:
        files = [p for p in source_dir.glob(pattern) if p.is_file()]
    return sorted(files)


def gcs_uri(bucket: str, prefix: str, source_dir: Path, file_path: Path) -> str:
    """Build destination GCS URI preserving path relative to source_dir."""
    rel = file_path.relative_to(source_dir).as_posix()
    clean_prefix = prefix.strip("/")
    if clean_prefix:
        return f"gs://{bucket}/{clean_prefix}/{rel}"
    return f"gs://{bucket}/{rel}"


def main():
    parser = argparse.ArgumentParser(description="Upload DGO CSV files to GCS.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=default_dgos_dir(),
        help="Directory containing CSV files to upload (default: ./python/dgos).",
    )
    parser.add_argument(
        "--pattern",
        default="*.csv",
        help='Filename pattern to upload (default: "*.csv").',
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search source directory recursively.",
    )
    parser.add_argument(
        "--bucket",
        default="ce-riverscapes",
        help="Destination GCS bucket name.",
    )
    parser.add_argument(
        "--prefix",
        default="dgos",
        help='Destination prefix/folder inside bucket (default: "dgos").',
    )
    parser.add_argument(
        "--project",
        default="climate-engine-pro",
        help="GCP project used for upload commands.",
    )
    parser.add_argument(
        "--no-clobber",
        action="store_true",
        help="Do not overwrite objects that already exist in GCS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print upload commands without executing them.",
    )
    args = parser.parse_args()

    if shutil.which("gcloud") is None:
        raise SystemExit("gcloud CLI not found on PATH. Install Google Cloud SDK before uploading.")

    source_dir = args.source_dir.expanduser().resolve()
    if not source_dir.exists():
        raise SystemExit(f"Source directory does not exist: {source_dir}")

    files = collect_files(source_dir, args.pattern, args.recursive)
    if not files:
        log.warning(colored(f'No files found in {source_dir} matching pattern "{args.pattern}"', "yellow"))
        return

    log.title("Uploading Files to GCS")
    log.info(colored(f"Source directory: {source_dir}", "cyan"))
    log.info(colored(f"Files found: {len(files)}", "cyan"))
    log.info(colored(f"Destination: gs://{args.bucket}/{args.prefix.strip('/')}", "cyan"))
    log.info(colored(f"Project: {args.project}", "cyan"))

    uploaded = 0
    failed = 0

    for index, file_path in enumerate(files, start=1):
        destination = gcs_uri(args.bucket, args.prefix, source_dir, file_path)
        cmd = [
            "gcloud",
            "storage",
            "cp",
            str(file_path),
            destination,
            "--project",
            args.project,
        ]
        if args.no_clobber:
            cmd.append("--no-clobber")

        rel = file_path.relative_to(source_dir).as_posix()
        log.info(colored(f"[{index}/{len(files)}] {rel} -> {destination}", "cyan"))

        if args.dry_run:
            print(shlex.join(cmd))
            uploaded += 1
            continue

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            failed += 1
            detail = (result.stderr or result.stdout).strip()
            log.error(colored(f"Upload failed for {rel}", "red"))
            if detail:
                print(detail)
            continue

        uploaded += 1
        log.info(colored(f"Uploaded: {rel}", "green"))

    status_color = "green" if failed == 0 else "yellow"
    log.info(colored(f"Complete. uploaded={uploaded} failed={failed}", status_color))


if __name__ == "__main__":
    main()
