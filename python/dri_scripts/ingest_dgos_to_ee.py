"""Ingest DGO CSVs from GCS into Earth Engine as per-HUC10 polygon FeatureCollections.

This script scans CSV objects in a GCS location (default: gs://ce-riverscapes/dgos),
extracts HUC10 values from filenames like `rme_1303020101.csv`, converts binary
WKB-style geometry columns to WKT, stages converted CSVs to GCS, and starts one
Earth Engine table ingestion task per file.
Converted staging CSVs are retained in GCS under a temp prefix.

Output asset IDs follow:
    projects/dri-blm/assets/bootheel-sra/dgos/huc_{huc10}

Requirements:
1. `gcloud` CLI installed and authenticated for bucket access.
2. `earthengine` CLI installed and authenticated for EE asset ingestion.
3. Python package `shapely` available in the runtime environment.
4. Write access to the destination EE asset root.

Examples:
    python3 dri_scripts/ingest_dgos_to_ee.py --dry-run
    python3 dri_scripts/ingest_dgos_to_ee.py
    python3 dri_scripts/ingest_dgos_to_ee.py --overwrite-existing
"""

import argparse
import ast
import csv
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rsxml import Logger
from termcolor import colored

log = Logger("Ingest DGOs to EE")
HUC10_PATTERN = re.compile(r"rme_(\d{10})\.csv$", re.IGNORECASE)
NOT_FOUND_MARKERS = ("not found", "no such asset", "does not exist")


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command and return completed process without raising."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def command_detail(result: subprocess.CompletedProcess[str]) -> str:
    """Return stderr/stdout detail for command failures."""
    return (result.stderr or result.stdout).strip()


def gcs_search_uri(bucket: str, prefix: str, pattern: str, recursive: bool) -> str:
    """Build a gs:// URI pattern for object listing."""
    clean_prefix = prefix.strip("/")
    wildcard = f"**/{pattern}" if recursive else pattern
    if clean_prefix:
        return f"gs://{bucket}/{clean_prefix}/{wildcard}"
    return f"gs://{bucket}/{wildcard}"


def list_csv_objects(bucket: str, prefix: str, pattern: str, recursive: bool, project: str | None) -> list[str]:
    """List matching CSV object URIs from GCS."""
    search_uri = gcs_search_uri(bucket, prefix, pattern, recursive)
    cmd = ["gcloud", "storage", "ls", search_uri]
    if project:
        cmd.extend(["--project", project])
    result = run_command(cmd)

    if result.returncode != 0:
        raise RuntimeError(f"Failed to list GCS objects with {search_uri}\n{command_detail(result)}")

    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return sorted({row for row in rows if row.lower().endswith(".csv")})


def filename_from_gs_uri(gs_uri: str) -> str:
    """Get object filename from gs:// URI."""
    return gs_uri.rstrip("/").split("/")[-1]


def extract_huc10(gs_uri: str) -> str | None:
    """Extract HUC10 from filename pattern rme_{huc10}.csv."""
    match = HUC10_PATTERN.match(filename_from_gs_uri(gs_uri))
    return match.group(1) if match else None


def ee_asset_exists(asset_id: str) -> bool:
    """Return True if EE asset exists, False if it does not."""
    result = run_command(["earthengine", "asset", "info", asset_id])
    if result.returncode == 0:
        return True

    detail = f"{result.stdout}\n{result.stderr}".lower()
    if any(marker in detail for marker in NOT_FOUND_MARKERS):
        return False

    raise RuntimeError(f"Failed checking asset existence for {asset_id}\n{command_detail(result)}")


def delete_ee_asset(asset_id: str):
    """Delete an EE asset."""
    result = run_command(["earthengine", "rm", asset_id])
    if result.returncode != 0:
        raise RuntimeError(f"Failed deleting existing asset {asset_id}\n{command_detail(result)}")


def copy_with_gcloud(src: str, dst: str, project: str | None):
    """Copy a local or GCS object using gcloud storage cp."""
    cmd = ["gcloud", "storage", "cp", src, dst]
    if project:
        cmd.extend(["--project", project])
    result = run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed copying {src} -> {dst}\n{command_detail(result)}")


def _ensure_csv_field_size_limit():
    """Raise CSV parser field limit to handle large geometry columns."""
    max_size = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_size)
            return
        except OverflowError:
            max_size //= 10


def _load_shapely_wkb():
    """Import shapely.wkb lazily with a clear error message."""
    try:
        from shapely import wkb as shapely_wkb
    except ImportError as exc:
        raise RuntimeError(
            "shapely is required for WKB->WKT conversion. Install it in your Python env, e.g. `python3 -m pip install shapely`."
        ) from exc
    return shapely_wkb


def parse_wkb_literal(raw_value: str) -> bytes:
    """Parse a geometry value like b\"\\x01...\" into bytes."""
    value = (raw_value or "").strip()
    if not value:
        raise ValueError("empty geometry value")

    if value.startswith(("b'", 'b"')):
        parsed = ast.literal_eval(value)
        if not isinstance(parsed, (bytes, bytearray)):
            raise ValueError("geometry literal did not evaluate to bytes")
        return bytes(parsed)

    compact = value.replace(" ", "")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise ValueError("geometry value is neither bytes literal nor hex WKB") from exc


