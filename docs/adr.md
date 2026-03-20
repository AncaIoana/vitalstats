# Architecture Decision Records (ADR)
### vitalStats Platform

ADRs document *why* key decisions were made, not just what was decided. This helps future-you understand the reasoning and make informed changes.

---

## ADR-001: Use PostgreSQL as the primary analytical database

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Need a persistent store for transformed health data that supports dbt, complex SQL queries, and eventually ML feature extraction.

**Decision:**  
Use PostgreSQL (local for development, AWS RDS free tier for production).

**Alternatives considered:**
- SQLite — too limited for production use; no concurrent connections; weaker SQL support
- Snowflake — overkill for personal data volume; costs money; not necessary until 10M+ rows
- DuckDB — great for analytics but not designed as a persistent operational store
- BigQuery — excellent but not free at scale; GCP not our chosen cloud

**Consequences:**
- Free tier on AWS RDS (db.t3.micro, 750hrs/month) covers all needs
- Can run identically locally and in production
- dbt Core has first-class PostgreSQL support
- Scalable path: can migrate dbt models to Snowflake/BigQuery later with minimal changes

---

## ADR-002: Use Medallion Architecture (Bronze / Silver / Gold)

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Multiple data sources (blood tests, Fitbit, PDFs, wearables) with different formats, schemas, and quality levels. Need a clear architectural pattern for data flow.

**Decision:**  
Adopt the Medallion Architecture:
- **Bronze (S3):** Raw, immutable archive of every ingested file
- **Silver (PostgreSQL `silver` schema):** Cleaned, typed, normalised
- **Gold (PostgreSQL `gold` schema):** Analytics/ML-ready marts

**Alternatives considered:**
- Single-layer (raw → analytics): Loses auditability; can't re-derive Gold from source
- Two-layer (raw → clean): Less clear separation; harder to add intermediate logic

**Consequences:**
- Every source lands in Bronze before PostgreSQL — full audit trail
- Can re-run any dbt model from scratch using Bronze as source
- Clear ownership: Python ingestion owns Bronze→Silver load; dbt owns Silver→Gold
- Slight overhead: more tables, but separation of concerns is worth it

---

## ADR-003: Use long/narrow schema for blood test storage

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Blood test data has ~80+ analytes but each test only measures a subset. Two schema options: wide (one column per analyte) or long (one row per analyte).

**Decision:**  
Store in long/narrow format in Silver (`stg_blood_tests`): one row per analyte per date.  
Pivot to wide format only in `mart_ml_features` (Gold) for ML use cases.

**Alternatives considered:**
- Wide format in Silver: Adding a new analyte requires a schema migration; lots of NULLs; dbt tests harder to write
- Wide format only: Can't easily query "all results for ferritin over time" without pivoting manually

**Consequences:**
- New analytes are added as new rows — no schema changes needed
- Easy to query trends: `WHERE analyte_slug = 'ferritin' ORDER BY test_date`
- ML features require a dbt PIVOT mart — this is expected and standard
- Reference range checks are simple: compare result against range on the same row

---

## ADR-004: Store reference ranges separately, not embedded in test rows

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
The source Google Sheet includes a `Reference Interval` column that varies by lab (Synevo vs NHS use different ranges), contains inconsistent formats (`"35-50"`, `"<35"`, `"0 (no AKI) to 3 (severe AKI)"`), and may be absent.

**Decision:**  
- Parse and store source reference intervals in Silver for auditability
- Maintain a canonical `gold.mart_reference_ranges` table as single source of truth
- ML and anomaly detection uses canonical ranges, not source ranges

**Consequences:**
- Canonical ranges can be updated without re-ingesting data
- Source ranges still preserved for audit / comparison
- Need to manually curate canonical ranges for ~80 analytes (one-time effort)
- Unit normalisation must happen before range comparison

---

## ADR-005: Use hash-based deduplication, not date watermarking alone

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Ingestion runs on a schedule. The source Google Sheet may have rows added, but also rows edited (correcting a past test result). Need to detect both.

