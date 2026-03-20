# vitalStats — Personal Health Intelligence Platform
### A Phased Project Plan for a Data Engineer

---

## Vision

A personal health data platform that ingests data from multiple sources (blood tests, wearables, nutrition, medical records), processes and stores it cleanly, and uses ML/AI to surface actionable, personalised health insights — *"your HbA1c has been trending up for 18 months, consider reviewing your carbohydrate intake"*.

Built entirely with free tools. Designed to grow.

---

## Guiding Principles

- **One thing at a time** — each phase delivers something working end-to-end before the next begins
- **Free tier first** — no paid services until you deliberately choose to upgrade
- **Production habits from day one** — git, tests, CI/CD even when it feels overkill
- **ML is the destination** — every engineering decision should make the ML layer easier to build later

---

## Technology Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11+ | You know it; dominant in ML/data |
| Dependency management | uv | Replaces pip + venv + pyenv in one tool; lock file guarantees reproducibility |
| Source control | Git + GitHub | Industry standard |
| Ingestion | Python + Google Sheets API | Free, structured, great starting point |
| Raw storage | AWS S3 (free tier) | Data lake pattern; 5GB free |
| Database | PostgreSQL on AWS RDS (free tier) | 750hrs/month free; production-grade |
| Transformation | dbt Core | You already know it; add tests here |
| Orchestration | GitHub Actions (Phase 1) → Apache Airflow (Phase 3) | Free CI/CD to start; Airflow is industry standard |
| ML | scikit-learn → then AWS SageMaker free tier | Progression from simple to cloud ML |
| AI/LLM | Claude API or OpenAI API (small free credits) | For plain-English health insights |
| Notebooks | Jupyter | EDA and analysis |
| Testing | pytest + dbt tests + GitHub Actions | Unit + data quality + integration |
| IaC | Terraform | Free; industry standard for AWS |
| Containers | Docker | Phase 2 onwards |
| Frontend | Streamlit (free tier) | Python-native, fast to build |

---

## Project Structure (Repository Layout)

```
vitalStats/
├── .github/
│   └── workflows/
│       ├── ci.yml              # Run tests on every PR
│       └── pipeline.yml        # Scheduled data pipeline run
├── ingestion/
│   ├── google_sheets/
│   │   ├── extract.py
│   │   └── tests/
│   ├── fitbit/                 # Phase 4
│   └── pdf_parser/             # Phase 4
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   └── tests/
├── ml/
│   ├── anomaly_detection/
│   ├── trend_analysis/
│   └── llm_insights/
├── infrastructure/
│   └── terraform/
├── notebooks/
│   └── eda/
├── app/                        # Phase 5
├── docker/                     # Phase 2
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
├── .env.example
├── requirements.txt
├── Makefile                    # make ingest, make test, make transform
└── README.md
```

---

## Phase 1 — Foundation: Blood Tests End-to-End
**Goal:** Working pipeline from Google Sheet → database → insight. No cloud yet. Just something real.
**Estimated time:** 4–6 weeks at your pace

### What you'll build
A Python script that reads your blood test Google Sheet, stores the raw data, transforms it with dbt, and outputs a simple trend analysis showing which markers are moving in the wrong direction.

### Step-by-step

**Week 1 — Setup & Ingestion**
1. Create GitHub repo, set up branch protection, write a `README.md`
2. Install uv, run `uv python pin 3.11`, `uv init` — commit `pyproject.toml` and `uv.lock` before any other code
3. Enable Google Sheets API; create a service account; store credentials in `.env`
4. Write `ingestion/google_sheets/extract.py`:
   - Reads your blood test sheet via the API
   - Validates the data (expected columns, date formats, numeric ranges)
   - Writes raw JSON to a local `/data/raw/` folder (S3 comes in Phase 2)
5. Write `pytest` unit tests for the extraction and validation logic
6. Commit with a proper `.gitignore` (never commit credentials, never commit `.venv/`)

