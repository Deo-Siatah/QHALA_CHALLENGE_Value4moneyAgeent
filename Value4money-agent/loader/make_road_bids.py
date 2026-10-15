# Build six synthetic road-work bid PDFs, a second demonstration set beside the fence bids in
# sample_bids/. Nothing here is a real tender: every page says so in the words parse_bid looks for.
#
# The figures are chosen against the real Kenya OCDS road awards, whose median sits in the billions,
# so the demonstration shows a pool that is genuinely comparable. They also spread on purpose:
# one bid far above the middle, one far below, and one whose line items do not add up to its stated
# total, because a review file that has never caught anything proves nothing.
#
# Run it with: uv run python -m loader.make_road_bids
# It writes six PDFs into pdfs/, which the agent reads with: uv run python main.py --bids-dir pdfs

from pathlib import Path
from typing import List

from .make_sample_bids import write_bid

TENDER_REF = "KURA/ENG/2026/NRD/041"
BIDS_DIR = Path("pdfs")

# Rehabilitation, laterite haulage, culverts and clearance: the same four jobs priced six ways.
KOROMO = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 2150000000),
    ("Haulage of laterite to site", "lorry", 620, 1450000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 2200000),
    ("Site clearance and bush removal", "hectare", 35, 2200000),
]

UPLANDS = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 6800000000),
    ("Haulage of laterite to site", "lorry", 620, 2300000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 2900000),
    ("Site clearance and bush removal", "hectare", 35, 2600000),
]

# Tugen's line items come to 1,769,850,000 against a stated 1,800,000,000, on purpose.
TUGEN = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 1400000000),
    ("Haulage of laterite to site", "lorry", 620, 420000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 1150000),
    ("Site clearance and bush removal", "hectare", 35, 1550000),
]

RIFT_VALLEY = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 1950000000),
    ("Haulage of laterite to site", "lorry", 620, 1180000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 1900000),
    ("Site clearance and bush removal", "hectare", 35, 1760000),
]

HIGHLAND = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 3050000000),
    ("Haulage of laterite to site", "lorry", 620, 1780000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 2600000),
    ("Site clearance and bush removal", "hectare", 35, 2300000),
]

KAPENGURIA = [
    ("Rehabilitation of 14km road to bitumen standard", "item", 1, 560000000),
    ("Haulage of laterite to site", "lorry", 620, 380000),
    ("Supply and installation of 600mm concrete culverts", "each", 48, 980000),
    ("Site clearance and bush removal", "hectare", 35, 1150000),
]

BIDS = [
    ("koromo-road-works.pdf", "Koromo Road Works Ltd", KOROMO, 3231600000),
    ("uplands-infrastructure.pdf", "Uplands Infrastructure Ltd", UPLANDS, 8456200000),
    ("tugen-civil-engineering.pdf", "Tugen Civil Engineering Ltd", TUGEN, 1800000000),
    ("rift-valley-roads-agency.pdf", "Rift Valley Roads Agency Ltd", RIFT_VALLEY, 2834400000),
    ("highland-construction.pdf", "Highland Construction & Civil Works Ltd", HIGHLAND, 4358900000),
    ("kapenguria-works-agency.pdf", "Kapenguria Works Agency Ltd", KAPENGURIA, 882890000),
]


def write_road_bids(directory: Path = BIDS_DIR) -> List[Path]:
    """Write every road bid into the given folder and return the paths written."""
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, bidder, items, stated_total in BIDS:
        path = directory / name
        computed = sum(quantity * unit_price for _, _, quantity, unit_price in items)
        write_bid(path, bidder, items, stated_total, TENDER_REF)
        written.append(path)
        print(f"wrote {path} | stated {stated_total:,.2f} | line items {computed:,.2f}"
              f"{' | ARITHMETIC MISMATCH ON PURPOSE' if abs(computed - stated_total) > 0.01 else ''}")
    return written


def main() -> None:
    """Write the six road bid PDFs into pdfs/."""
    write_road_bids(BIDS_DIR)


if __name__ == "__main__":
    main()