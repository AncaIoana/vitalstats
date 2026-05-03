# vitalStats 💉

### Personal Health Intelligence Platform

A personal health data platform that ingests data from multiple sources, processes and stores it cleanly, and uses ML/AI to surface actionable, personalised health insights.

> *"Your HbA1c has been trending up for 18 months — consider reviewing your carbohydrate intake."*

---

## What it does

vitalStats ingests personal health data (blood tests, wearables, medical records), runs it through a structured data pipeline, and applies ML models and LLMs to generate plain-English health insights — the kind of summary you'd want before a GP appointment.

Built for one user. Designed to grow.

---

## Current status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Blood tests: Sheets → PostgreSQL → dbt → trend analysis | 🔨 In progress |
| Phase 2 | Cloud: Docker + S3 + RDS + Terraform + scheduled pipeline | ⏳ Planned |
| Phase 3 | ML: anomaly detection + trend forecasting + LLM insights | ⏳ Planned |
| Phase 4 | More sources: Fitbit + PDF medical letters + Health Connect | ⏳ Planned |
| Phase 5 | Frontend: Streamlit dashboard | ⏳ Planned |
| Phase 6 | Streaming, RAG, MLflow, feature store, monitoring | ⏳ Planned |

### Phase 1 progress

| Story | Description | Status |
|---|---|---|
| s53 | Set up .gitignore for credentials and sensitive files | ✅ Done |
| s54 | Create synthetic fixture data for all tests | ✅ Done |
| s01 | Create GitHub repo + folder structure | ✅ Done |
| s02 | Write README and project docs | ✅ Done |
| s12 | Set up local PostgreSQL + schemas | ✅ Done |
| s13 | Create pipeline_state + pipeline_run_log tables | ✅ Done |
| s03 | Enable Google Sheets API + service account | ✅ Done |
| s04 | Write extract_blood_tests.py for blood_tests_bulk | ✅ Done |
| s05 | Write extract_menoscale.py for menoscale tab | ✅ Done |
| s07 | Build result parser (parse_result.py) | ✅ Done |
| s08 | Build reference interval parser | ✅ Done |
| s06 | Implement hash-based deduplication | ✅ Done |
| s09 | Implement known values registry | ✅ Done |
| s10 | Implement unknown value detection + stg_unknown_values | ✅ Done |
| s11 | Implement error handling strategy | ✅ Done |
| s14 | Set up dbt Core project | ✅ Done |
---

## Architecture

vitalStats uses a **Medallion Architecture** — data flows through three layers, each progressively cleaner and more useful:

```
Google Sheets API  →  Python ingestion  →  S3 (Bronze)
                                              ↓
                                    raw.blood_tests_raw
                                              ↓
                                         dbt staging
                                              ↓
                                  silver.stg_google_sheets__blood_tests_vw
                                              ↓
                                          dbt marts
                                              ↓
                          gold.mart_blood_trends
                          gold.mart_health_timeline
                          gold.mart_ml_features
                          gold.mart_insights
```

- **Bronze (S3):** Raw, immutable archive of every ingested file. Never edited.
- **Silver (PostgreSQL):** Cleaned, typed, deduplicated, unit-normalised.
- **Gold (PostgreSQL):** Analytics-ready marts with business logic, ML features, and LLM outputs.

---

## Tech stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Dependency management | uv |
| Source control | Git + GitHub |
| Ingestion | Python + Google Sheets API v4 |
| Raw storage | AWS S3 |
| Database | PostgreSQL (local dev → AWS RDS) |
| Transformation | dbt Core |
| Orchestration | GitHub Actions → Apache Airflow (Phase 3) |
| ML | scikit-learn → AWS SageMaker |
| AI/LLM | Claude API |
| IaC | Terraform |
| Containers | Docker (Phase 2+) |
| Frontend | Streamlit (Phase 5) |
| Testing | pytest + dbt tests + GitHub Actions |

---

## Data sources

