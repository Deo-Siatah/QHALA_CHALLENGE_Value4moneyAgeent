
-- The trigram indexes in 02_indexes.sql need this, and a fresh database has neither.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS load_log (
  id SERIAL PRIMARY KEY,
  year INT NOT NULL,
  file_name TEXT NOT NULL,
  rows_loaded INT NOT NULL,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenders (
  ocid TEXT PRIMARY KEY,
  data_year INT NOT NULL,
  buyer_id TEXT,
  buyer_name TEXT,
  title TEXT,
  category TEXT,
  method TEXT,
  published_at TIMESTAMPTZ,
  quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS awards (
  award_id TEXT PRIMARY KEY,
  ocid TEXT NOT NULL REFERENCES tenders(ocid),
  data_year INT NOT NULL,
  award_title TEXT,
  award_description TEXT,
  value_kes NUMERIC,
  currency TEXT,
  contract_start DATE,
  contract_end DATE,
  supplier_name TEXT,
  supplier_norm TEXT,
  lot_group TEXT,
  quality_flags TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS award_labels (
  award_id TEXT PRIMARY KEY REFERENCES awards(award_id),
  work_type TEXT,
  unit_count NUMERIC,
  unit_name TEXT,
  model TEXT,
  labelled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  actor TEXT NOT NULL,
  tool TEXT NOT NULL,
  input JSONB,
  output JSONB,
  approved_by TEXT
);

CREATE TABLE IF NOT EXISTS reports (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  body_md TEXT NOT NULL,
  approved_by TEXT
);