**Week 2 — Local Database & dbt**
1. Install PostgreSQL locally (or use SQLite to start even simpler)
2. Write a loader script: raw JSON → `raw.blood_tests` table
3. Set up dbt Core project:
   - `staging/stg_blood_tests.sql` — clean column names, cast types, handle nulls
   - `intermediate/int_blood_tests_normalised.sql` — add reference range columns (e.g., is this value flagged high/low?)
   - `marts/mart_blood_trends.sql` — one row per marker per test date, with 3-month rolling average
4. Add dbt schema tests: `not_null`, `unique`, `accepted_values`
5. Add a custom dbt test: flag any value more than 2 standard deviations from your personal historical average

**Week 3 — Analysis & Output**
1. Jupyter notebook: `notebooks/eda/blood_test_analysis.ipynb`
   - Plot each marker over time
   - Highlight values outside reference range
   - Show trend direction (improving / stable / worsening)
2. Write a simple Python script `analysis/generate_report.py` that prints a plain-text summary:
   - "⚠️ HbA1c: trending UP over 6 readings — was 5.2 in Jan 2022, now 5.8"
   - "✅ Vitamin D: within range for last 4 tests"
   - "🔴 Ferritin: below range — last 3 tests"

**Week 4 — CI/CD & Testing**
1. Set up GitHub Actions: `.github/workflows/ci.yml`
   - On every push/PR: run `pytest`, run `dbt test`
   - Fail the PR if tests fail
2. Write integration tests: run the full pipeline on a small fixture dataset and assert the mart output looks correct
3. Write a `Makefile` with: `make ingest`, `make transform`, `make test`, `make report`

### ✅ Phase 1 Deliverables
- [ ] Google Sheets API ingestion working
- [ ] Raw data stored and versioned
- [ ] dbt models with data quality tests
- [ ] Trend analysis output with flags
- [ ] CI running on every commit
- [ ] README with setup instructions
- [ ] `.gitignore` covers credentials, `.env`, service account JSON
- [ ] Synthetic fixture files for all tests (no real health data in repo)
- [ ] Medications + vaccines ingestion (Phase 1b — after blood tests pipeline is stable)

---

## Phase 2 — Cloud & DevOps: Move to AWS
**Goal:** The same pipeline, but running in the cloud on a schedule. Learn Terraform + Docker + S3.
**Estimated time:** 4–6 weeks

### What you'll add
1. **Dockerise the ingestion + dbt pipeline** — `Dockerfile` + `docker-compose.yml`
2. **AWS S3 as raw data lake** — raw JSON files land in `s3://your-bucket/raw/blood_tests/YYYY-MM-DD/`
3. **AWS RDS PostgreSQL** — replace local Postgres (free tier: db.t3.micro)
4. **Terraform** — define all AWS resources as code (S3 bucket, RDS instance, IAM roles)
   - Learn: `terraform init`, `plan`, `apply`, `destroy`
   - Store state in S3 (Terraform remote backend)
5. **GitHub Actions scheduled pipeline** — runs every Sunday night; ingests, transforms, sends you an email summary via AWS SES (free tier)
6. **Secrets management** — AWS Parameter Store for credentials (not `.env` files)

### Security checklist for Phase 2
- AWS billing alerts set ($5 and $20 thresholds) before any resources are created
- IAM roles follow least privilege — separate roles per component (ingestion, dbt, ML)
- GitHub Actions uses OIDC for AWS authentication — no long-lived access keys in secrets
- RDS in private subnet — not publicly accessible
- S3 bucket has public access blocked explicitly in Terraform
- S3 encryption at rest enabled (one Terraform line)
- RDS encryption at rest enabled
- AWS CloudTrail enabled from day one
- Security groups: RDS accepts connections from VPC only

### New skills learned
- Docker multi-stage builds
- Terraform IaC workflow
- AWS IAM (roles, policies, least privilege)
- S3 data lake patterns (raw / processed / curated zones)
- Remote state management
- Scheduled CI/CD

---

## Phase 3 — ML Layer: Anomaly Detection & Trends
**Goal:** First real ML models on your blood test data.
**Estimated time:** 4–8 weeks

### Models to build (in order of complexity)

