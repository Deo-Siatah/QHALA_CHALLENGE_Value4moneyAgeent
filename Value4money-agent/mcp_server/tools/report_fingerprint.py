"""Fingerprint the filed Markdown body."""

import hashlib


def fingerprint_markdown(body_md):
    """SHA-256 of the exact filed body, so any later change is visible."""
    return hashlib.sha256(body_md.encode("utf-8")).hexdigest()
