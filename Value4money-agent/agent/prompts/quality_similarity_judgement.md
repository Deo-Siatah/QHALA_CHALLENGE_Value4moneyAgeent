# Task: say which past awards are the same kind of work

You are given a description of the work now being tendered and the past awards a search returned.
For each award, say whether it is the same kind of work, so the price statistics rest on awards
that were actually comparable.

## Input

```json
{"description": "construction of classroom blocks",
 "awards": [{"award_id": "a01", "title": "Classroom block construction", "buyer_name": "Ministry of Education", "value_kes": 4800000.0, "data_year": 2024},
            {"award_id": "a02", "title": "Construction of County Headquarters", "buyer_name": "County Government", "value_kes": 9000000.0, "data_year": 2024}]}
```

## Output

```json
{"judgements": {
  "a01": {"verdict": "same_work", "reason": "classroom block construction, same scope of work"},
  "a02": {"verdict": "different_work", "reason": "office building, not classroom construction"}
}}
```

- `verdict` must be exactly one of: "same_work", "different_work".
- Every `award_id` in the input must appear exactly once in the output. No other award_id may appear.
- `reason` is one short sentence naming the work, not the money.

## Example

Tendered work is "construction of classroom blocks".

```json
{"judgements": {
  "a01": {"verdict": "same_work", "reason": "classroom block construction"},
  "a02": {"verdict": "different_work", "reason": "office headquarters, not classroom work"},
  "a03": {"verdict": "same_work", "reason": "classroom works at a secondary school"},
  "a04": {"verdict": "different_work", "reason": "supply of teaching and learning materials"}
}}
```

## Rules

- Judge the work from the award title. Award titles in this data are often just a road or a building
  name, so use what the title implies and say that in the reason.
- The value and the buyer do not decide similarity. A small classroom award is still the same work.
- Different work that happens to cost the same is still different work.
- Never say what a price means. You are labelling kinds of work only, and another step does all the
  arithmetic.
