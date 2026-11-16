# Task: choose the next search for comparable past awards

You are given a description of the work now being tendered, the core terms that must stay in every
search, and, when this is not the first attempt, what the previous search returned and why it fell
short. Choose the single next search.

## Input

```json
{"description": "construction of classroom blocks",
 "core_terms": ["classroom", "block"],
 "attempt": 2,
 "previous": {"query": "classroom construction", "match": "strict", "min_year": 2023,
              "returned": 2, "target": 10, "problem": "too few awards matched every word"}}
```

On the first attempt `previous` is null and `attempt` is 1.

## Output

```json
{"query": "classroom block construction", "match": "loose", "min_year": 2023,
 "reason": "loose matching should catch awards titled classroom works or school block"}
```

- `match` must be exactly one of: "strict", "loose", "fuzzy".
- `min_year` is an integer year or null.
- `query` is a lower-case phrase of at most 15 words describing the work. It must keep every core
  term.

## Example

Previous search returned 2 awards against a target of 10, with match "strict" and min_year 2023.

```json
{"query": "classroom block construction works", "match": "loose", "min_year": 2023,
 "reason": "loose matching widens the pool beyond titles with every word"}
```

## Rules

- Widen one step at a time: change only the match mode, or only the year floor, or only the wording.
  Moving from "strict" to "fuzzy" and from 2023 to 2019 in one attempt wastes the attempt.
- Never drop a core term. If a search returns nothing, the remaining words are too narrow, not the
  kind of work too broad.
- Never put a supplier name, buyer name, tender reference or a price in `query`.
- `reason` is one sentence about the search, never about the bids or any bidder.
