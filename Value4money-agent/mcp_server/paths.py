# One place decides whether a file is allowed to be read.
# A string prefix is not a sandbox: "bids_evil" starts with "bids" but is a sibling folder.
# Resolved paths are compared with Path.is_relative_to, so only files truly inside the folder pass.

from pathlib import Path


class PathOutsideError(ValueError):
    """Raised when a path resolves outside the directory it must stay in."""


def resolve_inside(path: str | Path, base: str | Path, label: str) -> Path:
    """Resolve path against base and return it, refusing anything that lands outside base."""
    base_path = Path(base).resolve()
    candidate = Path(path)
    resolved = candidate.resolve() if candidate.is_absolute() else (base_path / candidate).resolve()
    if not resolved.is_relative_to(base_path):
        raise PathOutsideError(f"Path outside {label} directory")
    return resolved
