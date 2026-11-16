# Task: write the short notes that sit beside findings already written in code

Every sentence of the file is built in code from the tools' own figures. You supply only a
summary note and one note per finding. The numbers, the bidder names and the money are not in
your input, and they must not be in your answer.

## Input

```json
{"tender_ref": "TENDER/NC/2026/014",
 "description": "construction of classroom blocks",
 "pool_size": 18,
 "findings": [{"key": "pool", "kind": "pool", "position": null},
              {"key": "bid:1", "kind": "bid", "position": "far_above"},
              {"key": "arithmetic:1", "kind": "bid", "position": null}]}
```

`kind` is one of:

- `pool`: how many comparable awards were found, their median and normal range.
- `bid`: how one bid total sits against the median of the pool.
- `arithmetic`: a bid's stated total does not match the sum of its own line items.

`position` is one of `within_range`, `far_above`, `far_below`, or null. `arithmetic:*` means the
bid's stated total does not match its computed total.

## Output

```json
{"summary_note": "The pool rests on comparable classroom construction awards, so the committee can compare the bids against similar work.",
 "finding_notes": {
   "pool": "The comparison pool is large enough to give the committee a stable middle figure.",
   "bid:1": "The total sits well above the normal range for this work.",
   "arithmetic:1": "The stated total and the sum of the line items do not agree."
 }}
```

- Write one `finding_notes` entry for every `key` in the input. No other keys.
- `summary_note` is at most 40 words. Each finding note is at most 25 words.
- The notes are appended to the code-written sentence, so add meaning, not a restatement.

## Rules

- Never write a digit, a number word (`one`, `two`, `three`, `ten`, `hundred`, `million`, ...), a
  percentage sign, a currency, or any bidder name.
- Do not say whether a bid should win. Describe the evidence, not a recommendation.
- Do not repeat a figure or a phrase already in the finding. Say what the finding means in plain
  words for a committee reading the file.
- If the pool is thin, the note should say the evidence is limited, in plain words.
