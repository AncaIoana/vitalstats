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
                                  silver.stg_blood_tests
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
│   └── workflows/
│       ├── ci.yml              # Run tests on every PR
│       └── pipeline.yml        # Scheduled data pipeline
├── ingestion/
│   ├── google_sheets/
│   │   ├── extract.py          # Google Sheets API ingestion
│   │   └── tests/
│   ├── config/
│   │   └── known_values.py     # Registry of expected analytes, sites, test types
│   ├── utils/
│   │   └── result_parser.py    # Parse "< 0.6", "negative", "48" etc.
│   ├── fitbit/                 # Phase 4
│   └── pdf_parser/             # Phase 4
├── dbt/
│   ├── models/
│   │   ├── staging/            # stg_blood_tests, stg_menoscale
│   │   ├── intermediate/       # int_blood_tests_normalised
│   │   └── marts/              # mart_blood_trends, mart_health_timeline, mart_ml_features
│   └── tests/
├── ml/
│   ├── anomaly_detection/      # Phase 3
│   ├── trend_analysis/         # Phase 3
│   └── llm_insights/           # Phase 3
├── infrastructure/
│   └── terraform/              # Phase 2
├── notebooks/
│   └── eda/
├── app/                        # Phase 5
├── docker/                     # Phase 2
├── docs/
│   ├── database-schema.md
│   ├── blood-tests-schema.md
│   ├── adr.md
│   └── project-plan.md
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
├── requirements.txt
├── Makefile
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
psql -U your_user -d vitalstats -f docs/database-schema.sql
```

### 5. Configure dbt

```bash
cd dbt
# Edit profiles.yml with your local PostgreSQL connection
uv run dbt debug  # verify connection
```

### 6. Run the pipeline

```bash
make ingest      # fetch from Google Sheets → raw tables
make transform   # run dbt models → silver + gold
make test        # run pytest + dbt tests
make report      # generate plain-text health summary
```

### 7. Kanban board

1. Install a modern Node from Homebrew (LTS line)

```
brew update
brew install node@22
```

1. Force-link that version so it is the active "node"

```
brew unlink node 2>/dev/null || true
brew link --overwrite --force node@22
```

1. Put node@22 bin first in PATH (choose ONE line)

Apple Silicon:

```
echo 'export PATH="/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zshrc
```

Intel Mac:

```
echo 'export PATH="/usr/local/opt/node@22/bin:$PATH"' >> ~/.zshrc
```

1. Reload shell and clear command cache

```
source ~/.zshrc
hash -r
```

1. Verify

```
type -a node
node -v
npm -v
```

1. Run

```
cd /Users/Poirot/vitalStats
npm create vite@latest vs-board -- --template react
cd vs-board
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

## Running tests

Install dependencies:
```bash
uv sync
```

Run all tests:
```bash
uv run pytest
```

Run with coverage:
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
