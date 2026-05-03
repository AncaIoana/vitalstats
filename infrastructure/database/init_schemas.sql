-- vitalStats — schema initialisation
-- Creates the three top-level schemas. Run once on a fresh database.
-- Run with: psql -d vitalstats -f infrastructure/database/init_schemas.sql
--
-- After running this, run create_ingestion_tables.sql to create
-- the tables that Python ingestion scripts write to.
-- dbt creates everything else on first: cd dbt && uv run dbt run

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
