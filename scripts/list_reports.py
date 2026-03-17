"""List all reports for the currently authenticated user.

Examples:
    python scripts/list_reports.py staging
    python scripts/list_reports.py production
    python scripts/list_reports.py staging --status CREATED QUEUED RUNNING
    python scripts/list_reports.py staging --report-type rme-report
"""
import argparse
import json
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI, RSReport

log = Logger('List Reports')

STATUS_COLORS = {
    'COMPLETE': 'green',
    'RUNNING': 'cyan',
    'QUEUED': 'yellow',
    'CREATED': 'white',
    'ERROR': 'red',
    'STOPPED': 'red',
    'DELETED': 'magenta',
    'UNKNOWN': 'grey',
}


def print_report(report: RSReport):
    color = STATUS_COLORS.get(report.status, 'white')
    type_str = f" [{report.report_type.short_name or report.report_type.name}]" if report.report_type else ""
    created = report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else 'unknown'
    status_str = f"{report.status} ({report.progress}%)" if report.status in ('RUNNING', 'QUEUED') else report.status
    print(colored(f"  {report.id}", 'blue') + f"  {report.name}{type_str}")
    print(colored(f"    Status: {status_str}", color) + f"  |  Created: {created}")
    if report.status_message:
        print(f"    Message: {report.status_message}")


def main():
    parser = argparse.ArgumentParser(description="List reports for the current user.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage to connect to")
    parser.add_argument('--status', nargs='+', metavar='STATUS',
                        help="Filter by status (e.g. CREATED QUEUED RUNNING COMPLETE ERROR)")
    parser.add_argument('--report-type', metavar='TYPE_ID',
                        help="Filter by report type ID")
    parser.add_argument('--limit', type=int, default=50, help="Page size (default: 50)")
    parser.add_argument('--json', action='store_true', help="Output raw JSON")
    args = parser.parse_args()

    status_filter = set(s.upper() for s in args.status) if args.status else None

    with ReportsAPI(stage=args.stage) as api:
        profile = api.get_profile()
        log.title(f"Reports for {profile['name']} on {args.stage.upper()}")

        all_reports = list(api.iter_reports(page_size=args.limit))

        # Apply filters
        if status_filter:
            all_reports = [r for r in all_reports if r.status in status_filter]
        if args.report_type:
            all_reports = [r for r in all_reports if r.report_type and r.report_type.id == args.report_type]

        log.info(f"Showing {len(all_reports)} report(s)")

        if args.json:
            print(json.dumps([r.json for r in all_reports], indent=2, default=str))
        else:
            for report in all_reports:
                print_report(report)

        log.info("Done")


if __name__ == '__main__':
    main()