| Source | Method | Status |
|---|---|---|
| Blood tests (Google Sheets) | Google Sheets API v4 | Phase 1 |
| Medications & vaccines (Google Sheets) | Google Sheets API v4 | Phase 1b |
| MenoScale score (Google Sheets) | Google Sheets API v4 | Phase 1 |
| Fitbit | Fitbit Web API (OAuth2) | Phase 4 |
| Flo (women's health) | GDPR JSON export (manual) | Phase 4 |
| Medical letters | PDF parsing (pdfplumber / AWS Textract) | Phase 4 |
| Google Fit / Health Connect | Health Connect API / Google Takeout | Phase 4 |

---

## Repository structure

```
vitalStats/
├── .github/
│   └── workflows/                      # Phase 2
│       ├── ci.yml                      # CI + scheduled pipeline
│       └── pipeline.yml
├── ingestion/
│   ├── google_sheets/
│   │   ├── extract_blood_tests.py      # Blood tests ingestion
│   │   ├── extract_menoscale.py        # MenoScale ingestion
│   │   └── sheets_client.py
│   ├── config/
│   │   └── known_values.py             # Registry of expected analytes, sites, test types
│   ├── fitbit/                         # Phase 4
│   ├── pdf_parser/                     # Phase 4
│   └── utils/                          # Shared parsing utilities
│   │   ├── dates.py                    # Date parsing utilities
│   │   ├── hashing.py                  # Row hashing utilities
│   │   ├── pipeline.py                 # Shared pipeline utilities
│   │   ├── ref_interval_parser.py      # Parse a raw reference interval string
│   │   └── result_parser.py            # Parse a raw result string
├── dbt/
│   ├── dbt_project.yml                 # Project config (materializations, folders)
│   ├── models/
│   │   ├── sources.yml                 # Raw source table definitions
│   │   ├── staging/                    # stg_google_sheets__blood_tests_vw, stg_google_sheets__menoscale_vw
│   │   ├── intermediate/               # int_blood_tests_normalised_vw
│   │   └── marts/                      # mart_blood_trends, mart_health_timeline, mart_ml_features
│   └── tests/
├── infrastructure/
│   └── database/
│       ├── init_schemas.sql            # Creates raw/silver/gold schemas (run once)
│       └── create_ingestion_tables.sql # Ingestion-owned tables (run once)
│       └── terraform/                  # Phase 2 IaC (if present)
├── ml/
│   ├── anomaly_detection/
│   ├── trend_analysis/
│   └── llm_insights/
├── notebooks/
│   └── eda/
├── app/                                # Phase 5 (Streamlit)
├── docker/                             # Docker assets (Phase 2)
├── docs/
│   ├── adr.md
│   ├── database-schema.md
│   ├── blood-tests-schema.md
│   └── medications-vaccines-schema.md
├── tests/
│   ├── fixtures/
│   ├── unit/
│   └── integration/
├── vs-board/                           # Local kanban board (React + Vite)
├── .env.example
├── pyproject.toml
├── uv.lock
├── vitalstats-architecture.drawio      # Architecture diagram (project root)
└── README.md
```

---

## Key design decisions

All architectural decisions are documented in [`docs/adr.md`](docs/adr.md). Key ones:

- **Monorepo** — one repo, clean internal folder boundaries (ADR-010)
- **Medallion architecture** — Bronze/Silver/Gold separation (ADR-002)
- **Long/narrow schema** — one row per analyte, not one column per analyte (ADR-003)
- **Hash-based deduplication** — detects edits to past rows, not just new rows (ADR-005)
- **Unit normalisation** — everything converted to NHS/SI convention (mmol/L etc.) (ADR-011)
- **Two-tier error handling** — hard failures abort; soft failures skip and log (ADR-013)
- **Unknown value detection** — new analytes continue; new collection sites warn (ADR-014)
- **Pipeline state in PostgreSQL** — not DynamoDB; keep everything in one place (ADR-012)

---

## Local setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — handles Python version + all dependencies
- PostgreSQL (local)
- Google Sheets API credentials (see below)

Install uv if you don't have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then activate it and check the version
```
source $HOME/.local/bin/env
uv --version
```

And initialise the project
```
uv python pin 3.11
uv init --no-readme --no-workspace
```

Once set up, start the environment with
```
uv sync
```


### 1. Clone the repo

```bash
git clone https://github.com/your-username/vitalStats.git
cd vitalStats
```

### 2. Install Python + dependencies

uv reads `.python-version` and `uv.lock` to give you an identical environment on any machine:

```bash
uv sync        # installs correct Python version + all dependencies
```

That's it. No manual `pip install`, no `source venv/bin/activate`.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials — never commit this file
```

Required environment variables:

```
GOOGLE_SHEETS_CREDENTIALS=path/to/service-account.json
BLOOD_TESTS_SHEET_ID=your_sheet_id
DB_HOST=localhost
DB_PORT=5432
DB_NAME=vitalstats
DB_USER=your_user
DB_PASSWORD=your_password
```

### 4. Set up the database

```bash
# Create schemas (run once)
psql -d vitalstats -f infrastructure/database/init_schemas.sql
```

```
# Create ingestion-owned tables (run once)
psql -d vitalstats -f infrastructure/database/create_ingestion_tables.sql
```

dbt creates all Silver and Gold objects automatically on first dbt run — do not create them manually.

### 5. Configure dbt

```bash
cd dbt
# Edit profiles.yml with your local PostgreSQL connection
uv run dbt debug  # verify connection
```

### 6. Run the pipeline

```bash
# Ingest blood tests
uv run python -m ingestion.google_sheets.extract_blood_tests

# Ingest menoscale scores
uv run python -m ingestion.google_sheets.extract_menoscale
```

> A `Makefile` with shorthand commands (`make ingest`, `make test` etc.) is planned for a later story.

### 7. Kanban board

1. Install a modern Node from Homebrew (LTS line)

```
brew update
brew install node@22
```

2. Force-link that version so it is the active "node"

```
brew unlink node 2>/dev/null || true
brew link --overwrite --force node@22
```

3. Put node@22 bin first in PATH (choose ONE line)

Apple Silicon:

```
echo 'export PATH="/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zshrc
```

Intel Mac:

```
echo 'export PATH="/usr/local/opt/node@22/bin:$PATH"' >> ~/.zshrc
```

4. Reload shell and clear command cache

```
source ~/.zshrc
hash -r
```

5. Verify

```
type -a node
node -v
npm -v
```

6. Run

```
cd /Users/Poirot/vitalStats/vs-board
npm install
npm run dev
```

### Adding dependencies

```bash
uv add <package>            # production dependency
uv add --dev <package>      # development only (pytest, black, ruff etc.)
uv remove <package>         # remove a dependency
```

Always commit both `pyproject.toml` and `uv.lock` — the lock file is what guarantees reproducibility.

---

## Daily working session

Everything you need to do when you sit down to work.

### 1. Start PostgreSQL
```bash
brew services start postgresql@14
```

Verify it's running:
```bash
brew services list | grep postgres
```

You should see `started` next to your version.

### 2. Open the kanban board
```bash
cd /Users/anca/vitalStats/vs-board
npm install   # only needed first time or after pulling new dependencies
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173) in your browser.

