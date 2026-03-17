"""Check the status of one or more reports.

Examples:
    python scripts/report_status.py staging <report-id>
    python scripts/report_status.py production <report-id> --poll
    python scripts/report_status.py staging <report-id> --poll --interval 30
"""
import argparse
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI, RSReport

log = Logger('Report Status')

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


def print_report_detail(report: RSReport):
    color = STATUS_COLORS.get(report.status, 'white')

    print()
    print(f"  Name:         {report.name}")
    print(f"  ID:           {report.id}")
    if report.report_type:
        print(f"  Report Type:  {report.report_type.name} (v{report.report_type.version})")
    print(colored(f"  Status:       {report.status}", color) + f"  ({report.progress}% complete)")
    if report.status_message:
        print(f"  Message:      {report.status_message}")
    print(f"  Created:      {report.created_at}")
    print(f"  Updated:      {report.updated_at}")
    if report.outputs:
        print(f"  Outputs:      {', '.join(report.outputs)}")
    if report.description:
        print(f"  Description:  {report.description}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Check the status of a report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report to check")
    parser.add_argument('--poll', action='store_true',
                        help="Keep polling until the report reaches a terminal state")
    parser.add_argument('--interval', type=int, default=10,
                        help="Seconds between polls when --poll is used (default: 10)")
    parser.add_argument('--timeout', type=int, default=3600,
                        help="Max seconds to wait when polling (default: 3600)")
    args = parser.parse_args()

    with ReportsAPI(stage=args.stage) as api:
        if args.poll:
            log.title(f"Polling report {args.report_id} on {args.stage.upper()}")
            report = api.poll_report(args.report_id, interval=args.interval, timeout=args.timeout)
            log.info(f"Final status: {report.status}")
        else:
            report = api.get_report(args.report_id)

        print_report_detail(report)


if __name__ == '__main__':
    main()