**3a. Rule-based baseline (not ML, but important)**
- Flag values outside NHS/standard reference ranges
- This is your baseline to beat with ML

**3b. Personal anomaly detection**
- Use `scikit-learn` Isolation Forest or z-score against *your own* historical data
- A value might be "in range" for the population but anomalous *for you*
- E.g., your ferritin is always 80–100, but now it's 45 — flag it even if 45 is technically "normal"

**3c. Trend forecasting**
- Use a simple time series model (statsmodels ARIMA, or Facebook Prophet — free)
- For each marker: "at current trend, your HbA1c will be 6.1 in 12 months"
- Prophet is very easy to get started with

**3d. LLM-powered plain English insights**
- Feed the structured output from 3a/3b/3c into Claude or GPT
- Prompt: *"Here are my blood test results with trend analysis. Act as a health-aware assistant. Summarise the 3 most important things I should discuss with my GP, and why."*
- This is your first AI feature — and it's genuinely useful
- Store all prompts/responses in the DB for auditability

**3e. Internet-sourced analyte enrichment (RAG)**
- Build a `gold.mart_analyte_reference` table: one row per analyte, with a plain-English description, what it measures, what high/low values mean, and which organs/systems it relates to
- Step 1: fetch definitions from trusted sources (NHS Inform, MedlinePlus, Lab Tests Online) and store them statically — no LLM needed yet
- Step 2: RAG pattern — retrieve the relevant reference content for a flagged analyte, inject it into an LLM prompt alongside your actual result, and generate a contextualised explanation: not just "cortisol is a stress hormone" but "your cortisol is at the high end of normal — here is what that may mean in context"
- All generated explanations stored in `gold.mart_insights` with the source URL that grounded them
- Always cite the source and include a disclaimer that outputs are informational, not medical advice

**3f. Airflow orchestration** (replaces GitHub Actions for pipeline runs)
- Install Apache Airflow locally or on a small EC2 (t2.micro free tier)
- DAG: `ingest → validate → transform → run_ml → generate_insights → notify`

### Security checklist for Phase 3
- Review what health data is sent in LLM API prompts — use anonymised or aggregated values where possible
- Store API keys for Claude/OpenAI in AWS Parameter Store, not in code or `.env`
- All LLM prompts and responses stored in `gold.mart_insights` for auditability

### New skills learned
- scikit-learn pipelines
- Time series modelling
- LLM prompt engineering
- Evaluating ML model output (how do you know if anomaly detection is working?)
- Airflow DAGs, sensors, operators

---

## Phase 4 — More Data Sources
**Goal:** Enrich the platform with wearable and lifestyle data to enable cross-source insights.
**Estimated time:** ongoing, one source at a time

### Sources (recommended order)

| Source | Method | Data available |
|---|---|---|
| **Fitbit** | Fitbit Web API (OAuth2) | Steps, sleep stages, heart rate, SpO2, HRV |
| **Flo** | GDPR JSON export (manual) | Cycle dates, period length, symptoms, mood, physical feelings |
| **Medical letters** | PDF parsing (pdfplumber / AWS Textract) | Diagnoses, medication, GP notes |
| **Google Fit / Health Connect** | Health Connect Android API or Google Takeout | Activity, weight, nutrition |
| **Zoe** | Manual export (CSV) or investigate their API | Gut health scores, food responses |
| **Medications & Vaccines Google Sheet** | Google Sheets API v4 | Medication history, dosage changes, vaccine records |
| **Blood tests Google Sheet** | Already done ✅ | |

### Cross-source ML opportunities
Once you have Fitbit + blood tests together:
- "Your HbA1c is highest in months where your average daily steps were below 5,000"
- "Your ferritin drops correlate with months of poor sleep (< 6.5 hrs avg)"
- "Your resting heart rate spikes 3 days after your cholesterol is elevated"

Once medications data is added:
- "Your ferritin improves when ferrous sulfate dose increases — current dose may be insufficient"
- "Your ALT elevation correlates with active Metyrapone periods — worth discussing with your endocrinologist"
- "Your cholesterol markers are within range while on Simvastatin — review if dose is still appropriate"
- Medication active flag becomes a feature in every blood test model — results should be interpreted in context of what you were taking

