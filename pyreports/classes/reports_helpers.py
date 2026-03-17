import re
from datetime import datetime
from dateutil.parser import parse as dateparse
from rsxml import Logger


def format_date(date: datetime) -> str:
    return date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3]


def verify_guid(guid: str) -> bool:
    return bool(re.match(r'^[a-f0-9-]{36}$', guid))


class RSReportType:
    """Helper class representing a report type from the Reports API."""

    def __init__(self, obj: dict):
        self.json = obj
        self.id = obj.get('id')
        self.name = obj.get('name')
        self.short_name = obj.get('shortName')
        self.description = obj.get('description')
        self.sub_header = obj.get('subHeader')
        self.version = obj.get('version')
        self.parameters = obj.get('parameters')

    def __repr__(self):
        return f"RSReportType(id={self.id!r}, name={self.name!r}, version={self.version!r})"


class RSReport:
    """Helper class representing a report record from the Reports API."""

    def __init__(self, obj: dict):
        log = Logger('RSReport')
        try:
            self.json = obj
            self.id = obj.get('id')
            self.name = obj.get('name')
            self.description = obj.get('description')
            self.status = obj.get('status')
            self.status_message = obj.get('statusMessage')
            self.progress = obj.get('progress', 0)
            self.outputs = obj.get('outputs', [])
            self.parameters = obj.get('parameters')
            self.extent = obj.get('extent')
            self.centroid = obj.get('centroid')

            self.created_at = dateparse(obj['createdAt']) if obj.get('createdAt') else None
            self.updated_at = dateparse(obj['updatedAt']) if obj.get('updatedAt') else None

            report_type_raw = obj.get('reportType')
            self.report_type = RSReportType(report_type_raw) if report_type_raw else None

            created_by_raw = obj.get('createdBy')
            self.created_by_id = created_by_raw.get('id') if created_by_raw else None
            self.created_by_name = created_by_raw.get('name') if created_by_raw else None

        except Exception as e:
            log.error(f"Error parsing RSReport: {e}")
            raise

    def is_complete(self) -> bool:
        return self.status == 'COMPLETE'

    def is_running(self) -> bool:
        return self.status in ('QUEUED', 'RUNNING')

    def is_failed(self) -> bool:
        return self.status in ('ERROR', 'STOPPED')

    def __repr__(self):
        return f"RSReport(id={self.id!r}, name={self.name!r}, status={self.status!r})"