def convert_wkb_csv_to_wkt(
    source_csv: Path,
    output_csv: Path,
    preferred_geometry_column: str,
    fallback_geometry_column: str,
    output_geometry_column: str,
) -> tuple[int, str]:
    """Convert one CSV's WKB-like geometry column into a WKT geometry column."""
    _ensure_csv_field_size_limit()
    shapely_wkb = _load_shapely_wkb()

    with source_csv.open(newline="", encoding="utf-8") as src_handle:
        reader = csv.DictReader(src_handle)
        if not reader.fieldnames:
            raise RuntimeError(f"Missing CSV header: {source_csv}")

        geometry_column = None
        if preferred_geometry_column in reader.fieldnames:
            geometry_column = preferred_geometry_column
        elif fallback_geometry_column in reader.fieldnames:
            geometry_column = fallback_geometry_column
        else:
            raise RuntimeError(
                f"No geometry column found. Tried '{preferred_geometry_column}' and '{fallback_geometry_column}'."
            )

        if output_geometry_column in reader.fieldnames:
            raise RuntimeError(
                f"Output geometry column '{output_geometry_column}' already exists in CSV; choose a different output name."
            )

        drop_columns = {"dgo_geom", "geometry_simplified"}
        out_fieldnames = [name for name in reader.fieldnames if name not in drop_columns]
        out_fieldnames.append(output_geometry_column)

        converted_rows = 0
        with output_csv.open("w", newline="", encoding="utf-8") as out_handle:
            writer = csv.DictWriter(out_handle, fieldnames=out_fieldnames)
            writer.writeheader()

            for row_index, row in enumerate(reader, start=2):
                raw_geometry = row.get(geometry_column, "")
                try:
                    geom_bytes = parse_wkb_literal(raw_geometry)
                    geom = shapely_wkb.loads(geom_bytes)
                    if geom.is_empty:
                        raise ValueError("empty geometry")
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed geometry conversion in {source_csv.name} at CSV row {row_index}: {exc}"
                    ) from exc

                out_row = {key: row.get(key, "") for key in out_fieldnames if key != output_geometry_column}
                out_row[output_geometry_column] = geom.wkt
                writer.writerow(out_row)
                converted_rows += 1

    return converted_rows, geometry_column


def temp_gcs_uri(bucket: str, temp_prefix: str, huc10: str) -> str:
    """Return staging URI for converted CSV upload."""
    clean_prefix = temp_prefix.strip("/")
    return f"gs://{bucket}/{clean_prefix}/huc_{huc10}.csv"


