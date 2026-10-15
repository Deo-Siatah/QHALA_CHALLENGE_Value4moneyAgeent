CREATE INDEX IF NOT EXISTS idx_awards_ocid ON awards (ocid);
CREATE INDEX IF NOT EXISTS idx_awards_lot_group ON awards (lot_group);
CREATE INDEX IF NOT EXISTS idx_awards_value ON awards (value_kes) WHERE value_kes > 0;
CREATE INDEX IF NOT EXISTS idx_awards_year ON awards (data_year);
CREATE INDEX IF NOT EXISTS idx_awards_supplier ON awards (supplier_norm);

CREATE INDEX IF NOT EXISTS idx_tenders_category ON tenders (category);
CREATE INDEX IF NOT EXISTS idx_tenders_buyer ON tenders (buyer_id);
CREATE INDEX IF NOT EXISTS idx_tenders_title_fts
  ON tenders USING gin (to_tsvector('simple', coalesce(title, '')));
CREATE INDEX IF NOT EXISTS idx_tenders_title_trgm
  ON tenders USING gin (title gin_trgm_ops);

ANALYZE tenders;
ANALYZE awards;