**Decision:**  
Hash every row (SHA-256 of all fields) at ingestion. On each run, compare hashes against `raw.blood_tests_raw`. Only insert rows with new hashes.

Track pipeline state (`raw.pipeline_state`) including `last_run_at` and `row_count` for monitoring.

**Alternatives considered:**
- Date watermark only: misses edits to existing rows
- Full reload every time: simple, but doesn't scale; loses change history

**Consequences:**
- Edits to past rows are detected and re-ingested
- Can reconstruct history of changes to any result (useful for medical accuracy)
- Slightly more complex ingestion code, but well-contained in Python

---

## ADR-006: Use dbt Core (not dbt Cloud) for transformations

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
dbt is used for all Silver → Gold transformations. Two deployment options: dbt Core (open source, self-hosted) or dbt Cloud (hosted, free tier available).

**Decision:**  
Use dbt Core, run via GitHub Actions for scheduling.

**Alternatives considered:**
- dbt Cloud free tier: limited to 1 developer seat, 1 job; fine for now but creates dependency on a paid product later

**Consequences:**
- Full control; runs in Docker container in CI/CD
- GitHub Actions triggers dbt runs on schedule (or after ingestion)
- Local development identical to production

---

## ADR-007: Use AWS as cloud provider

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Project requires cloud storage, a managed database, and eventually compute for ML.

**Decision:**  
Use AWS. Key free tier services: S3 (5GB), RDS PostgreSQL (750hrs/month), Lambda (1M requests/month), SageMaker (free tier for training/inference).

**Alternatives considered:**
- GCP: Generous free tier; BigQuery is compelling; but less marketable than AWS for DE roles
- Azure: Less relevant for personal/DE projects; smaller free tier

**Consequences:**
- AWS credentials managed via IAM roles, not access keys where possible
- All infrastructure defined in Terraform (ADR-008)
- Free tier sufficient for all Phase 1–3 needs

---

## ADR-008: Use Terraform for all infrastructure

**Date:** 2026-03  
**Status:** Accepted (Phase 2)

**Context:**  
Cloud infrastructure (S3, RDS, IAM, etc.) needs to be reproducible, version-controlled, and destroyable.

**Decision:**  
Define all AWS resources in Terraform. State stored in S3 with DynamoDB locking.

**Alternatives considered:**
- AWS CDK: More powerful for app deployments; overkill for data infrastructure
- CloudFormation: Verbose; Terraform is more portable and learnable
- Manual console setup: Not reproducible; defeats learning objective

**Consequences:**
- Infrastructure is code — reviewed in PRs, rolled back via git
- `terraform destroy` removes everything cleanly (important for free tier cost management)
- Learning Terraform is directly applicable to professional DE/DevOps roles

---

## ADR-009: Use Streamlit for the initial frontend (Phase 5)

**Date:** 2026-03  
**Status:** Proposed

**Context:**  
Phase 5 requires a personal dashboard to visualise health data and display LLM insights.

**Decision:**  
Use Streamlit as the first frontend. Deploy on Streamlit Community Cloud (free).

**Rationale:**
- Python-native — no new language to learn for Phase 5
- Fast to build; can have a working dashboard in a few hours
- Free hosting on Streamlit Community Cloud
- Can be replaced with FastAPI + React in Phase 6 if needed

**Consequences:**
- Limited design flexibility vs. React
- Not suitable for a public multi-user app (fine for personal use)
- Acts as a rapid prototype — validates what views/metrics are most useful before investing in a full frontend

---

## ADR-010: Use a monorepo with disciplined internal structure

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Need to decide how to organise the codebase across multiple distinct components: ingestion, dbt transformations, ML models, infrastructure (Terraform), and eventually a frontend. Three options were considered.

**Decision:**  
Use a single monorepo (`vitalStats/`) with clearly separated internal folders, each treated as an independent module with its own README, dependencies, and tests.

**Alternatives considered:**

