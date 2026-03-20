import { useState, useEffect, useCallback } from "react";

const PHASES = [
  { id: "phase1", label: "Phase 1", subtitle: "Blood Tests Pipeline", color: "#e8f4f0", accent: "#2d7d5f" },
  { id: "phase2", label: "Phase 2", subtitle: "Cloud & DevOps", color: "#f0f0f8", accent: "#4a4a9e" },
  { id: "phase3", label: "Phase 3", subtitle: "ML & AI", color: "#fdf4e8", accent: "#b8620a" },
  { id: "phase4", label: "Phase 4+", subtitle: "Sources & Frontend", color: "#faeef4", accent: "#9e2d5f" },
];

const STATUSES = ["backlog", "in_progress", "done"];
const STATUS_LABELS = { backlog: "Backlog", in_progress: "In Progress", done: "Done" };

const INITIAL_STORIES = [
  // Phase 1
  { id: "s01", phase: "phase1", epic: "Setup", title: "Create GitHub repo + folder structure", status: "backlog", priority: "high", notes: "Monorepo layout as per ADR-010. Set up branch protection, main/dev/feature branches." },
  { id: "s02", phase: "phase1", epic: "Setup", title: "Write README and project docs", status: "backlog", priority: "medium", notes: "Initial README with setup instructions. Upload project docs to Claude Project." },
  { id: "s03", phase: "phase1", epic: "Ingestion", title: "Enable Google Sheets API + service account", status: "backlog", priority: "high", notes: "Create service account, store credentials in .env. Never commit to git." },
  { id: "s04", phase: "phase1", epic: "Ingestion", title: "Write extract.py for blood_tests_bulk", status: "backlog", priority: "high", notes: "Read tab via API. Validate expected columns. Write raw JSON to /data/raw/." },
  { id: "s05", phase: "phase1", epic: "Ingestion", title: "Write extract.py for menoscale tab", status: "backlog", priority: "medium", notes: "Handle two date formats (hyphen + space). See blood-tests-schema.md for parser." },
  { id: "s06", phase: "phase1", epic: "Ingestion", title: "Implement hash-based deduplication", status: "backlog", priority: "high", notes: "SHA-256 hash of all fields. Compare against raw.blood_tests_raw on each run. ADR-005." },
  { id: "s07", phase: "phase1", epic: "Ingestion", title: "Build result parser (parse_result.py)", status: "backlog", priority: "high", notes: "Handle numeric, <value, >value, negative, Not Detected, free text. See blood-tests-schema.md." },
  { id: "s08", phase: "phase1", epic: "Ingestion", title: "Build reference interval parser", status: "backlog", priority: "medium", notes: "Handle range, lt, gt, N/A, narrative, Adults: pattern, empty." },
  { id: "s09", phase: "phase1", epic: "Ingestion", title: "Implement known values registry", status: "backlog", priority: "high", notes: "ingestion/config/known_values.py. Expected test types + collection sites. ADR-014." },
  { id: "s10", phase: "phase1", epic: "Ingestion", title: "Implement unknown value detection + stg_unknown_values", status: "backlog", priority: "high", notes: "Log unknown analytes/sites to silver.stg_unknown_values. risk_level, run_id FK. ADR-014." },
  { id: "s11", phase: "phase1", epic: "Ingestion", title: "Implement error handling strategy", status: "backlog", priority: "high", notes: "Hard vs soft failures. Atomic DB transactions. pipeline_run_log with rows_skipped_detail. ADR-013." },
  { id: "s12", phase: "phase1", epic: "Database", title: "Set up local PostgreSQL + schemas", status: "backlog", priority: "high", notes: "Create raw, silver, gold schemas. Run CREATE TABLE scripts from database-schema.md." },
  { id: "s13", phase: "phase1", epic: "Database", title: "Create pipeline_state + pipeline_run_log tables", status: "backlog", priority: "high", notes: "Two-table pattern. pipeline_state = current; pipeline_run_log = full history. ADR-012." },
  { id: "s14", phase: "phase1", epic: "dbt", title: "Set up dbt Core project", status: "backlog", priority: "high", notes: "dbt init, profiles.yml for local postgres, folder structure: staging/intermediate/marts." },
  { id: "s15", phase: "phase1", epic: "dbt", title: "Write stg_blood_tests.sql", status: "backlog", priority: "high", notes: "Clean columns, cast types, parse dates, generate analyte_slug, unit normalisation." },
  { id: "s16", phase: "phase1", epic: "dbt", title: "Write stg_menoscale.sql", status: "backlog", priority: "medium", notes: "Clean date, validate score 0-100." },
  { id: "s17", phase: "phase1", epic: "dbt", title: "Write int_blood_tests_normalised.sql", status: "backlog", priority: "high", notes: "Add reference range columns, is_in_range, is_flagged_high/low." },
  { id: "s18", phase: "phase1", epic: "dbt", title: "Write mart_blood_trends.sql", status: "backlog", priority: "high", notes: "Rolling avg 3m/6m, personal_mean, personal_stddev, z_score, trend_direction." },
  { id: "s19", phase: "phase1", epic: "dbt", title: "Write mart_health_timeline.sql", status: "backlog", priority: "medium", notes: "Unified event log. Blood tests + menoscale. Foundation for cross-source ML." },
  { id: "s20", phase: "phase1", epic: "dbt", title: "Add dbt schema tests", status: "backlog", priority: "high", notes: "not_null, unique, accepted_values. Custom test: z_score computable when reading_count >= 3." },
  { id: "s21", phase: "phase1", epic: "Analysis", title: "EDA notebook: blood_test_analysis.ipynb", status: "backlog", priority: "medium", notes: "Plot each marker over time. Highlight out-of-range. Show trend direction." },
  { id: "s22", phase: "phase1", epic: "Analysis", title: "Write generate_report.py", status: "backlog", priority: "medium", notes: "Plain-text summary: ⚠️ HbA1c trending up, ✅ Vitamin D in range, 🔴 Ferritin below range." },
  { id: "s23", phase: "phase1", epic: "CI/CD", title: "Set up GitHub Actions CI", status: "backlog", priority: "high", notes: ".github/workflows/ci.yml. On every PR: run pytest, run dbt test. Fail if tests fail." },
  { id: "s24", phase: "phase1", epic: "CI/CD", title: "Write unit tests (pytest)", status: "backlog", priority: "high", notes: "Test extract.py, parse_result.py, reference interval parser, dedup logic." },
  { id: "s25", phase: "phase1", epic: "CI/CD", title: "Write integration tests", status: "backlog", priority: "medium", notes: "Run full pipeline on fixture dataset. Assert mart output is correct." },
  { id: "s26", phase: "phase1", epic: "CI/CD", title: "Write Makefile", status: "backlog", priority: "low", notes: "make ingest, make transform, make test, make report." },

  // Phase 2
  { id: "s27", phase: "phase2", epic: "Docker", title: "Dockerise ingestion + dbt pipeline", status: "backlog", priority: "high", notes: "Dockerfile + docker-compose.yml. Multi-stage build." },
  { id: "s28", phase: "phase2", epic: "AWS", title: "Set up AWS account + free tier guardrails", status: "backlog", priority: "high", notes: "Billing alerts. IAM admin user. Never use root account day-to-day." },
  { id: "s29", phase: "phase2", epic: "Terraform", title: "Write Terraform for S3 raw bucket", status: "backlog", priority: "high", notes: "s3://vitalstats-raw. Versioning enabled. Remote state in S3 + DynamoDB lock." },
  { id: "s30", phase: "phase2", epic: "Terraform", title: "Write Terraform for RDS PostgreSQL", status: "backlog", priority: "high", notes: "db.t3.micro free tier. VPC, security groups, parameter groups." },
  { id: "s31", phase: "phase2", epic: "Terraform", title: "Write Terraform for IAM roles", status: "backlog", priority: "high", notes: "Least privilege. Separate roles for ingestion, dbt, ML." },
  { id: "s32", phase: "phase2", epic: "AWS", title: "Move raw storage from local to S3", status: "backlog", priority: "high", notes: "Update ingestion script to write to s3://vitalstats-raw/blood_tests/YYYY-MM-DD/." },
  { id: "s33", phase: "phase2", epic: "AWS", title: "Move database from local to RDS", status: "backlog", priority: "high", notes: "Update dbt profiles.yml and ingestion DB connection to RDS endpoint." },
  { id: "s34", phase: "phase2", epic: "AWS", title: "Secrets management via AWS Parameter Store", status: "backlog", priority: "medium", notes: "Replace .env files with Parameter Store. Update pipeline to fetch secrets at runtime." },
  { id: "s35", phase: "phase2", epic: "CI/CD", title: "Scheduled pipeline via GitHub Actions", status: "backlog", priority: "high", notes: "pipeline.yml. Runs every Sunday night. Ingest → transform → email summary via SES." },

  // Phase 3
  { id: "s36", phase: "phase3", epic: "ML", title: "Rule-based anomaly baseline", status: "backlog", priority: "high", notes: "Flag values outside canonical reference ranges. Baseline to beat with ML." },
  { id: "s37", phase: "phase3", epic: "ML", title: "Personal anomaly detection (Isolation Forest)", status: "backlog", priority: "high", notes: "scikit-learn. Z-score against personal history. A value in range may be anomalous for you." },
  { id: "s38", phase: "phase3", epic: "ML", title: "Trend forecasting (Prophet)", status: "backlog", priority: "medium", notes: "Per marker: 'at current trend, HbA1c will be X in 12 months'. Facebook Prophet." },
  { id: "s39", phase: "phase3", epic: "AI", title: "LLM-powered plain English insights", status: "backlog", priority: "high", notes: "Feed flagged results to Claude API. Store prompts/responses in gold.mart_insights. ADR TBD." },
  { id: "s40", phase: "phase3", epic: "AI", title: "Analyte enrichment — static fetch (RAG step 1)", status: "backlog", priority: "medium", notes: "Fetch from NHS Inform / MedlinePlus. Populate gold.mart_analyte_reference." },
  { id: "s41", phase: "phase3", epic: "AI", title: "Contextualised RAG explanations (RAG step 2)", status: "backlog", priority: "medium", notes: "Retrieve reference content, inject into prompt, generate contextualised explanation. Cite source." },
  { id: "s42", phase: "phase3", epic: "Orchestration", title: "Replace GitHub Actions with Airflow DAG", status: "backlog", priority: "medium", notes: "DAG: ingest → validate → transform → run_ml → generate_insights → notify." },

  // Phase 4+
  { id: "s43", phase: "phase4", epic: "Fitbit", title: "Fitbit OAuth2 integration", status: "backlog", priority: "medium", notes: "Fitbit Web API. Steps, sleep stages, heart rate, SpO2, HRV." },
  { id: "s44", phase: "phase4", epic: "Fitbit", title: "stg_fitbit_daily + stg_fitbit_sleep models", status: "backlog", priority: "medium", notes: "Silver staging models. Feed into mart_health_timeline." },
  { id: "s45", phase: "phase4", epic: "PDFs", title: "PDF parsing for medical letters", status: "backlog", priority: "low", notes: "pdfplumber or AWS Textract. Diagnoses, medication, GP notes." },
  { id: "s46", phase: "phase4", epic: "Frontend", title: "Streamlit dashboard — blood test history", status: "backlog", priority: "medium", notes: "Interactive charts per marker over time. Reference range overlays." },
  { id: "s47", phase: "phase4", epic: "Frontend", title: "Streamlit dashboard — AI insights panel", status: "backlog", priority: "medium", notes: "Display mart_insights. Regenerate button. Source citations." },
  { id: "s48", phase: "phase4", epic: "ML", title: "Cross-source ML: blood tests + Fitbit", status: "backlog", priority: "low", notes: "HbA1c vs steps. Ferritin vs sleep. Resting HR vs cholesterol. mart_ml_features pivot." },
  { id: "s49", phase: "phase4", epic: "Flo", title: "Parse Flo GDPR JSON export", status: "backlog", priority: "medium", notes: "Manual export from Flo app (Settings → Privacy → Export data). Parse cycles and symptoms into stg_flo_cycles and stg_flo_symptoms. Derive cycle_phase from cycle_start_date." },
  { id: "s50", phase: "phase4", epic: "Flo", title: "Add cycle phase as ML feature across all blood test models", status: "backlog", priority: "medium", notes: "Join stg_flo_cycles to mart_ml_features on date. cycle_phase becomes a feature in anomaly detection and trend models — adds hormonal context to every blood test result." },
  { id: "s51", phase: "phase4", epic: "Flo", title: "Cross-source ML: blood tests + Flo cycle data", status: "backlog", priority: "low", notes: "ALT vs cycle phase. Ferritin vs period heaviness. MenoScale score vs cycle regularity. Requires stg_flo_cycles + mart_ml_features." },
  { id: "s52", phase: "phase4", epic: "DevOps", title: "Explore migrating board to GitHub Projects", status: "backlog", priority: "low", notes: "Once active coding begins, GitHub Projects integrates with issues, PRs, and commits. More natural than a standalone board. Evaluate when Phase 1 is underway." },

  // Security — Phase 1
  { id: "s53", phase: "phase1", epic: "Security", title: "Set up .gitignore for credentials and sensitive files", status: "backlog", priority: "high", notes: "Must be done before first commit. Cover: .env, *.json (service accounts), *.pem, .venv/. Commit .env.example with placeholder values only. ADR-016." },
  { id: "s54", phase: "phase1", epic: "Security", title: "Create synthetic fixture data for all tests", status: "backlog", priority: "high", notes: "All pytest fixtures must use fake dates, invented analyte values, fictional lab names. Never commit real health data to the repo — even in a private repo. ADR-016." },

  // Security — Phase 2
  { id: "s55", phase: "phase2", epic: "Security", title: "Set AWS billing alerts ($5 and $20)", status: "backlog", priority: "high", notes: "Set before creating any AWS resources. AWS Billing console → Budgets. Alerts do not stop charges — they notify. Essential for free tier management. ADR-016." },
  { id: "s56", phase: "phase2", epic: "Security", title: "Implement IAM least privilege roles", status: "backlog", priority: "high", notes: "Separate IAM roles for ingestion, dbt, ML. Each role has only the permissions it needs. No admin roles. Define in Terraform. ADR-016." },
  { id: "s57", phase: "phase2", epic: "Security", title: "Set up OIDC for GitHub Actions → AWS auth", status: "backlog", priority: "high", notes: "Use OpenID Connect instead of long-lived access keys in GitHub secrets. OIDC tokens are short-lived and scoped. ADR-016." },
  { id: "s58", phase: "phase2", epic: "Security", title: "RDS in private subnet, no public access", status: "backlog", priority: "high", notes: "Private subnet, security group restricts inbound to VPC only. Defined in Terraform. ADR-016." },
  { id: "s59", phase: "phase2", epic: "Security", title: "Enable S3 + RDS encryption at rest", status: "backlog", priority: "high", notes: "Free on AWS. One line each in Terraform. S3: server-side encryption. RDS: storage_encrypted = true. Also block S3 public access explicitly. ADR-016." },
  { id: "s60", phase: "phase2", epic: "Security", title: "Enable AWS CloudTrail", status: "backlog", priority: "medium", notes: "Logs every AWS API call. Free for management events. Invaluable for auditing. Enable on day one of AWS setup. ADR-016." },
  { id: "s61", phase: "phase2", epic: "Security", title: "Migrate secrets from .env to AWS Parameter Store", status: "backlog", priority: "high", notes: "Replace .env files in production with Parameter Store. Update pipeline to fetch secrets at runtime. ADR-016." },

  // Security — Phase 3
  { id: "s62", phase: "phase3", epic: "Security", title: "Review health data in LLM prompts", status: "backlog", priority: "medium", notes: "Prefer aggregated values in prompts — e.g. 'ferritin below range for 3 tests' not raw history. Store all prompts + responses in gold.mart_insights. LLM API keys in Parameter Store. ADR-016." },
];

