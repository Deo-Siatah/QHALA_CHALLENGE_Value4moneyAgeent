# Task: name the work that was tendered

You are given one tender reference and the item lines of a bid. Say what kind of work this is
and describe it in a few words, so a search over past public awards can be aimed at it.

## Input

```json
{"tender_ref": "TENDER/NC/2026/014",
 "items": [{"description": "Classroom construction", "unit": "item", "quantity": 10, "unit_price": 100000.0}]}
```

## Output

```json
{"category": "works", "description": "construction of classroom blocks"}
```

- `category` must be exactly one of: "works", "goods", "services".
- `description` is a lower-case phrase of at most 12 words describing the work, with no supplier
  name, no tender reference, no buyer name and no numbers.

## Example

Input items are "supply of office chairs", "delivery and installation of 40 chairs".
Output:

```json
{"category": "goods", "description": "supply and delivery of office chairs"}
```

## Rules

- Judge the category from the work itself. Chairs are goods even if they are delivered and installed.
- If the items do not describe one coherent job, give the description of the largest part of the work
  and say so in it, for example "supply of office chairs, with minor electrical fittings".
- Never name a supplier, never guess a location, never mention a price.
