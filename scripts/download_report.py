"""Download output files from a completed report.

Examples:
    # Download all output files
    python scripts/download_report.py staging <report-id> ./output/

    # Download only specific file types
    python scripts/download_report.py staging <report-id> ./output/ --types OUTPUTS ZIP

    # Force re-download even if files already exist
    python scripts/download_report.py staging <report-id> ./output/ --force
"""
import argparse
import os
from rsxml import Logger
from termcolor import colored
from pyreports import ReportsAPI

log = Logger('Download Report')


def main():
    parser = argparse.ArgumentParser(description="Download output files from a report.")
    parser.add_argument('stage', choices=['staging', 'production'], help="API stage")
    parser.add_argument('report_id', help="UUID of the report")
    parser.add_argument('output_dir', help="Local directory to download files into")
    parser.add_argument('--types', nargs='+', metavar='TYPE',
                        choices=['INDEX', 'INPUTS', 'LOG', 'OUTPUTS', 'ZIP'],
                        help="File type(s) to download (default: all)")
    parser.add_argument('--force', action='store_true',
                        help="Re-download files that already exist locally")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    with ReportsAPI(stage=args.stage) as api:
        report = api.get_report(args.report_id)
        log.title(f"Downloading files for report: {report.name} ({report.id})")
        log.info(f"  Status: {report.status}")
        log.info(f"  Output dir: {os.path.abspath(args.output_dir)}")

        if report.status != 'COMPLETE':
            log.warning(f"Report status is '{report.status}' — files may not be available yet.")

        file_types = args.types if args.types else None
        urls = api.get_download_urls(args.report_id, file_types)

        if not urls:
            log.warning("No download URLs returned. The report may not have any files yet.")
            return

        log.info(f"Found {len(urls)} file(s) to download")
        success = 0
        skipped = 0
        failed = 0

        for file_url_obj in urls:
            url = file_url_obj['url']
            file_type = file_url_obj.get('fileType', 'UNKNOWN')

            # Derive a filename from the URL (strip query string and S3 prefix)
            raw_path = url.split('?')[0].split('/')
            # Use the last two segments to preserve some folder structure
            rel_path = os.path.join(file_type.lower(), raw_path[-1]) if len(raw_path) > 1 else raw_path[-1]
            local_path = os.path.join(args.output_dir, rel_path)

            try:
                downloaded = api.download_file(url, local_path, force=args.force)
                if downloaded:
                    log.info(colored(f"  ✓ {rel_path}", 'green'))
                    success += 1
                else:
                    log.info(f"  - Skipped (exists): {rel_path}")
                    skipped += 1
            except Exception as e:
                log.error(f"  ✗ Failed: {rel_path}: {e}")
                failed += 1

        log.info(f"Download complete: {success} downloaded, {skipped} skipped, {failed} failed")


if __name__ == '__main__':
    main()
