# These are the tests for loader/make_road_bids.py. They are the spec: they say what the six
# road bids must be before any of them exist. They read the generated PDFs back with pypdf, so
# they check the file the agent will actually parse, not just the numbers in the source.

from pathlib import Path

import pypdf
import pytest

from loader import make_road_bids


def read_text(path: Path) -> str:
    """The words in a generated PDF, as the agent's parser will read them."""
    with open(path, "rb") as handle:
        reader = pypdf.PdfReader(handle)
        return "\n".join(page.extract_text() for page in reader.pages)


def stated_total(path: Path) -> float:
    """The stated total as printed in the PDF, in KES."""
    for line in read_text(path).splitlines():
        if line.strip().lower().startswith("stated total:"):
            return float(line.split(":", 1)[1].replace(",", "").strip())
    raise AssertionError(f"{path.name} has no stated total")


def computed_total(path: Path) -> float:
    """The sum of the line items as printed in the PDF, in KES."""
    rows = [line for line in read_text(path).splitlines()
            if line.strip()[:1].isdigit() and "|" in line]
    return sum(float(row.split("|")[3].replace(",", "").strip()) *
               float(row.split("|")[4].replace(",", "").strip())
               for row in rows)


@pytest.fixture
def written(tmp_path):
    """The six generated PDFs, in a temporary folder."""
    return make_road_bids.write_road_bids(tmp_path)


def test_six_bids_are_written(written):
    assert len(written) == 6
    assert all(path.exists() for path in written)


def test_the_bids_are_named_after_their_bidders(written):
    names = [path.name for path in written]

    assert "koromo-road-works.pdf" in names
    assert "uplands-infrastructure.pdf" in names
    assert "tugen-civil-engineering.pdf" in names


def test_the_default_folder_is_pdfs_and_it_sits_beside_the_fence_bids():
    assert make_road_bids.BIDS_DIR == Path("pdfs")


def test_every_bid_says_it_is_synthetic(written):
    for path in written:
        assert "Synthetic" in read_text(path), f"{path.name} must say it is not a real tender"


def test_every_bid_carries_the_same_roads_tender_reference(written):
    for path in written:
        assert make_road_bids.TENDER_REF in read_text(path)


def test_every_bid_names_its_bidder_in_full(written):
    for path in written:
        assert read_text(path).splitlines()[0].startswith("Bidder: ")
        assert len(read_text(path).splitlines()[0]) > len("Bidder: ")


def test_five_of_the_six_bids_add_up(written):
    wrong = [path.name for path in written if path.name != "tugen-civil-engineering.pdf"
             and abs(stated_total(path) - computed_total(path)) > 0.01]

    assert wrong == []


def test_tugen_does_not_add_up_on_purpose(written):
    tugen = next(path for path in written if path.name == "tugen-civil-engineering.pdf")

    assert stated_total(tugen) > computed_total(tugen)
    assert stated_total(tugen) - computed_total(tugen) > 100000


def test_the_bids_spread_around_the_road_benchmark(written):
    """One honest comparator, some far above, one far below: the pool must be worth judging."""
    totals = sorted(stated_total(path) for path in written)

    assert totals[0] < 1_000_000_000
    assert totals[-1] > 5_000_000_000
    assert 2_000_000_000 < totals[len(totals) // 2] < 4_000_000_000


def test_writing_the_bids_twice_gives_the_same_figures(tmp_path):
    make_road_bids.write_road_bids(tmp_path)
    first = [stated_total(path) for path in sorted(tmp_path.glob("*.pdf"))]
    make_road_bids.write_road_bids(tmp_path)
    second = [stated_total(path) for path in sorted(tmp_path.glob("*.pdf"))]

    assert first == second


def test_the_work_is_road_work(written):
    for path in written:
        text = read_text(path).lower()
        assert "road" in text
        assert "fence" not in text