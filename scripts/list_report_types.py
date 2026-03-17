"""List all available report types.

Examples:
    python scripts/list_report_types.py staging
    python scripts/list_report_types.py production --json
"""
import argparse
import json
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Report Types')


def main():
    parser = argparse.ArgumentParser(description="List available report types.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('--json', action='store_true', help="Output raw JSON")
    args = parser.parse_args()

    with ReportsAPI(stage=args.stage) as api:
        log.title(f"Report Types on {args.stage.upper()}")
        report_types = api.list_report_types()
        log.info(f"Found {len(report_types)} report type(s)")

        if args.json:
            print(json.dumps([rt.json for rt in report_types], indent=2, default=str))
            return

        for rt in report_types:
            print(colored(f"\n  {rt.id}", 'blue') + f"  {rt.name} v{rt.version}")
            if rt.short_name:
                print(f"    Short name: {rt.short_name}")
            if rt.description:
                print(f"    {rt.description}")
            if rt.sub_header:
                print(f"    {rt.sub_header}")
            if rt.parameters:
                print(f"    Parameters schema: {json.dumps(rt.parameters, indent=6)}")


if __name__ == '__main__':
    main()