const PRIORITY_CONFIG = {
  high: { label: "High", color: "#dc2626", bg: "#fef2f2" },
  medium: { label: "Med", color: "#d97706", bg: "#fffbeb" },
  low: { label: "Low", color: "#6b7280", bg: "#f9fafb" },
};

const EPICS = [...new Set(INITIAL_STORIES.map(s => s.epic))];
const EPIC_COLORS = {};
const epicColorPalette = ["#e0f2fe","#dcfce7","#fef9c3","#fce7f3","#ede9fe","#ffedd5","#f0fdf4","#fff7ed"];
EPICS.forEach((e, i) => { EPIC_COLORS[e] = epicColorPalette[i % epicColorPalette.length]; });

export default function VitalStatsBoard() {
  const [stories, setStories] = useState(INITIAL_STORIES);
  const [loaded, setLoaded] = useState(false);
  const [selectedPhase, setSelectedPhase] = useState("phase1");
  const [filterEpic, setFilterEpic] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [editingStory, setEditingStory] = useState(null);
  const [addingStory, setAddingStory] = useState(null);
  const [newStoryStatus, setNewStoryStatus] = useState("backlog");
  const [saving, setSaving] = useState(false);
  const [draggedId, setDraggedId] = useState(null);

  // Load from storage
  useEffect(() => {
    (async () => {
      try {
        const result = await window.storage.get("vitalstats-stories");
        if (result?.value) setStories(JSON.parse(result.value));
      } catch (_) {}
      setLoaded(true);
    })();
  }, []);

  // Save to storage
  const save = useCallback(async (updated) => {
    setSaving(true);
    try {
      await window.storage.set("vitalstats-stories", JSON.stringify(updated));
    } catch (_) {}
    setTimeout(() => setSaving(false), 600);
  }, []);

  const updateStories = (updated) => {
    setStories(updated);
    save(updated);
  };

  const moveStory = (id, newStatus) => {
    updateStories(stories.map(s => s.id === id ? { ...s, status: newStatus } : s));
  };

  const saveEdit = (updated) => {
    updateStories(stories.map(s => s.id === updated.id ? updated : s));
    setEditingStory(null);
  };

  const deleteStory = (id) => {
    updateStories(stories.filter(s => s.id !== id));
    setEditingStory(null);
  };

  const addStory = (story) => {
    const id = "s" + Date.now();
    updateStories([...stories, { ...story, id, phase: selectedPhase, status: newStoryStatus }]);
    setAddingStory(null);
  };

  const resetToDefault = async () => {
    if (window.confirm("Reset all stories to the default plan? This cannot be undone.")) {
      updateStories(INITIAL_STORIES);
    }
  };

  const phaseStories = stories.filter(s => {
    if (s.phase !== selectedPhase) return false;
    if (filterEpic !== "all" && s.epic !== filterEpic) return false;
    if (filterPriority !== "all" && s.priority !== filterPriority) return false;
    return true;
  });

  const phaseEpics = [...new Set(stories.filter(s => s.phase === selectedPhase).map(s => s.epic))];

  const counts = STATUSES.reduce((acc, st) => {
    acc[st] = phaseStories.filter(s => s.status === st).length;
    return acc;
  }, {});

  const totalByPhase = PHASES.map(p => ({
    ...p,
    total: stories.filter(s => s.phase === p.id).length,
    done: stories.filter(s => s.phase === p.id && s.status === "done").length,
  }));

  if (!loaded) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", fontFamily: "monospace", color: "#666" }}>
      Loading vitalStats board...
    </div>
  );

  return (
    <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", background: "#f7f7f5", minHeight: "100vh", color: "#1a1a1a" }}>
      {/* Header */}
      <div style={{ background: "#1a1a2e", color: "white", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 32, height: 32, background: "linear-gradient(135deg, #2d7d5f, #4a4a9e)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>💉</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18, letterSpacing: "-0.5px" }}>vitalStats</div>
            <div style={{ fontSize: 11, opacity: 0.6, marginTop: -2 }}>project board</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 12, opacity: saving ? 1 : 0, color: "#86efac", transition: "opacity 0.3s" }}>● saved</div>
          <button onClick={resetToDefault} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.7)", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer" }}>Reset</button>
        </div>
      </div>

      {/* Phase summary bar */}
      <div style={{ background: "white", borderBottom: "1px solid #e5e5e5", padding: "0 24px", display: "flex", gap: 0 }}>
        {totalByPhase.map(p => (
          <button key={p.id} onClick={() => { setSelectedPhase(p.id); setFilterEpic("all"); }}
            style={{ padding: "12px 20px", border: "none", background: "transparent", cursor: "pointer", borderBottom: selectedPhase === p.id ? `3px solid ${p.accent}` : "3px solid transparent", fontWeight: selectedPhase === p.id ? 600 : 400, color: selectedPhase === p.id ? p.accent : "#666", fontSize: 13, display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2 }}>
            <span>{p.label}</span>
            <span style={{ fontSize: 10, color: "#999", fontWeight: 400 }}>{p.done}/{p.total} done</span>
          </button>
        ))}
      </div>

      {/* Phase header + filters */}
      <div style={{ padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{PHASES.find(p => p.id === selectedPhase)?.label} — {PHASES.find(p => p.id === selectedPhase)?.subtitle}</h2>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "#888" }}>{counts.backlog} backlog · {counts.in_progress} in progress · {counts.done} done</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <select value={filterEpic} onChange={e => setFilterEpic(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #e0e0e0", fontSize: 12, background: "white", cursor: "pointer" }}>
            <option value="all">All epics</option>
            {phaseEpics.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
          <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid #e0e0e0", fontSize: 12, background: "white", cursor: "pointer" }}>
            <option value="all">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Board columns */}
      <div style={{ padding: "0 24px 32px", display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        {STATUSES.map(status => (
          <div key={status}
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); if (draggedId) { moveStory(draggedId, status); setDraggedId(null); } }}
            style={{ background: status === "in_progress" ? "#fffbf0" : status === "done" ? "#f0fdf4" : "#f7f7f5", borderRadius: 10, border: `1px solid ${status === "in_progress" ? "#fde68a" : status === "done" ? "#bbf7d0" : "#e5e5e5"}`, minHeight: 200 }}>
            {/* Column header */}
            <div style={{ padding: "12px 14px", borderBottom: `1px solid ${status === "in_progress" ? "#fde68a" : status === "done" ? "#bbf7d0" : "#e5e5e5"}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600, fontSize: 13, color: status === "in_progress" ? "#92400e" : status === "done" ? "#166534" : "#555" }}>
                {STATUS_LABELS[status]}
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ background: status === "in_progress" ? "#fde68a" : status === "done" ? "#bbf7d0" : "#e5e5e5", borderRadius: 10, padding: "1px 8px", fontSize: 11, fontWeight: 600, color: "#555" }}>
                  {counts[status]}
                </span>
                <button onClick={() => { setAddingStory({ epic: phaseEpics[0] || "Setup", title: "", priority: "medium", notes: "" }); setNewStoryStatus(status); }}
                  style={{ background: "transparent", border: "none", cursor: "pointer", fontSize: 16, color: "#aaa", lineHeight: 1, padding: "0 2px" }} title="Add story">+</button>
              </div>
            </div>

            {/* Cards */}
            <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {phaseStories.filter(s => s.status === status).map(story => (
                <div key={story.id} draggable
                  onDragStart={() => setDraggedId(story.id)}
                  onDragEnd={() => setDraggedId(null)}
                  style={{ background: "white", borderRadius: 8, padding: "10px 12px", boxShadow: "0 1px 3px rgba(0,0,0,0.08)", border: "1px solid #eee", cursor: "grab", opacity: draggedId === story.id ? 0.5 : 1, transition: "opacity 0.15s" }}>
                  {/* Epic tag */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ background: EPIC_COLORS[story.epic], color: "#444", fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 4, letterSpacing: "0.3px" }}>
                      {story.epic}
                    </span>
                    <span style={{ background: PRIORITY_CONFIG[story.priority].bg, color: PRIORITY_CONFIG[story.priority].color, fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 4 }}>
                      {PRIORITY_CONFIG[story.priority].label}
                    </span>
                  </div>
                  {/* Title */}
                  <div style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.4, marginBottom: story.notes ? 6 : 0 }}>{story.title}</div>
                  {/* Notes preview */}
                  {story.notes && <div style={{ fontSize: 11, color: "#888", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{story.notes}</div>}
                  {/* Actions */}
                  <div style={{ marginTop: 8, display: "flex", gap: 4 }}>
                    {STATUSES.filter(s => s !== status).map(s => (
                      <button key={s} onClick={() => moveStory(story.id, s)}
                        style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, border: "1px solid #e0e0e0", background: "white", cursor: "pointer", color: "#666" }}>
                        → {STATUS_LABELS[s]}
                      </button>
                    ))}
                    <button onClick={() => setEditingStory({ ...story })}
                      style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, border: "1px solid #e0e0e0", background: "white", cursor: "pointer", color: "#666", marginLeft: "auto" }}>
                      Edit
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Edit modal */}
      {editingStory && (
        <Modal title="Edit Story" onClose={() => setEditingStory(null)}>
          <StoryForm story={editingStory} epics={phaseEpics} onChange={setEditingStory}
            onSave={() => saveEdit(editingStory)}
            onDelete={() => { if (window.confirm("Delete this story?")) deleteStory(editingStory.id); }}
            onClose={() => setEditingStory(null)} />
        </Modal>
      )}

      {/* Add modal */}
      {addingStory && (
        <Modal title="Add Story" onClose={() => setAddingStory(null)}>
          <StoryForm story={addingStory} epics={phaseEpics} onChange={setAddingStory}
            onSave={() => addStory(addingStory)}
            onClose={() => setAddingStory(null)} />
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100, padding: 16 }}>
      <div style={{ background: "white", borderRadius: 12, width: "100%", maxWidth: 480, boxShadow: "0 20px 60px rgba(0,0,0,0.2)" }}>
        <div style={{ padding: "16px 20px", borderBottom: "1px solid #eee", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontWeight: 600, fontSize: 15 }}>{title}</span>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "#999" }}>×</button>
        </div>
        <div style={{ padding: 20 }}>{children}</div>
      </div>
    </div>
  );
}

function StoryForm({ story, epics, onChange, onSave, onDelete, onClose }) {
  const field = (label, key, type = "text", options = null) => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#555", marginBottom: 4 }}>{label}</label>
      {options ? (
        <select value={story[key]} onChange={e => onChange({ ...story, [key]: e.target.value })}
          style={{ width: "100%", padding: "7px 10px", borderRadius: 6, border: "1px solid #e0e0e0", fontSize: 13, background: "white" }}>
          {options.map(o => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
        </select>
      ) : type === "textarea" ? (
        <textarea value={story[key]} onChange={e => onChange({ ...story, [key]: e.target.value })} rows={3}
          style={{ width: "100%", padding: "7px 10px", borderRadius: 6, border: "1px solid #e0e0e0", fontSize: 13, resize: "vertical", boxSizing: "border-box" }} />
      ) : (
        <input type={type} value={story[key]} onChange={e => onChange({ ...story, [key]: e.target.value })}
          style={{ width: "100%", padding: "7px 10px", borderRadius: 6, border: "1px solid #e0e0e0", fontSize: 13, boxSizing: "border-box" }} />
      )}
    </div>
  );

  return (
    <div>
      {field("Title", "title")}
      {field("Epic", "epic", "text", epics.length ? epics : ["Setup"])}
      {field("Priority", "priority", "select", [
        { value: "high", label: "High" }, { value: "medium", label: "Medium" }, { value: "low", label: "Low" }
      ])}
      {field("Notes", "notes", "textarea")}
      <div style={{ display: "flex", gap: 8, justifyContent: "space-between", marginTop: 4 }}>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onSave} style={{ background: "#1a1a2e", color: "white", border: "none", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>Save</button>
          <button onClick={onClose} style={{ background: "white", color: "#555", border: "1px solid #e0e0e0", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer" }}>Cancel</button>
        </div>
        {onDelete && (
          <button onClick={onDelete} style={{ background: "white", color: "#dc2626", border: "1px solid #fecaca", borderRadius: 6, padding: "8px 18px", fontSize: 13, cursor: "pointer" }}>Delete</button>
        )}
      </div>
    </div>
  );
}
