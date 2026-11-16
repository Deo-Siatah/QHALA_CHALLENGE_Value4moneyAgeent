-- The filed record keeps the fingerprint of its exact Markdown body and the structured model
-- that rendered it. Both are added here so an existing database is brought forward safely.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS fingerprint TEXT;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS review_json JSONB;
