"""Delete a report and all its associated S3 files.

WARNING: This is irreversible. The report record and all files in S3 will be
permanently deleted.

Examples:
    python scripts/delete_report.py staging <report-id>
    python scripts/delete_report.py staging <report-id> --yes
"""
import argparse
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Delete Report')


def main():
    parser = argparse.ArgumentParser(description="Delete a report and its files.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report to delete")
    parser.add_argument('--yes', action='store_true',
                        help="Skip confirmation prompt")
    args = parser.parse_args()

    with ReportsAPI(stage=args.stage) as api:
        report = api.get_report(args.report_id)
        log.title(f"Delete report: {report.name}")
        log.info(f"  ID:     {report.id}")
        log.info(f"  Status: {report.status}")

        if not args.yes:
            confirm = input(colored(f"\n  WARNING: This will permanently delete the report and all its files.\n  Type 'yes' to confirm: ", 'red'))
            if confirm.strip().lower() != 'yes':
                log.info("Deletion cancelled.")
                return

        deleted = api.delete_report(args.report_id)
        log.info(colored(f"Report deleted. Final status: {deleted.status}", 'magenta'))


if __name__ == '__main__':
    main()
