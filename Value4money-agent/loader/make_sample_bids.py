# Build the synthetic bid PDFs used to demonstrate the agent.
#
# These are not real bids and never claim to be. Every page says so, and every figure was made up.
# The numbers are chosen against the real Kenya OCDS awards for chainlink fence work, whose median is
# about 3.3 million KES, so the demonstration shows a pool that is genuinely comparable rather than
# one built to flatter the agent.
#
# Run it with: uv run python -m loader.make_sample_bids
# It writes three PDFs into sample_bids/ and prints what it wrote. Nothing is random and no clock is
# read, so running it again produces the same files.

from pathlib import Path

from fpdf import FPDF

TENDER_REF = "JKUAT/ENG/2026/FENCE/017"
BIDS_DIR = Path("sample_bids")

APEX = [
    ("Supply and fixing of chainlink fabric 2.4m high", "metre", 1800, 1250),
    ("Supply of concrete posts 100x100mm", "each", 260, 1900),
    ("Supply of concrete footing blocks", "each", 260, 950),
    ("Erection of sliding steel gate 4m", "each", 1, 120000),
    ("Labour for excavation and backfilling", "item", 1, 39000),
]

BORA = [
    ("Supply and fixing of chainlink fabric 2.4m high", "metre", 1800, 4200),
    ("Supply of concrete posts 100x100mm", "each", 260, 1700),
    ("Supply of concrete footing blocks", "each", 260, 1050),
    ("Erection of sliding steel gate 4m", "each", 1, 300000),
    ("Labour for excavation and backfilling", "item", 1, 75000),
]

# Zed's line items add up to 2,690,000 against a stated total of 2,750,000, on purpose.
ZED = [
    ("Supply and fixing of chainlink fabric 2.4m high", "metre", 1800, 1180),
    ("Supply of concrete posts 100x100mm", "each", 260, 1300),
    ("Supply of concrete footing blocks", "each", 260, 700),
    ("Erection of sliding steel gate 4m", "each", 1, 30000),
    ("Labour for excavation and backfilling", "item", 1, 16000),
]

BIDS = [
    ("apex-fencing.pdf", "Apex Fencing Contractors Ltd", APEX, 3150000),
    ("bora-contractors.pdf", "Bora Contractors (K) Ltd", BORA, 8650000),
    ("zed-solutions.pdf", "Zed Solutions Enterprises", ZED, 2750000),
]


def money(value: float) -> str:
    """Format a KES amount the way a Kenyan tender document would."""
    return f"{value:,.2f}"


def write_bid(path: Path, bidder: str, items: list, stated_total: float,
              tender_ref: str = TENDER_REF) -> None:
    """Write one bid page in the format parse_bid_pdf expects."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    lines = [
        "Bidder: " + bidder,
        f"Tender reference: {tender_ref}",
        "Currency: KES",
        "Synthetic: demonstration data, not a real tender",
        "Items: number, description, unit, quantity, unit price, line total",
    ]
    for number, (description, unit, quantity, unit_price) in enumerate(items, start=1):
        lines.append(f"{number} | {description} | {unit} | {quantity:,} | "
                     f"{money(unit_price)} | {money(quantity * unit_price)}")
    lines += [f"Stated total: {money(stated_total)}"]

    for line in lines:
        pdf.cell(0, 8, text=line, new_x="LMARGIN", new_y="NEXT")

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def main() -> None:
    """Write every sample bid PDF."""
    for name, bidder, items, stated_total in BIDS:
        path = BIDS_DIR / name
        computed = sum(quantity * unit_price for _, _, quantity, unit_price in items)
        write_bid(path, bidder, items, stated_total)
        print(f"wrote {path} | stated {stated_total:,.2f} | line items {computed:,.2f}"
              f"{' | ARITHMETIC MISMATCH ON PURPOSE' if computed != stated_total else ''}")


if __name__ == "__main__":
    main()