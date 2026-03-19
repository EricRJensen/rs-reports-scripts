# Riverscapes Reports Scripts

Client libraries for creating, managing, and monitoring reports via the
[Riverscapes Reports GraphQL API](https://api.reports.riverscapes.net).

Available in **Python** and **TypeScript/JavaScript** — choose whichever
language fits your workflow. Both implementations offer identical functionality.

---

## What is this project?

The Riverscapes Reports platform generates map-based reports for river
and watershed science. This repository gives you:

| Component | Purpose |
|---|---|
| [`python/`](python/) | Installable Python package wrapping the Reports GraphQL API |
| [`typescript/`](typescript/) | TypeScript/JavaScript package wrapping the Reports GraphQL API |

You interact with the platform entirely through a **GraphQL API** — no manual
HTTP wrangling required. The client classes take care of authentication,
query execution, and error handling so your scripts can focus on business logic.

---

## Getting Started

Each language has its own README with full installation instructions, API
reference, examples, and troubleshooting:

- **[Python README](python/README.md)** — `pyreports` package, `uv` workflow, context-manager pattern
- **[TypeScript README](typescript/README.md)** — `rs-reports` package, `npm` workflow, `open()`/`close()` pattern

---

## Project Layout

```
rs-reports-scripts/
├── README.md                       ← you are here
├── graphql.config.json
│
├── python/                         # Python client
│   ├── README.md                   # Full Python documentation
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── pyreports/
│   │   ├── __init__.py
│   │   ├── classes/
│   │   │   ├── ReportsAPI.py       # Main API client class
│   │   │   └── reports_helpers.py  # Data classes + utils
│   │   └── graphql/                # GraphQL schema, queries, mutations
│   └── scripts/
│       └── create_report.py        # Interactive CLI script
│
└── typescript/                     # TypeScript/JavaScript client
    ├── README.md                   # Full TypeScript documentation
    ├── package.json
    ├── tsconfig.json
    ├── tsconfig.build.json
    ├── .prettierrc.cjs
    ├── src/
    │   ├── index.ts
    │   ├── ReportsAPI.ts           # Main API client class
    │   ├── reportsHelpers.ts       # Data classes + utils
    │   └── graphql/                # GraphQL schema, queries, mutations
    └── scripts/
        └── createReport.ts         # Interactive CLI script
```

---

## Authentication

Both clients support two authentication modes:

| Mode | Use case | How |
|---|---|---|
| **Interactive (browser)** | Personal scripts, local development | Opens a browser tab for OAuth 2.0 PKCE login |
| **Machine (client-credentials)** | CI/CD, automated pipelines | Pass `clientId` / `secretId` — no browser needed |

See the language-specific READMEs for code examples.

> **Port note:** The OAuth callback server listens on port `4721` by default.
> Set `RSAPI_ALTPORT=1` to use port `4723` instead.

---

## Report Lifecycle

The typical workflow is the same in both languages:

1. **Create** a report — registers it with status `CREATED`
2. **Attach** picker inputs (if the report type requires them)
3. **Start** the report — submits it to the processing queue
4. **Poll** until it reaches a terminal state (`COMPLETE`, `ERROR`, `STOPPED`)
5. **Download** output files (optional)

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

## GraphQL

Both clients load `.graphql` files from disk and execute them via a single
POST endpoint. The full schema is at `python/pyreports/graphql/rs-reports.schema.graphql`
(mirrored in `typescript/src/graphql/`).

You can also introspect the live API with any GraphQL client
([Altair](https://altairgraphql.dev/), [Insomnia](https://insomnia.rest/)) by
pointing it at the API URL with an `Authorization: Bearer <token>` header.