### 3. Activate the project environment

All Python commands in this project are prefixed with `uv run` — no manual activation needed. But if you want shell completion or to run scripts directly:
```bash
cd /Users/anca/vitalStats
source .venv/bin/activate
```

### 4. Pick up where you left off

Check your current branch:
```bash
git status
git branch
```

Create a feature branch for a new story if starting something new:
```bash
git checkout dev
git pull
git checkout -b feature/your-story-name
```

---

## Adding new blood test / menoscale results

When you have new test results to add to the Google Sheet and want them ingested:

### 1. Add the results to the Google Sheet

Open your Blood Tests Google Sheet and add the new rows to the `blood_tests_bulk` tab. Make sure:
- Date is in `D-Mon-YYYY` format (e.g. `6-Apr-2023`)
- Test Type matches a known value exactly (see `ingestion/config/known_values.py`)
- Collection matches a known site exactly

### 2. Start PostgreSQL if not already running
```bash
brew services start postgresql@14
```

### 3. Run the ingestion pipeline
```bash
cd /Users/anca/vitalStats
uv run python -m ingestion.google_sheets.extract_blood_tests
uv run python -m ingestion.google_sheets.extract_menoscale
```

### 4. Check the output

The log output tells you what happened. A clean run looks like:

```
INFO Run started. run_id=... source=blood_tests_bulk
INFO Fetched 530 non-empty rows
INFO 6 new rows to insert, 524 duplicates skipped
INFO Raw JSON written to data/raw/blood_tests/YYYY-MM-DD/blood_tests_bulk.json
INFO Inserted 6 rows into raw.blood_tests_raw
INFO Run complete. status=success
```
### 5. Verify in the database
```bash
psql vitalstats -c "SELECT COUNT(*) FROM raw.blood_tests_raw;"
psql vitalstats -c "SELECT source, rows_fetched, rows_ingested, rows_skipped, status FROM raw.pipeline_run_log ORDER BY started_at DESC LIMIT 3;"
```

