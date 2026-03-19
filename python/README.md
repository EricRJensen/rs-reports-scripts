# Riverscapes Reports Scripts — Python

Python client library for creating, managing, and monitoring reports via the
[Riverscapes Reports GraphQL API](https://api.reports.riverscapes.net).

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | Use `python --version` to check |
| [uv](https://docs.astral.sh/uv/) | latest | Required package manager |
| Internet access | — | Required for API calls and browser login |

> **No GraphQL experience required.** The `ReportsAPI` class wraps every
> query and mutation so you call ordinary Python methods. See the
> [GraphQL Primer](#graphql-primer) section if you want to understand what
> is happening under the hood.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Riverscapes/rs-reports-scripts.git
cd rs-reports-scripts/python
```

### 2. Install uv (if you don't have it)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows use the PowerShell installer from [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/).

### 3. Create the virtual environment and install dependencies

```bash
uv sync
```

`uv sync` reads `pyproject.toml`, creates a `.venv` folder, and installs
everything in one step. Run it again any time you pull new changes.

### 4. Verify the install

```bash
uv run python -c "from pyreports import ReportsAPI; print('OK')"
```

---

## Quick Start

Run the interactive report-creation script against the **staging** environment:

```bash
uv run python scripts/create_report.py staging
```

The script will:

1. Open a browser tab for you to log in with your Riverscapes account.
2. Present an interactive menu to select a report type.
3. Prompt for a report name, picker layer, and unit system.
4. Create the report, attach inputs, start it, and poll until it finishes.
5. Print a direct link to the finished report.

Use `production` instead of `staging` to target the live platform.

---

## Authentication

### Interactive (browser) login — for personal use

When you use `ReportsAPI` without providing `machine_auth`, it starts a
temporary local web server, opens your browser to the Riverscapes Auth0 login
page, and captures the authorization code automatically via the OAuth 2.0
PKCE flow.

```python
with ReportsAPI(stage='production') as api:
    # You will be prompted to log in via the browser once.
    # The access token is refreshed automatically in the background.
    profile = api.get_profile()
    print(profile['name'])
```

> **Port note:** The callback server listens on port `4721` by default.
> If that port is already in use, set the environment variable
> `RSAPI_ALTPORT=1` to use port `4723` instead.

### Machine (client-credentials) auth — for automated pipelines

For CI/CD or server-side scripts where no browser is available, pass a
`machine_auth` dict with a client ID and secret issued by the Riverscapes team:

```python
with ReportsAPI(
    stage='production',
    machine_auth={
        'clientId': 'YOUR_CLIENT_ID',
        'secretId': 'YOUR_CLIENT_SECRET',
    }
) as api:
    report = api.create_report(name='My Report', report_type_id='...')
```

Keep your credentials out of source code — load them from environment
variables or a secrets manager:

```python
import os

with ReportsAPI(
    stage='production',
    machine_auth={
        'clientId': os.environ['RS_CLIENT_ID'],
        'secretId': os.environ['RS_CLIENT_SECRET'],
    }
) as api:
    ...
```

---

## GraphQL Primer

> Skip this section if you only want to run the scripts.

### What is GraphQL?

GraphQL is a query language for APIs created by Meta. Instead of many REST
endpoints (`GET /reports`, `POST /reports/{id}/start`, …), a GraphQL API
exposes **a single endpoint** (e.g. `https://api.reports.riverscapes.net`).
Every request is a POST with a JSON body containing a `query` string and an
optional `variables` object.

### How does this library make it easier?

1. **Query files** — GraphQL strings live in `pyreports/graphql/` so they are
   readable and reusable, not buried in Python strings.
2. **`run_query()`** — handles setting the `Authorization` header, JSON
   encoding, error parsing, and automatic token refresh.
3. **Data classes** — raw dicts from the API are wrapped in `RSReport` and
   `RSReportType`, giving you typed attributes (`report.status`,
   `report.is_complete()`) instead of string indexing.

### Exploring the schema

The full schema is at `pyreports/graphql/rs-reports.schema.graphql`. You can
also introspect the live API with any GraphQL client (e.g.
[Altair](https://altairgraphql.dev/), [Insomnia](https://insomnia.rest/)) by
pointing it at the API URL and adding an `Authorization: Bearer <token>` header.

---

## Project Layout

```
python/
├── pyproject.toml              # Package metadata and dependencies
├── requirements.txt            # Pinned runtime dependencies
│
├── pyreports/                  # Installable Python package
│   ├── __init__.py             # Public exports: ReportsAPI, RSReport, RSReportType
│   ├── __version__.py          # Package version string
│   │
│   ├── classes/
│   │   ├── ReportsAPI.py       # Main API client class
│   │   └── reports_helpers.py  # Data classes (RSReport, RSReportType) + utils
│   │
│   └── graphql/
│       ├── rs-reports.schema.graphql   # Full API schema (for reference / IDE support)
│       ├── queries/            # Read-only GraphQL operations
│       └── mutations/          # Write GraphQL operations
│
└── scripts/
    └── create_report.py        # Interactive CLI script
```

### Key design decisions

- **GraphQL files are separate** from Python code. This keeps queries readable,
  allows editor syntax highlighting, and means you can copy-paste them
  directly into a GraphQL client for testing.
- **Context manager (`with` statement)** — `ReportsAPI` implements `__enter__`
  and `__exit__` so it authenticates on entry and cleanly cancels any
  background token-refresh timers on exit. Always use the `with` form.
- **`RSReport` and `RSReportType` data classes** — wrap raw API dicts and add
  helper methods like `is_complete()`, `is_running()`, and `is_failed()`.

---

## API Reference

### `ReportsAPI(stage, machine_auth=None, dev_headers=None)`

The main client class. Always use as a context manager:

```python
with ReportsAPI(stage='production') as api:
    ...
```

| Parameter | Type | Description |
|---|---|---|
| `stage` | `str` | `'production'`, `'staging'`, or `'local'` |
| `machine_auth` | `dict \| None` | `{'clientId': ..., 'secretId': ...}` for non-browser auth |
| `dev_headers` | `dict \| None` | Raw headers to inject (for local development / testing) |

---

### Profile

#### `api.get_profile() -> dict`

Returns the authenticated user's profile (`id`, `name`, `email`, etc.).

```python
profile = api.get_profile()
print(profile['name'])
```

---

### Report Types

#### `api.list_report_types() -> list[RSReportType]`

Returns all available report types.

```python
for rt in api.list_report_types():
    print(rt.id, rt.name, rt.version)
```

#### `api.get_report_type(report_type_id: str) -> RSReportType`

Fetch a single report type by its UUID.

---

### Reports

#### `api.list_reports(limit=50, offset=0) -> tuple[list[RSReport], int]`

Returns a page of the current user's reports plus the total count.

```python
reports, total = api.list_reports(limit=10, offset=0)
print(f"Showing {len(reports)} of {total}")
```

#### `api.iter_reports(page_size=50) -> Generator[RSReport]`

Yields every report for the current user, handling pagination automatically.

```python
for report in api.iter_reports():
    print(report.id, report.status)
```

#### `api.get_report(report_id: str) -> RSReport`

Fetch a single report by its UUID.

#### `api.global_reports(limit=50, offset=0) -> tuple[list[RSReport], int]`

Admin method — returns reports across all users.

---

### Creating and Running a Report

The typical lifecycle is: **create → (attach inputs) → start → poll**.

#### `api.create_report(name, report_type_id, description=None, parameters=None, extent=None) -> RSReport`

Creates a new report with status `CREATED`.

```python
report = api.create_report(
    name='My Watershed Report',
    report_type_id='<uuid-of-report-type>',
    parameters={'units': 'imperial'},
)
```

#### `api.attach_picker_option(report_id, picker_layer, picker_item_id) -> RSReport`

Links a picker selection to the report.

#### `api.start_report(report_id: str) -> RSReport`

Submits the report to the processing queue.

#### `api.stop_report(report_id: str) -> RSReport`

Cancels a running report.

#### `api.delete_report(report_id: str) -> RSReport`

Permanently deletes a report and its stored files from S3.

---

### Polling

#### `api.poll_report(report_id, interval=10, timeout=3600) -> RSReport`

Blocks until the report reaches a terminal state, then returns the final `RSReport`.

```python
report = api.poll_report(report.id, interval=10)
if report.is_complete():
    print("Done!")
```

---

### File Operations

#### `api.upload_file(report_id, local_path, remote_path, file_type='INPUTS') -> bool`

Uploads a local file to the report's S3 storage with retry.

#### `api.get_upload_urls(report_id, file_paths, file_type=None) -> list[dict]`

Returns raw pre-signed S3 `PUT` URLs.

#### `api.get_download_urls(report_id, file_types=None) -> list[dict]`

Returns pre-signed S3 `GET` URLs for a report's files.

#### `api.download_file(url, local_path, force=False) -> bool`

Downloads from a pre-signed URL to a local path.

---

### Report Status Values

| Status | Meaning |
|---|---|
| `CREATED` | Report exists but has not been started |
| `QUEUED` | Submitted, waiting for a processing slot |
| `RUNNING` | Currently being processed |
| `COMPLETE` | Finished successfully |
| `ERROR` | Processing failed — check `status_message` |
| `STOPPED` | Manually stopped by the user |
| `DELETED` | Report has been deleted |

---

### `RSReport` attributes

| Attribute | Type | Description |
|---|---|---|
| `id` | `str` | UUID |
| `name` | `str` | Human-readable name |
| `description` | `str \| None` | Optional description |
| `status` | `str` | See status values above |
| `status_message` | `str \| None` | Human-readable status detail |
| `progress` | `int` | 0–100 percentage |
| `parameters` | `dict \| None` | Input parameters |
| `outputs` | `list` | Output file metadata |
| `extent` | `dict \| None` | GeoJSON geometry of the report area |
| `centroid` | `dict \| None` | GeoJSON point centroid |
| `created_at` | `datetime \| None` | Creation timestamp |
| `updated_at` | `datetime \| None` | Last-updated timestamp |
| `report_type` | `RSReportType \| None` | Embedded report type info |
| `created_by_id` | `str \| None` | Owner user ID |
| `created_by_name` | `str \| None` | Owner display name |

Helper methods: `is_complete()`, `is_running()`, `is_failed()`

---

## Writing Your Own Script

```python
import os
from pyreports import ReportsAPI

with ReportsAPI(stage='production') as api:

    # 1. Pick a report type
    report_types = api.list_report_types()
    rt = next(r for r in report_types if r.short_name == 'watershed-summary')

    # 2. Create the report
    report = api.create_report(
        name='My Test Report',
        report_type_id=rt.id,
        parameters={'units': 'imperial'},
    )

    # 3. Attach a picker selection (if the report type requires it)
    api.attach_picker_option(report.id, 'huc', '1302020710')

    # 4. Start it
    report = api.start_report(report.id)

    # 5. Wait for completion
    report = api.poll_report(report.id, interval=10)

    if report.is_complete():
        print("Report complete!")
        for item in api.get_download_urls(report.id, file_types=['OUTPUTS']):
            api.download_file(item['url'], f"/tmp/{item['filePath']}")
    else:
        print(f"Report failed: {report.status_message}")
```

### Calling a custom GraphQL query

```python
with ReportsAPI(stage='production') as api:
    result = api.run_query(
        """
        query MyCustomQuery($reportId: ID!) {
          report(reportId: $reportId) {
            id
            status
          }
        }
        """,
        variables={'reportId': 'YOUR-REPORT-UUID'},
    )
    print(result['data']['report'])
```

---

## Troubleshooting

### `Port 4721 is already in use`

Set the environment variable to switch to the alternate port:

```bash
export RSAPI_ALTPORT=1
python scripts/create_report.py staging
```

### `ReportsAPIException: You must be authenticated`

Your token expired and the library failed to refresh it. Try running the
script again — a fresh browser login will be triggered automatically.

### `ModuleNotFoundError: No module named 'pyreports'`

The package is not installed. Run:

```bash
uv sync
```

Then check you are using the correct interpreter (the one in `.venv/`).
You can also prefix any command with `uv run`.

### GraphQL errors in the response

`ReportsAPIException` includes the raw `errors` array from the API in its
message. The most useful fields are `message` and `extensions.code`.

### Debugging raw HTTP traffic

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will print every HTTP request/response including headers (but not the
bearer token value) to stderr.
