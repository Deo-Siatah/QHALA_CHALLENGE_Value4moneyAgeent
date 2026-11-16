import pytest

from mcp_server.tools.record_intake_correction import record_intake_correction


def test_a_named_person_can_record_a_correction():
    result = record_intake_correction("county", "Nairobi", "Grace Wanjiku", "typo in the PDF")

    assert result["field"] == "county"
    assert result["value"] == "Nairobi"
    assert result["approved_by"] == "Grace Wanjiku"
    assert result["recorded"] is True


@pytest.mark.parametrize("name", ["", "  ", "agent", "AI", "n/a"])
def test_a_role_or_a_blank_is_not_a_person(name):
    with pytest.raises(ValueError):
        record_intake_correction("county", "Nairobi", name)


@pytest.mark.parametrize("field, value", [("", "x"), ("county", ""), ("county", None)])
def test_a_correction_needs_a_field_and_a_value(field, value):
    with pytest.raises(ValueError):
        record_intake_correction(field, value, "Grace Wanjiku")