- **Polyrepo (one repo per component):** Clean separation and mirrors large team workflows, but creates significant coordination overhead for a solo developer. Cross-component changes (e.g. adding a new analyte requires ingestion + dbt + ML changes) would require PRs across multiple repos. Dependency management between repos is painful. Overkill until multiple teams are involved.

- **Microservices (separate repos + separately deployed services):** Maximum independence and the correct architecture for large production systems, but requires service discovery, inter-service communication, separate deployments, and per-service monitoring. Would mean spending 80% of time on infrastructure plumbing rather than building features. Not appropriate for a solo project at this scale.

**Consequences:**
- Simple to manage as a solo developer — one `git clone`, one CI pipeline, one place to look
- Cross-component refactoring is easy (e.g. moving a utility from ingestion to ML)
- Each internal folder (`ingestion/`, `dbt/`, `ml/`, `infrastructure/`, `app/`) has its own `README.md` and clear ownership boundaries
- If a component needs to be extracted into its own repo later, the clean folder structure makes that straightforward
- CI will run all tests on every push — acceptable at this scale; can be optimised with path filters in GitHub Actions if needed

**Branch strategy (agreed alongside this decision):**

| Branch | Purpose |
|---|---|
| `main` | Always deployable; protected; PRs only |
| `dev` | Integration branch; feature branches merge here first |
| `feature/<name>` | Working branches, e.g. `feature/phase1-ingestion` |

**Repository structure:**
```
vitalStats/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── pipeline.yml
├── ingestion/
│   ├── google_sheets/
│   ├── fitbit/              ← Phase 4
│   └── pdf_parser/          ← Phase 4
├── dbt/
│   └── models/
│       ├── staging/
│       ├── intermediate/
│       └── marts/
├── ml/
│   ├── anomaly_detection/
│   ├── trend_analysis/
│   └── llm_insights/
├── infrastructure/
│   └── terraform/
├── notebooks/
├── app/                     ← Phase 5
├── docs/
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example
├── requirements.txt
├── Makefile
└── README.md
```

---

## ADR-011: Normalise units to NHS convention (mmol/L system)

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Synevo lab (Romania) reports in mg/dL; NHS labs report in mmol/L. Same analyte, different values, can't be compared without conversion.

**Decision:**  
Canonical unit for all blood markers follows NHS/SI convention (mmol/L, μmol/L, g/L, etc.). Conversion happens in `silver.stg_blood_tests` dbt staging model.

**Consequences:**
- All downstream analysis uses consistent units
- Source unit and value preserved in raw/silver for auditability
- Conversion table maintained in `gold.mart_reference_ranges`
- HbA1c: special case — Synevo reports %, NHS reports mmol/mol — conversion formula documented in schema

---

## ADR-012: Use PostgreSQL for pipeline state and run logging, not DynamoDB

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
Need a place to track ingestion pipeline state (last run, row counts, success/failure) and a full log of every pipeline execution. DynamoDB was considered as an AWS-native, serverless alternative to storing this in PostgreSQL.

**Decision:**  
Use two PostgreSQL tables in the `raw` schema:
- `raw.pipeline_state` — one row per source, always reflects the latest run
- `raw.pipeline_run_log` — one row per execution, full history of every run

```sql
CREATE TABLE raw.pipeline_run_log (
    run_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source        TEXT NOT NULL,
    started_at    TIMESTAMP NOT NULL,
    finished_at   TIMESTAMP,
    rows_ingested INTEGER,
    rows_skipped  INTEGER,
    status        TEXT NOT NULL,   -- "success" | "failed" | "running"
    error_message TEXT
);
```

**Alternatives considered:**
- DynamoDB: AWS-native, generous free tier, high write throughput, integrates well with Lambda. But introduces a second storage technology with a different mental model (partition keys, no SQL, eventual consistency). Overkill for a pipeline that runs weekly. Splits operational state away from the rest of the data, making debugging harder.

