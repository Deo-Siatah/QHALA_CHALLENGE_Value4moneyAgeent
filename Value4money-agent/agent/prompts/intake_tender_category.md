# Task: name the kind of work that was tendered

You are given a tender's title, its reference, and the item lines of a bid. Say what kind of work
this is and give the words that must stay in every search over past awards. The title already
describes the work; do not rewrite it.

## Input

```json
{"tender_ref": "TENDER/NC/2026/014",
 "title": "Construction of classroom blocks",
 "items": [{"description": "Classroom construction", "unit": "item", "quantity": 10, "unit_price": 100000.0}]}
```

## Output

```json
{"category": "works", "core_terms": ["classroom", "block"]}
```

- `category` must be exactly one of: "works", "goods", "services".
- `core_terms` is one to three lower-case words that name the work itself. They must still match a
  reasonable past award title even when the search is widened. Do not use "construction", "supply",
  "works" or a place name on their own.

## Example

Title is "Supply and delivery of office chairs", items are "supply of office chairs" and
"delivery and installation of 40 chairs".
Output:

```json
{"category": "goods", "core_terms": ["chairs", "office"]}
```

## Rules

- Judge the category from the work itself. Chairs are goods even if they are delivered and installed.
- Never name a supplier, never guess a location, never mention a price.
- Answer with one JSON object and nothing else.
