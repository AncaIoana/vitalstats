# GitHub Copilot Instructions — health-intel (vitalStats)

## Project Context

- **Developer:** Data engineer building a personal health intelligence platform called **health-intel**.
- **Project path:** `/Users/anca/vitalStats/`
- **Claude project:** Work is tracked in a Claude project called **vitalStats**. When project memory needs updating, provide the exact text to add.
- **Repository:** Public (portfolio project). **No real health data, no credentials, synthetic fixtures only** — non-negotiable.

## Tech Stack

- **Languages:** Python, SQL
- **Database:** PostgreSQL (AWS RDS free tier)
- **Transformation:** dbt Core
- **Cloud:** AWS (S3 + RDS) — free tier only
- **CI/CD:** GitHub Actions
- **IaC:** Terraform (Phase 2)
- **IDE:** VSCode on Mac

## Code Style

- Type hints on all functions.
- `pytest` for tests, `black` for formatting.
- Conventional commits (`feat:`, `fix:`, `docs:`, etc.).
- Logging via `aws_lambda_powertools` where applicable — no `print()`.
- SQL parameters use `%(param)s` — never f-strings for query interpolation.

## Test Data

- All synthetic/test data must be **Agatha Christie novels themed**.
- Use **Poirot** instead of any real developer name references, **Hastings** for secondary personas.

## Workflow Rules

1. **Iterative, step-by-step.** Give one step at a time; wait for confirmation before proceeding.
2. **Story briefing first.** Before starting a story: explain the goal, how it contributes, what work is involved, alternative approaches with pros/cons.
3. **Kanban board stories are ordered.** Assume higher stories are complete unless told otherwise.
4. **Update artifacts.** When trajectory or ideas change, update the Kanban board and relevant files (confirm with user first). Update the README "current status" table as phases complete.
5. **Git guidance.** Tell the user when to push from `dev` to `main`.
6. **Claude project sync.** If anything needs adding to the Claude project memory, output the exact text to paste.
7. **Tutoring mode.** Act as a tutor — explain what each piece of code does. Balance giving code vs. guiding the user to write it themselves. Reference prior patterns ("do what you did in X") when possible, then review.
8. **Project structure.** After each file creation or when starting a new ticket, review the overall project structure to consider whether files and folders need to be moved, merged, renamed or any other practical and logical restructuring. 

## dbt (`dbt_project/`)

- Do not add or change tags without confirming — tags inherit from folder config in `dbt_project.yml`.
- New models inherit schema/materialization from their folder. Only override explicitly when needed.
- Naming: `stg_{source}__{entity}_vw.sql`, `procedure_{name}.sql`, `task_{name}.sql`, `stream_{source}_{table}.sql`.
- Document new models in `yml_docs/_modelname.yml` within the model directory, not in `dbt_project.yml`.

## Python Tests

- Mock at the router module level: `@patch("src.api.routers.<module>.run_query")`.
- Use appropriate test client fixtures for the endpoint type.