def write_table_manifest(manifest_path: Path, asset_id: str, source_uri: str, geometry_column: str):
    """Write an Earth Engine table upload manifest."""
    manifest = {
        "name": asset_id,
        "sources": [
            {
                "uris": [source_uri],
                "crs": "EPSG:4326",
                "primaryGeometryColumn": geometry_column,
                "xColumn": "",
                "yColumn": "",
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def start_table_ingestion_from_manifest(manifest_path: Path):
    """Start EE table ingestion from a manifest file."""
    result = run_command(["earthengine", "upload", "table", "--manifest", str(manifest_path)])
    if result.returncode != 0:
        raise RuntimeError(f"Failed starting ingestion with manifest {manifest_path}\n{command_detail(result)}")
    output = (result.stdout or "").strip()
    if output:
        print(output)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest DGO CSVs from GCS into Earth Engine polygon FeatureCollections."
    )
    parser.add_argument("--bucket", default="ce-riverscapes", help="Source GCS bucket name.")
    parser.add_argument("--prefix", default="dgos", help='Source prefix in bucket (default: "dgos").')
    parser.add_argument(
        "--pattern",
        default="rme_*.csv",
        help='Object filename pattern to ingest (default: "rme_*.csv").',
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search recursively under prefix (uses ** wildcard).",
    )
    parser.add_argument(
        "--asset-root",
        default="projects/dri-blm/assets/bootheel-sra/dgos",
        help='Destination EE asset root (default: "projects/dri-blm/assets/bootheel-sra/dgos").',
    )
    parser.add_argument(
        "--project",
        default="climate-engine-pro",
        help="GCP project used for gcloud commands.",
    )
    parser.add_argument(
        "--temp-prefix",
        default="dgos-ee-ingest-tmp",
        help='Temporary GCS prefix for converted CSVs (default: "dgos-ee-ingest-tmp").',
    )
    parser.add_argument(
        "--geometry-column",
        default="geometry_simplified",
        help='Preferred source geometry column (default: "geometry_simplified").',
    )
    parser.add_argument(
        "--fallback-geometry-column",
        default="dgo_geom",
        help='Fallback source geometry column if preferred column missing (default: "dgo_geom").',
    )
    parser.add_argument(
        "--output-geometry-column",
        default="ee_geometry_wkt",
        help='Output WKT geometry column for EE ingestion (default: "ee_geometry_wkt").',
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Delete existing EE assets before ingesting.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Optional limit for number of files to ingest (after sorting).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned ingestion commands without executing.",
    )
    args = parser.parse_args()

    if shutil.which("gcloud") is None:
        raise SystemExit("gcloud CLI not found on PATH. Install Google Cloud SDK first.")
    if shutil.which("earthengine") is None:
        raise SystemExit("earthengine CLI not found on PATH. Install and auth Earth Engine CLI first.")

    files = list_csv_objects(
        bucket=args.bucket,
        prefix=args.prefix,
        pattern=args.pattern,
        recursive=args.recursive,
        project=args.project,
    )
    if not files:
        log.warning(colored("No CSV files found to ingest.", "yellow"))
        return

    if args.max_files is not None:
        files = files[: args.max_files]

    asset_root = args.asset_root.rstrip("/")
    source_prefix = args.prefix.strip("/")
    source_uri = f"gs://{args.bucket}/{source_prefix}" if source_prefix else f"gs://{args.bucket}"

    log.title("Ingesting DGOs to Earth Engine (polygon geometry)")
    log.info(colored(f"CSV files found: {len(files)}", "cyan"))
    log.info(colored(f"Source: {source_uri}", "cyan"))
    log.info(colored(f"Asset root: {asset_root}", "cyan"))
    log.info(colored(f"Temp prefix: gs://{args.bucket}/{args.temp_prefix.strip('/')}", "cyan"))
    log.info(colored("Staged converted CSVs are retained for task reliability.", "cyan"))

    started = 0
    skipped = 0
    failed = 0
    ignored = 0
    seen_huc10s = set()

    for index, csv_uri in enumerate(files, start=1):
        huc10 = extract_huc10(csv_uri)
        if not huc10:
            ignored += 1
            log.warning(colored(f"[{index}/{len(files)}] Ignoring unexpected filename: {csv_uri}", "yellow"))
            continue

        if huc10 in seen_huc10s:
            ignored += 1
            log.warning(colored(f"[{index}/{len(files)}] Duplicate HUC10 encountered, skipping: {huc10}", "yellow"))
            continue
        seen_huc10s.add(huc10)

        asset_id = f"{asset_root}/huc_{huc10}"
        staged_csv_uri = temp_gcs_uri(args.bucket, args.temp_prefix, huc10)

        log.info(colored(f"[{index}/{len(files)}] {csv_uri} -> {asset_id}", "cyan"))

        if args.dry_run:
            print(f"# convert geometry and stage: {csv_uri} -> {staged_csv_uri}")
            print(
                "earthengine upload table --manifest "
                + shlex.quote(f"<manifest name={asset_id} source={staged_csv_uri} geom={args.output_geometry_column}>")
            )
            started += 1
            continue

        try:
            exists = ee_asset_exists(asset_id)
            if exists and not args.overwrite_existing:
                skipped += 1
                log.info(colored(f"Skipped existing asset: {asset_id}", "yellow"))
                continue
            if exists and args.overwrite_existing:
                log.info(colored(f"Deleting existing asset: {asset_id}", "yellow"))
                delete_ee_asset(asset_id)

            with tempfile.TemporaryDirectory(prefix=f"dgo-ee-{huc10}-") as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                local_source_csv = tmp_dir / f"{huc10}.source.csv"
                local_converted_csv = tmp_dir / f"{huc10}.converted.csv"
                manifest_path = tmp_dir / f"{huc10}.manifest.json"

                copy_with_gcloud(csv_uri, str(local_source_csv), project=args.project)
                converted_rows, geometry_column_used = convert_wkb_csv_to_wkt(
                    source_csv=local_source_csv,
                    output_csv=local_converted_csv,
                    preferred_geometry_column=args.geometry_column,
                    fallback_geometry_column=args.fallback_geometry_column,
                    output_geometry_column=args.output_geometry_column,
                )

                log.info(
                    colored(
                        f"Converted {converted_rows} rows using {geometry_column_used} -> {args.output_geometry_column}",
                        "cyan",
                    )
                )

                copy_with_gcloud(str(local_converted_csv), staged_csv_uri, project=args.project)
                write_table_manifest(
                    manifest_path=manifest_path,
                    asset_id=asset_id,
                    source_uri=staged_csv_uri,
                    geometry_column=args.output_geometry_column,
                )
                start_table_ingestion_from_manifest(manifest_path)

            started += 1
            log.info(colored(f"Started polygon ingestion: {asset_id}", "green"))
        except RuntimeError as exc:
            failed += 1
            log.error(colored(str(exc), "red"))

    status_color = "green" if failed == 0 else "yellow"
    log.info(
        colored(
            f"Complete. started={started} skipped={skipped} ignored={ignored} failed={failed}",
            status_color,
        )
    )


if __name__ == "__main__":
    main()
