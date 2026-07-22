"""SHA256 verification against the release's SHA256SUMS.txt."""

import hashlib
from pathlib import Path


class ChecksumError(Exception):
    """A missing entry or a digest mismatch — the download is rejected."""


def parse_sums(text: str) -> dict:
    """`sha256sum` format: '<hex>  <name>' per line -> {name: hex}."""
    entries = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            entries[parts[-1]] = parts[0].lower()
    return entries


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, sums_text: str) -> None:
    """Raise ChecksumError unless `path` matches its SHA256SUMS entry."""
    entries = parse_sums(sums_text)
    expected = entries.get(path.name)
    if expected is None:
        raise ChecksumError(f"{path.name} has no entry in SHA256SUMS.txt")
    actual = sha256_of(path)
    if actual != expected:
        raise ChecksumError(
            f"{path.name} digest mismatch: expected {expected}, got {actual}"
        )
