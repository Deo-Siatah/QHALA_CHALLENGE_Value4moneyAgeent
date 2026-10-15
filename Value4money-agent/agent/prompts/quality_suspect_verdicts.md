# Task: decide whether an oddly valued award belongs in the pool

Rules have already marked a handful of awards as suspicious because their value sits far from the
middle of the pool. For each one, say whether it is a real award of the kind of work, or a record
that looks wrong. You are not judging the bids. You are judging these past awards.

## Input

```json
{"description": "construction of classroom blocks",
 "median_kes": 4800000.0,
 "awards": [{"award_id": "a07", "title": "Classroom block construction", "value_kes": 43000000.0,
             "ratio_to_median": 9.0, "suspect_reason": "extreme_high"}]}
```

## Output

```json
{"verdicts": {
  "a07": {"verdict": "keep", "reason": "eight classroom blocks across three sites, value consistent with the scope"}
}}
```

- `verdict` must be exactly one of: "keep", "exclude".
- Every `award_id` in the input must appear exactly once. No other award_id may appear.
- `reason` is one short sentence about the record.

## Example

```json
{"verdicts": {
  "a07": {"verdict": "keep", "reason": "large multi-site classroom programme, not a stray figure"},
  "a08": {"verdict": "exclude", "reason": "title is one classroom but the value covers a county programme"},
  "a09": {"verdict": "exclude", "reason": "record has no supplier and reads as a test entry"}
}}
```

## Rules

- "keep" means the award is real and is the kind of work described. A genuinely large contract for
  the same work is kept, and its size is then part of the pool.
- "exclude" means the record cannot be trusted as a price for this work, or it is not this work.
- If the title is short and gives no scope, say so in the reason and keep the award only when the
  title clearly matches the described work.
- Never say a value is too high, too low or wrong. You may only exclude a record by giving its reason.
- Never mention any bidder. You have not seen the bids.
