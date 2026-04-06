"""Convert parquet files in python/dgos to CSV files in the same directory.

Examples:
    python3 dri_scripts/parquet_to_csv.py
    python3 dri_scripts/parquet_to_csv.py --input-dir ./dgos --overwrite
"""

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from rsxml import Logger
from termcolor import colored

log = Logger("Parquet->CSV")
GEOMETRY_COLUMN_PRIORITY = ("geometry_simplified", "dgo_geom", "geometry")


def default_dgos_dir() -> Path:
    """Return the default dgos directory from the python project root."""
    return Path(__file__).resolve().parents[1] / "dgos"


def collect_parquet_files(input_dir: Path, recursive: bool) -> list[Path]:
    """Find parquet files in the input directory."""
    pattern = "**/*.parquet" if recursive else "*.parquet"
    return sorted(p for p in input_dir.glob(pattern) if p.is_file())


def ordered_columns(column_names: list[str]) -> list[str]:
    """Return target column order with dgo_id and watershed_id first."""
    if "watershed_id" not in column_names:
        raise ValueError("Missing required column 'watershed_id'")

    return [
        "dgo_id",
        "watershed_id",
        *[col for col in column_names if col not in {"dgo_id", "watershed_id"}],
    ]


def with_id_columns_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame/GeoDataFrame with dgo_id + watershed_id first."""
    row_count = len(df.index)
    out_df = df.copy()
    out_df["dgo_id"] = [f"{i:05d}" for i in range(1, row_count + 1)]
    return out_df.loc[:, ordered_columns(list(out_df.columns))]


def build_minimal_geo_metadata(table: pa.Table) -> bytes | None:
    """Build minimal GeoParquet metadata when missing and geometry columns are obvious."""
    geometry_columns: list[str] = []
    for name in table.column_names:
        field_type = table.schema.field(name).type
        if name in GEOMETRY_COLUMN_PRIORITY and pa.types.is_binary(field_type):
            geometry_columns.append(name)

    if not geometry_columns:
        return None

    primary_column = next((name for name in GEOMETRY_COLUMN_PRIORITY if name in geometry_columns), geometry_columns[0])
    geo_payload = {
        "version": "1.0.0",
        "primary_column": primary_column,
        "columns": {name: {"encoding": "WKB", "geometry_types": []} for name in geometry_columns},
    }
    return json.dumps(geo_payload, separators=(",", ":")).encode("utf-8")


def metadata_with_geo(source_metadata: dict[bytes, bytes] | None, table: pa.Table) -> dict[bytes, bytes] | None:
    """Carry forward non-pandas metadata and ensure GeoParquet metadata is present when possible."""
    metadata = dict(source_metadata or {})
    metadata.pop(b"pandas", None)

    if b"geo" not in metadata:
        inferred_geo = build_minimal_geo_metadata(table)
        if inferred_geo is not None:
            metadata[b"geo"] = inferred_geo

    return metadata or None


def rewrite_table_with_id_columns(source_table: pa.Table) -> pa.Table:
    """Return a table with dgo_id and watershed_id first, preserving GeoParquet metadata."""
    out_columns = ordered_columns(source_table.column_names)
    row_count = source_table.num_rows
    dgo_id_array = pa.array([f"{i:05d}" for i in range(1, row_count + 1)], type=pa.string())

    arrays: list[pa.Array | pa.ChunkedArray] = []
    for column_name in out_columns:
        if column_name == "dgo_id":
            arrays.append(dgo_id_array)
        else:
            arrays.append(source_table[column_name])

    out_table = pa.Table.from_arrays(arrays, names=out_columns)
    out_metadata = metadata_with_geo(source_table.schema.metadata, out_table)
    return out_table.replace_schema_metadata(out_metadata)


def convert_parquet_to_csv(parquet_path: Path, csv_path: Path):
    """Read one parquet file, add identifier columns, and write parquet + CSV."""
    try:
        # Primary path: GeoPandas preserves/updates GeoParquet metadata correctly.
        gdf = gpd.read_parquet(parquet_path)
        gdf = with_id_columns_df(gdf)
        gdf.to_parquet(parquet_path, index=False)
    except ValueError as exc:
        if "Missing geo metadata" not in str(exc):
            raise

        # Fallback for already-broken files lacking GeoParquet metadata.
        source_table = pq.read_table(parquet_path)
        out_table = rewrite_table_with_id_columns(source_table)
        pq.write_table(out_table, parquet_path)

    # Use pandas for CSV so binary geometry columns remain bytes-like values.
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
