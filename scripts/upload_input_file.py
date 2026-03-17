"""Upload one or more input files to a report's S3 folder.

The report must be in CREATED state (not yet started) to accept input files.
After uploading all inputs call start_report.py to kick off processing.

Examples:
    # Upload a single file
    python scripts/upload_input_file.py staging <report-id> /path/to/data.gpkg inputs/data.gpkg

    # Upload multiple files (repeat --file)
    python scripts/upload_input_file.py staging <report-id> \\
        --file /path/to/data.gpkg inputs/data.gpkg \\
        --file /path/to/params.json inputs/params.json

    # Specify a different file type (default: INPUTS)
    python scripts/upload_input_file.py staging <report-id> /path/to/log.txt logs/run.txt --type LOG
"""
import argparse
import os
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Upload Input File')


def main():
    parser = argparse.ArgumentParser(description="Upload input file(s) to a report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report")
    # Positional convenience for single-file upload
    parser.add_argument('local_file', nargs='?', help="Local file path (single-file mode)")
    parser.add_argument('remote_path', nargs='?',
                        help="Destination path within the report's S3 folder (single-file mode)")
    # Multi-file mode
    parser.add_argument('--file', nargs=2, metavar=('LOCAL', 'REMOTE'), action='append', dest='files',
                        help="LOCAL_PATH REMOTE_PATH pair. Can be repeated for multiple files.")
    parser.add_argument('--type', default='INPUTS', dest='file_type',
                        choices=['INDEX', 'INPUTS', 'LOG', 'OUTPUTS', 'ZIP'],
                        help="File type enum (default: INPUTS)")
    args = parser.parse_args()

    # Assemble list of (local, remote) pairs
    uploads = []
    if args.local_file and args.remote_path:
        uploads.append((args.local_file, args.remote_path))
    if args.files:
        uploads.extend(args.files)

    if not uploads:
        parser.error("Provide either LOCAL_FILE REMOTE_PATH positional args or --file LOCAL REMOTE")

    # Validate local paths
    for local, _ in uploads:
        if not os.path.isfile(local):
            log.error(f"Local file not found: {local}")
            return

    with ReportsAPI(stage=args.stage) as api:
        report = api.get_report(args.report_id)
        log.title(f"Uploading files to report: {report.name} ({report.id})")
        log.info(f"  Current status: {report.status}")

        if report.status not in ('CREATED',):
            log.warning(f"Report is in '{report.status}' state — uploads are only expected before the report is started.")

        success = 0
        failed = 0
        for local_path, remote_path in uploads:
            try:
                api.upload_file(args.report_id, local_path, remote_path, args.file_type)
                log.info(colored(f"  ✓ {local_path} -> {remote_path}", 'green'))
                success += 1
            except Exception as e:
                log.error(f"  ✗ Failed: {local_path} -> {remote_path}: {e}")
                failed += 1

        log.info(f"Upload complete: {success} succeeded, {failed} failed")
        if failed == 0:
            print()
            print(f"Start the report:  python scripts/start_report.py {args.stage} {args.report_id}")


if __name__ == '__main__':
    main()
