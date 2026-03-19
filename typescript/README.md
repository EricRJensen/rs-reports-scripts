# Riverscapes Reports Scripts — TypeScript

TypeScript/JavaScript client library for creating, managing, and monitoring reports via the
[Riverscapes Reports GraphQL API](https://api.reports.riverscapes.net).

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Node.js | ≥ 22 | Use `node --version` to check |
| npm | ≥ 9 | Bundled with Node.js |
| Internet access | — | Required for API calls and browser login |

> **No GraphQL experience required.** The `ReportsAPI` class wraps every
> query and mutation so you call ordinary async methods. See the
> [GraphQL Primer](#graphql-primer) section if you want to understand what
> is happening under the hood.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Riverscapes/rs-reports-scripts.git
cd rs-reports-scripts/typescript
```

### 2. Install dependencies

```bash
npm install
```

### 3. Build the library

```bash
npm run build
```

### 4. Format code (optional)

The TypeScript code follows the same formatting conventions as the
[rs-web-monorepo](https://github.com/Riverscapes/rs-web-monorepo): no
semicolons, single quotes, trailing commas (es5), 120-char line width.

```bash
npm run format
```

---

## Quick Start

Run the interactive report-creation script against the **staging** environment:

```bash
npx tsx scripts/createReport.ts staging
```

Or using the package.json script:

```bash
npm run create-report -- staging
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

When you use `ReportsAPI` without providing `machineAuth`, it starts a
temporary local web server, opens your browser to the Riverscapes Auth0 login
page, and captures the authorization code automatically via the OAuth 2.0
PKCE flow.

```typescript
import { ReportsAPI } from 'rs-reports'

const api = new ReportsAPI({ stage: 'production' })
await api.open()
try {
  const profile = await api.getProfile()
  console.log(profile.name)
} finally {
  api.close()
}
```

> **Port note:** The callback server listens on port `4721` by default.
> If that port is already in use, set the environment variable
> `RSAPI_ALTPORT=1` to use port `4723` instead.

### Machine (client-credentials) auth — for automated pipelines

For CI/CD or server-side scripts where no browser is available, pass
`machineAuth` with a client ID and secret issued by the Riverscapes team:

```typescript
const api = new ReportsAPI({
  stage: 'production',
  machineAuth: {
    clientId: 'YOUR_CLIENT_ID',
    secretId: 'YOUR_CLIENT_SECRET',
  },
})
await api.open()
```

Keep your credentials out of source code — load them from environment variables:

```typescript
const api = new ReportsAPI({
  stage: 'production',
  machineAuth: {
    clientId: process.env.RS_CLIENT_ID!,
    secretId: process.env.RS_CLIENT_SECRET!,
  },
})
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

1. **Query files** — GraphQL strings live in `src/graphql/` so they are
   readable and reusable, not buried in template literals.
2. **`runQuery()`** — handles setting the `Authorization` header, JSON
   encoding, error parsing, and automatic token refresh.
3. **Data classes** — raw objects from the API are wrapped in `RSReport` and
   `RSReportType`, giving you typed properties (`report.status`,
   `report.isComplete()`) instead of manual indexing.

### Exploring the schema

The full schema is at `src/graphql/rs-reports.schema.graphql`. You can
also introspect the live API with any GraphQL client (e.g.
[Altair](https://altairgraphql.dev/), [Insomnia](https://insomnia.rest/)) by
pointing it at the API URL and adding an `Authorization: Bearer <token>` header.

---

## Project Layout

```
typescript/
├── package.json                # Package metadata and dependencies
├── tsconfig.json               # TypeScript config (type-checking, VS Code)
├── tsconfig.build.json         # TypeScript config (build / emit)
├── .prettierrc.cjs             # Prettier formatting rules
│
├── src/
│   ├── index.ts                # Public exports
│   ├── ReportsAPI.ts           # Main API client class
│   ├── reportsHelpers.ts       # Data classes (RSReport, RSReportType) + utils
│   │
│   └── graphql/
│       ├── rs-reports.schema.graphql   # Full API schema
│       ├── queries/            # Read-only GraphQL operations
│       └── mutations/          # Write GraphQL operations
│
└── scripts/
    └── createReport.ts         # Interactive CLI script
```

### Key design decisions

- **GraphQL files are separate** from TypeScript code. This keeps queries
  readable, allows editor syntax highlighting, and means you can copy-paste
  them directly into a GraphQL client for testing.
- **`open()` / `close()`** — call `await api.open()` to authenticate and
  `api.close()` to clean up. Use a `try/finally` block.
- **`RSReport` and `RSReportType` classes** — wrap raw API objects and add
  helper methods like `isComplete()`, `isRunning()`, and `isFailed()`.
- **Formatting** matches the
  [rs-web-monorepo](https://github.com/Riverscapes/rs-web-monorepo)
  conventions: no semicolons, single quotes, trailing commas (es5), 120 chars.

---

## API Reference

### `new ReportsAPI({ stage, machineAuth?, devHeaders? })`

The main client class:

```typescript
const api = new ReportsAPI({ stage: 'production' })
await api.open()
try {
  // ...
} finally {
  api.close()
}
```

| Parameter | Type | Description |
|---|---|---|
| `stage` | `string` | `'production'`, `'staging'`, or `'local'` |
| `machineAuth` | `MachineAuth \| undefined` | `{ clientId, secretId }` for non-browser auth |
| `devHeaders` | `Record<string, string> \| undefined` | Raw headers for local dev |

---

### Profile

#### `api.getProfile(): Promise<Record<string, unknown>>`

Returns the authenticated user's profile (`id`, `name`, `email`, etc.).

```typescript
const profile = await api.getProfile()
console.log(profile.name)
```

---

### Report Types

#### `api.listReportTypes(): Promise<RSReportType[]>`

Returns all available report types.

```typescript
for (const rt of await api.listReportTypes()) {
  console.log(rt.id, rt.name, rt.version)
}
```

#### `api.getReportType(id): Promise<RSReportType>`

Fetch a single report type by its UUID.

---

### Reports

#### `api.listReports(limit?, offset?): Promise<{ reports, total }>`

Returns a page of the current user's reports plus the total count.

```typescript
const { reports, total } = await api.listReports(10, 0)
console.log(`Showing ${reports.length} of ${total}`)
```

#### `api.iterReports(pageSize?): AsyncGenerator<RSReport>`

Yields every report for the current user, handling pagination automatically.

```typescript
for await (const report of api.iterReports()) {
  console.log(report.id, report.status)
}
```

#### `api.getReport(reportId): Promise<RSReport>`

Fetch a single report by its UUID.

#### `api.globalReports(limit?, offset?): Promise<{ reports, total }>`

Admin method — returns reports across all users.

---

### Creating and Running a Report

The typical lifecycle is: **create → (attach inputs) → start → poll**.

#### `api.createReport({ name, reportTypeId, ... }): Promise<RSReport>`

Creates a new report with status `CREATED`.

```typescript
const report = await api.createReport({
  name: 'My Watershed Report',
  reportTypeId: '<uuid-of-report-type>',
  parameters: { units: 'imperial' },
})
```

#### `api.attachPickerOption(reportId, pickerLayer, pickerItemId): Promise<RSReport>`

Links a picker selection to the report.

#### `api.startReport(reportId): Promise<RSReport>`

Submits the report to the processing queue.

#### `api.stopReport(reportId): Promise<RSReport>`

Cancels a running report.

#### `api.deleteReport(reportId): Promise<RSReport>`

Permanently deletes a report and its stored files from S3.

---

### Polling

#### `api.pollReport(reportId, interval?, timeout?): Promise<RSReport>`

Blocks until the report reaches a terminal state, then returns the final `RSReport`.

```typescript
const report = await api.pollReport(report.id!, 10)
if (report.isComplete()) {
  console.log('Done!')
}
```

---

### File Operations

#### `api.uploadFile(reportId, localPath, remotePath, fileType?): Promise<boolean>`

Uploads a local file to the report's S3 storage with retry.

#### `api.getUploadUrls(reportId, filePaths, fileType?): Promise<Array<...>>`

Returns raw pre-signed S3 `PUT` URLs.

#### `api.getDownloadUrls(reportId, fileTypes?): Promise<Array<...>>`

Returns pre-signed S3 `GET` URLs for a report's files.

#### `api.downloadFile(url, localPath, force?): Promise<boolean>`

Downloads from a pre-signed URL to a local path.

---

### Report Status Values

| Status | Meaning |
|---|---|
| `CREATED` | Report exists but has not been started |
| `QUEUED` | Submitted, waiting for a processing slot |
| `RUNNING` | Currently being processed |
| `COMPLETE` | Finished successfully |
| `ERROR` | Processing failed — check `statusMessage` |
| `STOPPED` | Manually stopped by the user |
| `DELETED` | Report has been deleted |

---

### `RSReport` properties

| Property | Type | Description |
|---|---|---|
| `id` | `string \| undefined` | UUID |
| `name` | `string \| undefined` | Human-readable name |
| `description` | `string \| undefined` | Optional description |
| `status` | `string \| undefined` | See status values above |
| `statusMessage` | `string \| undefined` | Status detail |
| `progress` | `number` | 0–100 percentage |
| `parameters` | `Record \| undefined` | Input parameters |
| `outputs` | `unknown[]` | Output file metadata |
| `extent` | `Record \| undefined` | GeoJSON geometry |
| `centroid` | `Record \| undefined` | GeoJSON point |
| `createdAt` | `Date \| null` | Creation timestamp |
| `updatedAt` | `Date \| null` | Last-updated timestamp |
| `reportType` | `RSReportType \| null` | Embedded report type info |
| `createdById` | `string \| undefined` | Owner user ID |
| `createdByName` | `string \| undefined` | Owner display name |

Helper methods: `isComplete()`, `isRunning()`, `isFailed()`

---

## Writing Your Own Script

```typescript
import { ReportsAPI } from 'rs-reports'

const api = new ReportsAPI({ stage: 'production' })
await api.open()

try {
  // 1. Pick a report type
  const reportTypes = await api.listReportTypes()
  const rt = reportTypes.find((r) => r.shortName === 'watershed-summary')!

  // 2. Create the report
  let report = await api.createReport({
    name: 'My Test Report',
    reportTypeId: rt.id!,
    parameters: { units: 'imperial' },
  })

  // 3. Attach a picker selection
  await api.attachPickerOption(report.id!, 'huc', '1302020710')

  // 4. Start it
  report = await api.startReport(report.id!)

  // 5. Wait for completion
  report = await api.pollReport(report.id!, 10)

  if (report.isComplete()) {
    console.log('Report complete!')
    const urls = await api.getDownloadUrls(report.id!, ['OUTPUTS'])
    for (const item of urls) {
      await api.downloadFile(item.url, `/tmp/${(item as any).filePath}`)
    }
  } else {
    console.log(`Report failed: ${report.statusMessage}`)
  }
} finally {
  api.close()
}
```

### Calling a custom GraphQL query

```typescript
const result = await api.runQuery(
  `query MyCustomQuery($reportId: ID!) {
    report(reportId: $reportId) {
      id
      status
    }
  }`,
  { reportId: 'YOUR-REPORT-UUID' }
)
console.log((result as any).data.report)
```

---

## Troubleshooting

### `Port 4721 is already in use`

Set the environment variable to switch to the alternate port:

```bash
export RSAPI_ALTPORT=1
npx tsx scripts/createReport.ts staging
```

### `ReportsAPIException: You must be authenticated`

Your token expired and the library failed to refresh it. Try running the
script again — a fresh browser login will be triggered automatically.

### `Cannot find module`

Make sure you've run `npm install` and `npm run build` in this directory.

### GraphQL errors in the response

`ReportsAPIException` includes the raw `errors` array from the API in its
message. The most useful fields are `message` and `extensions.code`.

### Debugging raw HTTP traffic

Use the `NODE_DEBUG=http` environment variable or add console logging to your script.
