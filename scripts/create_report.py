"""Create a new report (status: CREATED).

After creation the report is in CREATED state. You can then:
  1. Upload any input files with upload_input_file.py
  2. Start the report with start_report.py

Examples:
    python scripts/create_report.py staging "My RME Report" <report-type-id>
    python scripts/create_report.py production "My Report" <report-type-id> --description "Annual run" --start
    python scripts/create_report.py staging "My Report" <report-type-id> --params '{"huc": "17060304"}'
    python scripts/create_report.py staging --list-types
"""
import argparse
import json
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Create Report')


def main():
    parser = argparse.ArgumentParser(description="Create a new report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('name', nargs='?', help="Human-readable report name")
    parser.add_argument('report_type_id', nargs='?', help="ID of the report type to run")
    parser.add_argument('--description', help="Optional description")
    parser.add_argument('--params', metavar='JSON', help='Optional JSON parameters for the report engine (e.g. \'{"huc": "17060304"}\')')
    parser.add_argument('--start', action='store_true', help="Immediately start the report after creating it (skips input upload)")
    parser.add_argument('--list-types', action='store_true', help="List available report types and exit")
    args = parser.parse_args()

    parameters = None
    if args.params:
        try:
            parameters = json.loads(args.params)
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON for --params: {e}")
            return

    with ReportsAPI(stage=args.stage) as api:
        if args.list_types:
            log.title(f"Available report types on {args.stage.upper()}")
            for rt in api.list_report_types():
                print(colored(f"  {rt.id}", 'blue') + f"  {rt.name} v{rt.version}")
                if rt.description:
                    print(f"    {rt.description}")
            return

        if not args.name or not args.report_type_id:
            parser.error("name and report_type_id are required when not using --list-types")

        log.title(f"Creating report on {args.stage.upper()}")
        report = api.create_report(
            name=args.name,
            report_type_id=args.report_type_id,
            description=args.description,
            parameters=parameters,
        )
        log.info(colored(f"Report created: {report.id}", 'green'))
        log.info(f"  Name:   {report.name}")
        log.info(f"  Status: {report.status}")
        log.info(f"  Type:   {report.report_type.name if report.report_type else report_type_id}")

        if args.start:
            log.info("Starting report...")
            report = api.start_report(report.id)
            log.info(colored(f"Report started. Status: {report.status}", 'cyan'))

        print()
        print(f"Report ID: {report.id}")
        print(f"Next steps:")
        if not args.start:
            print(f"  Upload inputs: python scripts/upload_input_file.py {args.stage} {report.id} <local_file> <remote_path>")
            print(f"  Start report:  python scripts/start_report.py {args.stage} {report.id}")
        print(f"  Check status:  python scripts/report_status.py {args.stage} {report.id}")


if __name__ == '__main__':
    main()