**Consequences:**
- Pipeline state is queryable in plain SQL alongside all other data
- No new AWS service to configure, secure, or learn
- Full run history available for free in the same database
- Revisit DynamoDB in Phase 6 if moving to real-time streaming with high write throughput — at that point the tradeoff changes

---

## ADR-013: Error handling strategy for ingestion pipeline

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
The ingestion pipeline can fail in several distinct ways: the source is unreachable, the data structure is unexpected, individual rows are malformed, or the database write fails. Need a consistent strategy that is robust without being brittle.

**Decision:**  
Classify errors into two tiers and handle them differently:

**Hard failures — abort the entire run:**
- Source unreachable (API down, credentials expired, network error)
- Expected columns missing from source data
- Row count lower than previous run (suggests data was deleted from source — worth investigating)
- Database transaction failure

On a hard failure: log to `pipeline_run_log` with `status = "failed"`, full error message and traceback. Update `pipeline_state` to `status = "failed"`. Do not write any data to raw tables. Stop.

**Soft failures — skip the row, continue the run:**
- Individual row has an unparseable date
- Individual row has an unrecognised result format
- Individual row is missing a non-critical field

On a soft failure: log the row index, analyte, and reason to `pipeline_run_log.rows_skipped_detail` (JSONB). Increment `rows_failed` counter. Continue processing remaining rows. Final status is `"partial"` if any rows failed, `"success"` if all rows processed cleanly.

**All database writes are wrapped in a single transaction:**  
Either all rows for a run land, or none do. No partial loads.

**Run flow:**
```
start
  → set pipeline_state.status = "running"
  → fetch from source
      ✗ hard failure → log, set status = "failed", stop
  → validate structure
      ✗ hard failure → log, set status = "failed", stop
  → parse rows (row by row)
      ✗ soft failure per row → log to skipped_detail, continue
  → open DB transaction
      → insert valid rows into raw.blood_tests_raw
      → update pipeline_state
      ✗ DB error → rollback → log, set status = "failed", stop
  → commit
  → log to pipeline_run_log (rows_fetched, rows_ingested, rows_failed, status)
  → trigger dbt run
```

**Alternatives considered:**
- Abort on any single bad row: too brittle — one malformed row in 600 would block the entire pipeline indefinitely
- Ignore all errors silently: dangerous — bad data lands undetected, corrupts downstream models
- Separate error queue (e.g. SQS dead letter queue): overkill for this volume; JSONB column in pipeline_run_log achieves the same visibility without a new service

**Consequences:**
- Pipeline is resilient to occasional bad rows without silently swallowing problems
- Every skipped row is fully inspectable in SQL — nothing is lost
- `status = "partial"` makes it immediately obvious when a run was not fully clean
- Hard failure path ensures no half-written data ever reaches the raw tables
- Error traceback stored in DB means you don't need to dig through logs to diagnose failures

---

## ADR-014: Handle new analytes and collection sites differently

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
The source Google Sheet will occasionally contain values not seen before — a new analyte (e.g. cortisol added for the first time) or a new collection site (e.g. a new lab in a different country). These need to be detected and handled without breaking the pipeline or silently producing incorrect results.

**Decision:**  
Treat new analytes and new collection sites differently, because they carry different risk:

**New analyte — low risk, ingest and continue:**
- A new analyte is just a new row in a long/narrow schema — no schema change required (ADR-003)
- Ingest normally into `raw.blood_tests_raw` and `silver.stg_blood_tests`
- `is_in_range` will be NULL (no canonical reference range exists yet) — this is acceptable
- Log the new analyte to `silver.stg_unknown_values` for review
- Pipeline status remains `"success"`
- Action required: add the analyte to `gold.mart_reference_ranges` and `gold.mart_analyte_reference` at next opportunity

**New collection site — higher risk, ingest with warning:**
- A new site may use different units, different reference ranges, different analyte naming conventions
- Ingest the raw rows (never discard data) but flag every affected row in `silver.stg_unknown_values`
- Set `pipeline_run_log.status = "partial"` so the run is visibly not clean
- Log a clear warning with an example row
- Gold models should exclude unresolved rows from unknown sites until manually reviewed
- Action required: update `ingestion/config/known_values.py` with the new site and its unit conventions before the next run

