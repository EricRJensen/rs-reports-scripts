"""Stop a running report.

Examples:
    python scripts/stop_report.py staging <report-id>
"""
import argparse
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Stop Report')


def main():
    parser = argparse.ArgumentParser(description="Stop a running or queued report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report to stop")
    args = parser.parse_args()

    with ReportsAPI(stage=args.stage) as api:
        # Check current status first
        report = api.get_report(args.report_id)
        log.title(f"Stopping report: {report.name} ({report.id})")
        log.info(f"  Current status: {report.status}")

        if report.status not in ('RUNNING', 'QUEUED'):
            log.warning(f"Report is '{report.status}' — only RUNNING or QUEUED reports can be stopped.")
            return

        report = api.stop_report(args.report_id)
        log.info(colored(f"Report stopped. Status: {report.status}", 'yellow'))


if __name__ == '__main__':
    main()