### 6. If you see a warning about an unknown test type or collection site

An unknown **test type** will abort the run. Check `ingestion/config/known_values.py` and add the new value, then re-run.

An unknown **collection site** will complete with `status=partial`. Review the entry in:

```bash
psql vitalstats -c "SELECT * FROM silver.stg_unknown_values WHERE resolved = FALSE;"
```

Follow the resolution workflow in `docs/blood-tests-schema.md` under *What happens when an unknown value is detected*.

## Running PostgreSQL

### 1. Make sure PostgreSQL is running

```bash
brew services list | grep postgres
```

If it's not running, then start it:

```bash
brew services start postgresql@14
```

### 2. Open an interactive session

```bash
psql -d vitalstats
```

### 3. Run the SQL queries

The terminal will now show `vitalstats=#` . Type SQL queries, making sure they are followed by `;`. For example:

```SQL
SELECT * FROM raw.blood_tests_raw
```

### 4. Exit the interactive session

To exit, just type `exit` in the session.

#### Alternative to the interactive session

```bash
psql vitalstats -c "SELECT * FROM silver.stg_unknown_values WHERE resolved = FALSE;"
```

## Running tests

Install dependencies:

```bash
uv sync
```

Run all tests:

```bash
uv run pytest
uv run pytest tests/unit/ -v
```

Run with coverage (shows percentage):

```bash
uv run pytest --cov=ingestion
```

All test data is synthetic. No real health data is used in tests.

---

## Data quality

The pipeline tracks data quality at every layer:

- **Ingestion:** validates expected columns, detects unknown analytes/collection sites, logs every skipped row with reason
- **Silver:** dbt `not_null`, `unique`, `accepted_values` tests on all staging models
- **Gold:** custom dbt tests for z-score computability, trend direction completeness
- **Pipeline monitoring:** every run logged to `raw.pipeline_run_log` with row counts and status (`success` / `partial` / `failed`)
- **Unknown values:** parked in `silver.stg_unknown_values` for manual review, with `risk_level` and `resolved` tracking

---

## Known data quirks

Documented fully in [`docs/blood-tests-schema.md`](docs/blood-tests-schema.md). Key ones:

- Synevo (Romania) reports in `mg/dL`; NHS labs report in `mmol/L` — all converted to NHS convention
- HbA1c: Synevo reports `%` (NGSP), NHS reports `mmol/mol` (IFCC) — different scales entirely
- Reference intervals are inconsistently formatted across labs — parsed into structured `ref_low`, `ref_high`, `ref_type`
- Some analyte names differ across labs but map to the same canonical slug
- Duplicate rows exist in source — caught by hash-based deduplication

---

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Always deployable; protected; PRs only |
| `dev` | Integration branch; feature branches merge here first |
| `feature/<name>` | Working branches, e.g. `feature/phase1-ingestion` |

---

## Licence

Personal project. Not intended for medical use. All AI-generated health insights are informational only and should not replace professional medical advice.