Once Flo is added:
- "Your ALT is consistently higher in the luteal phase of your cycle"
- "Your ferritin drops correlate with heavier periods — tracked in Flo"
- "Your MenoScale score is rising as your cycle becomes more irregular"
- Cycle phase becomes a feature in every ML model — enriching all blood test analysis with hormonal context

This is where the project gets genuinely interesting.

---

## Phase 5 — Frontend & App
**Goal:** A simple personal health dashboard.
**Estimated time:** 4–6 weeks

### Option A — Streamlit (recommended first)
- Python-native, fast to build, free to deploy on Streamlit Community Cloud
- Pages: Blood Test History, Trends, AI Insights, Add New Test
- No JavaScript required

### Option B — FastAPI + React (for more learning)
- FastAPI backend serving a REST API over your data
- React frontend (or Next.js)
- Learn: REST API design, CORS, authentication, deployment

### Security checklist for Phase 5
- Enable Streamlit built-in authentication — personal use only
- LLM API calls go through backend, never from browser
- HTTPS enforced (default on Streamlit Community Cloud)

### Features
- Interactive charts per blood marker over time
- Reference range overlays
- LLM insights panel (with a "regenerate" button)
- New data entry form (so you don't need to edit the Google Sheet manually)
- Export to PDF report

---

## Phase 6 — Streaming & Advanced (Future)
**Goal:** Real-time data, advanced ML, production-grade ops.

- **Streaming:** Fitbit intraday data → AWS Kinesis → real-time heart rate / activity dashboard
- **Feature store:** Store ML features properly (Feast — open source)
- **MLflow:** Track ML experiments, model versions, metrics
- **More LLMs:** RAG over your medical letters — ask "have I ever been prescribed X?" or "what did Dr Smith say about my knee in 2021?"
- **Logging & monitoring:** Structured logging (structlog), AWS CloudWatch, data quality alerts
- **Notifications:** AWS SNS — "your model flagged an anomaly in today's Fitbit data"

---

## Recommended Starting Order (First 2 Weeks)

1. **Day 1:** Create the GitHub repo. Set up the folder structure above. Write the README. Make your first commit.
2. **Day 2:** Enable Google Sheets API. Get credentials working. Write a script that can read one tab. Commit.
3. **Day 3–4:** Build the full extraction + validation script. Write unit tests with pytest.
4. **Day 5–7:** Install dbt Core locally. Model your blood test data into staging → mart.
5. **Week 2:** Add dbt tests. Set up GitHub Actions CI. Write integration tests. Run it all cleanly.

**By the end of week 2 you'll have:** a real, tested, version-controlled data pipeline with CI — which is more than most data projects ever get to.

---

## What Makes This Project Special for a Portfolio

Unlike toy datasets, this project:
- Uses **real APIs** (Google Sheets, Fitbit OAuth2)
- Has **genuine ML value** (anomaly detection on personal health data)
- Demonstrates **full stack thinking** (ingestion → storage → transformation → ML → output)
- Shows **production habits** (tests, CI, IaC, Docker)
- Is **genuinely expandable** — you'll never run out of things to add
- Has a **compelling story** — health data is universally relatable in interviews

---

## Summary: Phase Roadmap

```
Phase 1 (Now)     → Blood tests: Sheets → Postgres → dbt → trend analysis → CI/CD
Phase 2 (+6wks)   → Cloud: Docker + S3 + RDS + Terraform + scheduled pipeline
Phase 3 (+3mo)    → ML: anomaly detection + trend forecasting + LLM insights
Phase 4 (+4mo)    → More sources: Fitbit API + PDF medical letters + Health Connect
Phase 5 (+6mo)    → Frontend: Streamlit dashboard or FastAPI + React
Phase 6 (+9mo)    → Streaming, RAG, MLflow, feature store, monitoring
```

Every phase builds on the last. Every phase is completable at 4–6 hrs/week. And after Phase 3, you'll have something genuinely impressive to talk about.