**Known values registry:**  
Maintained in `ingestion/config/known_values.py`. This is the single source of truth for expected test types, collection sites, and their associated unit conventions. Updated manually when a new value is reviewed and resolved.

**Alternatives considered:**
- Fail hard on any unknown value: too brittle — a new analyte shouldn't block 600 existing rows from ingesting
- Silently accept all unknown values: dangerous — a new lab with different units would corrupt Gold without any warning

**Resolution workflow:**

*New analyte (low risk):*
1. Insert canonical range into `gold.mart_reference_ranges`
2. Fetch plain-English description into `gold.mart_analyte_reference`
3. Run `dbt run` — Gold marts pick up the new reference data automatically
4. Mark `stg_unknown_values.resolved = TRUE`

No raw or Silver data needs to change. dbt re-reads Silver with the new reference data available.

*New collection site (high risk):*
1. Update `ingestion/config/known_values.py` with the new site and its unit conventions
2. Update analyte slug mappings if the new lab uses different naming
3. Delete affected rows from `silver.stg_blood_tests` only — never touch `raw.blood_tests_raw`
4. Run `dbt run --full-refresh --select stg_blood_tests` — rebuilds Silver from raw with correct unit conversions applied to all historical rows
5. Run `dbt run` for downstream marts — Gold rebuilds from corrected Silver
6. Mark `stg_unknown_values.resolved = TRUE`

The `--full-refresh` flag is critical for new collection sites — it ensures the unit conversion is applied to all historical rows from that site, not just future ones.

**Key principle:** Raw is immutable. Silver is reprocessable. You can always delete Silver rows and rebuild them cleanly from raw because raw preserves everything.

**Consequences:**
- Pipeline never loses data due to an unknown value — raw always intact
- Unknown values are fully traceable via `run_id` FK to `pipeline_run_log`
- `risk_level` field makes the review backlog immediately prioritisable
- `resolved_at` timestamp gives a full audit trail of when issues were addressed
- Gold layer is protected from unreviewed unit or naming inconsistencies via the `resolved` flag
- Small manual overhead when a new site appears — acceptable given how rarely this happens

---

## ADR-015: Use uv for Python version and dependency management

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
The project needs to run identically across multiple machines (personal laptop, CI/CD, Docker). Python version and dependency management needs to be reproducible, fast, and low-friction. Several options were considered.

