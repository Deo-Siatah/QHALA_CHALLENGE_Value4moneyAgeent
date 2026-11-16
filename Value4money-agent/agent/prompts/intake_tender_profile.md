# Task: name the work that was tendered

You are given one tender reference and the item lines of a bid. Say what kind of work this is,
describe it in a few words, and give the words that must stay in every search over past awards.

## Input

```json
{"tender_ref": "TENDER/NC/2026/014",
 "items": [{"description": "Classroom construction", "unit": "item", "quantity": 10, "unit_price": 100000.0}]}
```

## Output

```json
{"category": "works", "description": "construction of classroom blocks",
 "core_terms": ["classroom", "block"]}
```

- `category` must be exactly one of: "works", "goods", "services".
- `description` is a lower-case phrase of at most 12 words describing the work, with no supplier
  name, no tender reference, no buyer name and no numbers.
- `core_terms` is one to three lower-case words that name the work itself. They must still match a
  reasonable past award title even when the search is widened. Do not use "construction", "supply",
  "works" or a place name on their own.

## Example

Input items are "supply of office chairs", "delivery and installation of 40 chairs".
Output:

```json
{"category": "goods", "description": "supply and delivery of office chairs",
 "core_terms": ["chairs", "office"]}
```

## Rules

- Judge the category from the work itself. Chairs are goods even if they are delivered and installed.
- If the items do not describe one coherent job, give the description and core terms of the largest
  part of the work and say so in the description.
- Never name a supplier, never guess a location, never mention a price.
