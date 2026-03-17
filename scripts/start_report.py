"""Start a report (moves it from CREATED to QUEUED or RUNNING).

All input files should be uploaded before starting the report.

Examples:
    python scripts/start_report.py staging <report-id>
    python scripts/start_report.py production <report-id> --wait
    python scripts/start_report.py staging <report-id> --wait --interval 15
"""
import argparse
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Start Report')


def main():
    parser = argparse.ArgumentParser(description="Start a report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report to start")
    parser.add_argument('--wait', action='store_true',
                        help="Wait (poll) until the report reaches a terminal state")
    parser.add_argument('--interval', type=int, default=10,
                        help="Seconds between status checks when --wait is used (default: 10)")
    parser.add_argument('--timeout', type=int, default=3600,
                        help="Max seconds to wait when --wait is used (default: 3600)")
    args = parser.parse_args()

    with ReportsAPI(stage=args.stage) as api:
        log.title(f"Starting report {args.report_id} on {args.stage.upper()}")
        report = api.start_report(args.report_id)
        log.info(colored(f"Report started. Status: {report.status}", 'cyan'))

        if args.wait:
            log.info(f"Polling for completion (interval={args.interval}s, timeout={args.timeout}s)...")
            report = api.poll_report(args.report_id, interval=args.interval, timeout=args.timeout)

        color = 'green' if report.status == 'COMPLETE' else 'red' if report.status in ('ERROR', 'STOPPED') else 'cyan'
        log.info(colored(f"Final status: {report.status} ({report.progress}%)", color))
        if report.status_message:
            log.info(f"Message: {report.status_message}")

        if report.status == 'COMPLETE' and report.outputs:
            print()
            print(f"Outputs available: {', '.join(report.outputs)}")
            print(f"Download outputs: python scripts/download_report.py {args.stage} {args.report_id}")


if __name__ == '__main__':
    main()