**Decision:**  
Use [uv](https://docs.astral.sh/uv/) as the single tool for Python version pinning, virtual environment management, and dependency management.

**Alternatives considered:**

- **pipenv:** Combines package management and virtual environments but has notoriously slow dependency resolution, patchy maintenance history, and poor compatibility with dbt and ML tooling. The data engineering community has largely moved away from it.

- **venv + pip + requirements.txt:** Universal and simple but no lock file by default, no clean separation of prod vs dev dependencies, manual to maintain. Fine for simple scripts; not robust enough for a multi-layer project.

- **pyenv + venv + pip-tools:** A solid pragmatic choice — each tool does one job. `pyenv` manages Python versions, `venv` creates environments, `pip-tools` compiles a locked `requirements.txt` from `requirements.in`. More setup overhead than uv with no meaningful advantage.

**Why uv:**
- Single tool replaces pyenv + venv + pip + pip-tools
- 10–100x faster than pip for dependency resolution (Rust-based)
- `uv sync` on any machine gives an identical environment from `uv.lock`
- `.python-version` file pins the exact Python version for the project
- `pyproject.toml` separates production and dev dependencies cleanly
- First-class Docker support — produces smaller, faster images
- Becoming the de facto standard for new Python projects as of 2024–2025

**Project setup:**
```toml
# pyproject.toml
[project]
name = "vitalstats"
requires-python = ">=3.11"
dependencies = [
    "pandas>=2.0",
    "psycopg2-binary",
    "google-auth",
    "google-auth-oauthlib",
    "google-api-python-client",
    "dbt-postgres",
    "boto3",
    "python-dotenv",
]

[tool.uv]
dev-dependencies = [
    "pytest",
    "pytest-cov",
    "black",
    "ruff",
]
```

**Daily workflow:**
```bash
uv sync                        # install everything from lock file
uv run python script.py        # run without activating environment
uv run pytest                  # run tests
uv add <package>               # add production dependency
uv add --dev <package>         # add dev-only dependency
```

**Reproducibility guarantee:**  
Both `pyproject.toml` and `uv.lock` are committed to git. Any `git clone` followed by `uv sync` produces a byte-for-byte identical environment regardless of machine or OS.

**Consequences:**
- Any machine with uv installed can reproduce the environment in one command
- CI/CD and Docker use the same lock file as local development
- No more "works on my machine" dependency issues
- Dev dependencies (pytest, black, ruff) never leak into production Docker images via `uv sync --no-dev`

---

## ADR-016: Security strategy — layered approach by phase

**Date:** 2026-03  
**Status:** Accepted

**Context:**  
vitalStats handles personal health data — one of the most sensitive categories of personal information. Security needs to be built in at each phase, not retrofitted later. Decisions need to cover secrets management, data privacy, AWS infrastructure security, and application security.

**Decision:**  
Apply a layered security strategy where each phase introduces the security controls appropriate for what is being built at that stage. Nothing is deferred that could cause irreversible harm (e.g. credential exposure). Nothing is over-engineered ahead of when it is needed.

---

**Phase 1 — Secrets and data hygiene (non-negotiable from day one)**

- `.gitignore` must cover `.env`, `*.json` (service account files), `*.pem`, `.venv/` before first commit
- `.env.example` with placeholder values is committed as documentation — never the real `.env`
- No credentials hardcoded anywhere in source code, even temporarily
- All test fixture files use **synthetic data** — fake dates, invented analyte values, fictional lab names. Real health data must never be committed to the repository, even in a private repo.
- Rationale for synthetic fixtures: test files are committed to git. Git history is permanent. A real health record committed once is effectively permanent even if later deleted.

**Phase 2 — AWS infrastructure security**

- **Billing alerts:** $5 and $20 thresholds set before any AWS resources are created. Alerts do not prevent charges — they notify. Essential for free tier management.
- **IAM least privilege:** separate IAM roles per component (ingestion, dbt, ML). Each role has only the permissions it needs. No role has admin access.
- **OIDC for CI/CD:** GitHub Actions authenticates to AWS via OpenID Connect rather than long-lived access keys stored in GitHub secrets. Keys stored in secrets can be leaked; OIDC tokens are short-lived and scoped.
- **Private networking:** RDS instance lives in a private subnet with no public accessibility. Security groups restrict inbound connections to VPC only.
- **Encryption at rest:** S3 and RDS both encrypted at rest. Free on AWS, one line each in Terraform. No reason not to.
- **S3 public access block:** explicitly set in Terraform — do not rely on account-level defaults.
- **AWS CloudTrail:** enabled from day one. Logs every API call. Free for management events. Invaluable for auditing and incident response.
- All of the above defined in Terraform so it is code-reviewed, version-controlled, and reproducible.

**Phase 3 — LLM data privacy**

- Review what health data is included in prompts before calling external LLM APIs (Claude, OpenAI)
- Prefer aggregated or anonymised values in prompts where clinically sufficient — e.g. "ferritin has been below range for 3 consecutive tests" rather than sending raw result history
- Store all prompts and responses in `gold.mart_insights` for full auditability
- LLM API keys stored in AWS Parameter Store, not in code or environment files

**Phase 5 — Application security**

- Streamlit built-in authentication is sufficient for a single-user personal app
- LLM API calls must go through a backend function — never expose API keys to the browser
- HTTPS enforced by default on Streamlit Community Cloud — verify before deploying

**Alternatives considered:**
- Applying all security controls in Phase 1: premature — private subnets and IAM roles are irrelevant before AWS exists
- Deferring secrets management: rejected — credential exposure is immediate and irreversible
- Using AWS Secrets Manager instead of Parameter Store: both are valid; Parameter Store free tier is sufficient for this volume of secrets; revisit if secret rotation becomes a requirement

**Consequences:**
- No credentials will ever be committed to the repository
- Real health data will never appear in test fixtures or commit history
- AWS infrastructure will be private, encrypted, and auditable from day one of Phase 2
- LLM prompts will be auditable and will not unnecessarily expose raw health records to third parties
- Security controls are in Terraform — reviewable, reproducible, destroyable cleanly

---

## ADR-017: Parser validation notifications for unexpected field values

**Date:** 2026-03  
**Status:** Accepted (implementation deferred to Phase 1b)

**Context:**  
The ingestion pipeline has hard failures (abort) and soft failures (skip row, log). But there is a third category: values that are technically parseable and don't break the pipeline, but are unexpected or suspicious — a date that parses but is implausible (e.g. year 0204), a medication frequency outside a normal range, a vaccine name that's close to a known slug but not an exact match. These currently pass through silently.

**Decision:**  
Add a **validation notification layer** to all ingestion scripts. This runs after parsing, before loading, and emits structured warnings for any field value that is parseable but suspicious. Warnings are:

- Written to `silver.stg_unknown_values` with `risk_level = "low"` and `field = "validation_warning"`
- Included in `pipeline_run_log.rows_skipped_detail` JSONB with `"type": "validation_warning"`
- Set `pipeline_run_log.status = "partial"` if any warnings were emitted

**What triggers a validation warning (not exhaustive — extended per source):**

*All sources:*
- Date parses but year < 2000 or year > current year + 1
- Date parses but is in the future by more than 2 years
- Any field value not in the known values registry (ADR-014)

*Blood tests:*
- Result numeric is an extreme outlier (> 10x the reference range high)
- Unit not in the canonical unit list for that analyte
- Reference interval format not matching any known pattern

*Medications:*
- Frequency per day > 10 (likely data entry error)
- End date before start date
- Medication name fuzzy-matches a known slug but is not an exact match (e.g. `"Ferrous sulfade"` vs `"ferrous_sulfate"`) — ingest with the correction applied, but log the original

*Vaccines:*
- Booster due year more than 30 years in the future
- Vaccine name not in the known vaccines registry
- Date given in the future

**Implementation:**

```python
def validate_field(field: str, value, rules: list[callable]) -> list[dict]:
    warnings = []
    for rule in rules:
        result = rule(value)
        if result:
            warnings.append({"field": field, "value": str(value), "reason": result})
    return warnings

# Example rules
def year_plausible(dt: date) -> str | None:
    if dt.year < 2000 or dt.year > date.today().year + 1:
        return f"Implausible year: {dt.year}"
    return None

def frequency_plausible(freq: float) -> str | None:
    if freq is not None and freq > 10:
        return f"Unusually high frequency: {freq} times/day"
    return None
```

All warnings are non-blocking. The row is still ingested. The warning is logged.

**Note:** The `"15-Feb-0204"` date in the medications source was a known entry error that has since been corrected in the source sheet. The parser correction (`if raw == "15-Feb-0204": return date(2024, 2, 15)`) can be removed once confirmed fixed. The year plausibility rule above would have caught this automatically.

**Alternatives considered:**
- Fail hard on implausible values: too brittle — a plausible-but-wrong date shouldn't block 200 rows
- Ignore suspicious values: dangerous — silent data quality issues are hard to detect downstream
- Separate validation service: overkill at this scale; JSONB column in pipeline_run_log is sufficient

**Consequences:**
- No data is ever lost due to a suspicious value — raw is always preserved
- Suspicious values are immediately visible in SQL without hunting through logs
- `status = "partial"` makes runs with warnings visibly distinct from clean runs
- Implementation is deferred to Phase 1b — Phase 1 uses the simpler hard/soft failure model only
