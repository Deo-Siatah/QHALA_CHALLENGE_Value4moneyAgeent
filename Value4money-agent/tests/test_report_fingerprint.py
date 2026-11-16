import hashlib

from mcp_server.tools.report_fingerprint import fingerprint_markdown


def test_fingerprint_is_sha256_of_the_markdown_body_only():
    body = "# Price review evidence: T/1\n\nA body without an approval block.\n"

    assert fingerprint_markdown(body) == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_one_changed_character_changes_the_fingerprint():
    first = fingerprint_markdown("body\n")
    second = fingerprint_markdown("bodY\n")

    assert first != second


def test_the_same_body_has_the_same_fingerprint_every_time():
    body = "same body\n"

    assert fingerprint_markdown(body) == fingerprint_markdown(body)
