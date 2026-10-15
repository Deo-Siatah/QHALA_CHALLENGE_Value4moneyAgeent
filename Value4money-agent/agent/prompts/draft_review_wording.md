# Task: write the wording for a tender committee evidence file

You are given the numbers and the records. You supply short wording only. The file itself, its
headings, its tables and its money formatting are rendered for you, and a fixed notice and
limitations section are added automatically. Do not write Markdown, do not write a heading, do
not write a table row.

## Input

```json
{"tender_ref": "TENDER/NC/2026/014",
 "description": "construction of classroom blocks",
 "benchmark": {"n": 18, "confidence": "high", "median_kes": 4800000.0,
               "q1_kes": 4100000.0, "q3_kes": 5600000.0},
 "bids": [{"bidder": "Apex", "total": 5000000.0, "pct_vs_median": 4.2, "position": "within_range",
           "arithmetic_issues": []},
          {"bidder": "Bora", "total": 9000000.0, "pct_vs_median": 87.5, "position": "far_above",
           "arithmetic_issues": ["Stated total 9000000.00 does not match computed total 8400000.00"]}],
 "awards": [{"award_id": "a01", "title": "Classroom block construction", "buyer_name": "Ministry of Education",
             "value_kes": 4800000.0, "data_year": 2024}],
 "excluded": {"no_value": 2, "different_work": 4}}
```

## Output

```json
{"summary": "Eighteen awards of classroom construction were compared, and one bid total sits 87.5% above the median of that pool.",
 "bid_comments": {"Apex": "4.2% above the median of eighteen similar awards, inside the normal range.",
                  "Bora": "87.5% above the median of eighteen similar awards. The stated total does not match the sum of its own line items."},
 "findings": [{"text": "One bid total is 87.5% above the median of eighteen similar awards, above the upper quartile of 5600000.0.",
               "sources": ["a01", "a02"]}],
 "sources_used": ["a01", "a02"]}
```

- `summary` is at most 60 words and covers the whole pool, not one bidder.
- `bid_comments` has one entry for every bidder in the input, each at most 25 words. Say nothing
  when there is nothing to say: an empty string is correct for a bid that sits on the median with no
  arithmetic issue.
- `findings` is a list of at most 4 items. Each `text` is at most 40 words. Each `sources` list has
  at least one `award_id`, and every id must appear in `awards` in the input and in `sources_used`.
- `sources_used` lists every `award_id` you cite, and nothing else.

## Example for one finding

```json
{"text": "Eighteen awards of classroom construction between 2020 and 2025 have a median of 4800000.0 and a normal range of 4100000.0 to 5600000.0.",
 "sources": ["a01", "a02", "a03"]}
```

## Rules

- Every figure you write must already be in the input, copied exactly. Never compute, round,
  convert or estimate a figure. Another check rejects any number you add.
- A finding is a fact with its records attached. Write "X% above the median of N similar awards",
  never "the price is too high" or any wording from the banned list.
- Arithmetic issues are reported as facts about the document, not about the bidder's honesty.
- Do not repeat the same finding for two bidders with similar numbers. One finding, all its sources.
- If `confidence` is "insufficient" or the pool is thin, say so in the summary in plain words:
  the committee needs to know the evidence was limited.
