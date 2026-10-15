# Task: write one read-only query to find comparable past awards

Our own search has been tried and the pool of comparable awards is still too thin. You have been
given the real schema of the database. Write one query that finds awards of the same kind of work as
the description.

This query runs against a live public database through a server you do not control. It is checked
before it is sent and refused if it is anything other than a single read. Write accordingly.

## Input

```json
{"description": "construction of classroom blocks",
 "schema": [{"name": "awards", "columns": ["award_id", "ocid", "data_year", "value_kes", "currency", "supplier_name", "quality_flags"]},
            {"name": "tenders", "columns": ["ocid", "title", "buyer_name", "category", "data_year"]}],
 "have_so_far": 3,
 "need_at_least": 5,
 "previous_query": "classroom block construction"}
```

## Output

```json
{"sql": "SELECT a.award_id, a.ocid, a.data_year, a.value_kes, a.currency, a.supplier_name, t.title, t.buyer_name, t.category, a.quality_flags FROM awards a JOIN tenders t ON a.ocid = t.ocid WHERE a.value_kes > 0 AND a.currency = 'KES' AND to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', 'fenc%') ORDER BY a.data_year DESC LIMIT 30",
 "reason": "the awarded work is usually titled as a fence, not as a chainlink fence"}
```

- `sql` is one statement. No semicolons, no comments, no multiple statements.
- `reason` is one sentence about the search, never about any bidder.

## Rules

- Only these tables exist for you: `awards`, `tenders`, `award_labels`. Anything else is refused.
- Only `SELECT` or `WITH`. No insert, update, delete, drop, truncate, alter, create, grant, copy,
  commit, rollback or set, anywhere in the text, not even in a comment.
- Always join on `awards.ocid = tenders.ocid`.
- Always filter `a.value_kes > 0 AND a.currency = 'KES'`. A row without a usable KES value is not
  evidence of anything.
- Return `a.award_id` in the first column. Rows without it are thrown away.
- `ORDER BY` and `LIMIT 30`. Never select more than 30 rows.
- Match titles with `to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', ...)`, or
  `similarity(lower(coalesce(t.title, '')), ...)`. Use a prefix operator such as `fenc%` to widen
  a search that returned too little.
- Never mention a supplier, a price or any bidder in `reason`. You have not seen the bids.
