"""
Run this using the launch menu under  "🐍 Python: Run/Debug Current File"

Interactive script to demonstrate DGO-related GraphQL queries.

"""

import argparse
import json
from pathlib import Path
from urllib.parse import unquote, urlparse

import questionary
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Fetch DGOs')

QUERIES = {
    "Fetch all DGOs inside a HUC10 (paginated)": {
        "variables": ["huc10"],
        "queryFile": "fetchDGOsByHuc10",
    },
    "Fetch a signed S3 URL to download raw Parquet data": {
        "variables": ["huc10"],
        "queryFile": "fetchDGOParquetByHuc10",
    },
    "Fetch DGOs between a start and end segment distance of a given levelPath": {
        "variables": ["huc10", "startLevelPath", "startSegmentDistance", "endSegmentationDistance"],
        "queryFile": "fetchDGOsByLevelPathEnd",
    },
    "Fetch DGOs downstream of a given levelPath by segmentDistance": {
        "variables": ["huc10", "startLevelPath", "startSegmentDistance", "distance"],
        "queryFile": "fetchDGOsByLevelPathDistance",
    },
    "Fetch all DGOs downstream of a given levelPath and count": {
        "variables": ["huc10", "startLevelPath", "startSegmentDistance", "count"],
        "queryFile": "fetchDGOsByLevelPathCount",
    },
    "Fetch DGOs by a specific list of DGO IDs": {
        "variables": ["huc10", "dgoIds"],
        "queryFile": "fetchDGOs",
    },
}

DEFAULTS = {
    "huc10": "1602020101",
    "startLevelPath": "70000400028442",
    "startSegmentDistance": 1034.0,
    "endSegmentationDistance": 10.0,
    "distance": 500.0,
    "count": 5,
    "dgoIds": ["70000400028442-1034.0"],
}


def prompt_variables(var_names: list[str]) -> dict:
    """Prompt the user for each required variable with sensible defaults."""
    variables = {}
    for name in var_names:
        default = DEFAULTS.get(name)
        if name == "dgoIds":
            raw = questionary.text(
                f"{name} (comma-separated):",
                default=",".join(default),
            ).ask()
            variables[name] = [v.strip() for v in raw.split(",") if v.strip()]
        elif isinstance(default, float):
            raw = questionary.text(f"{name}:", default=str(default)).ask()
            variables[name] = float(raw)
        elif isinstance(default, int):
            raw = questionary.text(f"{name}:", default=str(default)).ask()
            variables[name] = int(raw)
        else:
            variables[name] = questionary.text(f"{name}:", default=str(default)).ask()
    return variables


def parquet_download_path(url: str, huc10: str) -> Path:
    """Build a default local destination for a downloaded parquet file."""
    filename = Path(unquote(urlparse(url).path)).name or f"rme_{huc10}.parquet"
    return Path("./dgos") / filename


def download_parquet_result(api: ReportsAPI, result: dict, huc10: str):
    """Prompt for a path and download the signed parquet URL."""
    url = (result.get("data") or {}).get("fetchDGOParquetByHuc10")
    if not url:
        log.warning(colored("No parquet download URL was returned by the API.", "yellow"))
        print(json.dumps(result, indent=2))
        return

    local_path_raw = questionary.text(
        "Save parquet to:",
        default=str(parquet_download_path(url, huc10)),
    ).ask()
    if not local_path_raw:
        log.warning(colored("Download cancelled. Printing the signed URL instead.", "yellow"))
        print(url)
        return

    local_path = Path(local_path_raw).expanduser()
    force = False
    if local_path.exists():
        overwrite = questionary.confirm(
            f"{local_path} already exists. Overwrite?",
            default=False,
        ).ask()
        if not overwrite:
            log.warning(colored("Download skipped because the destination file already exists.", "yellow"))
            return
        force = True

    api.download_file(url, str(local_path), force=force)
    log.info(colored(f"✅ Saved parquet to {local_path}", "green"))


def main():
    parser = argparse.ArgumentParser(description="Demonstrate DGO GraphQL queries.")
    parser.add_argument("stage", choices=["staging", "production", "local"], help="API stage")
    args = parser.parse_args()

    choice = questionary.select(
        "Which query would you like to run?",
        choices=list(QUERIES.keys()),
    ).ask()
    if not choice:
        return

    entry = QUERIES[choice]
    variables = prompt_variables(entry["variables"])

    log.title(f"🔍 Running: {choice}")
    log.info(colored(f"📋 Variables: {json.dumps(variables, indent=2)}", 'cyan'))

    with ReportsAPI(stage=args.stage) as api:
        query = api.load_query(entry["queryFile"])
        log.info(colored(f"⚡ Executing query from {entry['queryFile']}.graphql ...", 'cyan'))
        result = api.run_query(query, variables)
        if entry["queryFile"] == "fetchDGOParquetByHuc10":
            download_parquet_result(api, result, variables["huc10"])
        else:
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
