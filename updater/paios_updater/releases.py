"""GitHub Releases lookup: one HTTPS GET, pure parsing around it.

The fetcher is injectable so every decision in here is testable with
canned JSON and the launcher's periodic check never needs the network
in tests.
"""

import json
import urllib.request
from dataclasses import dataclass

DEFAULT_REPO = "adsecurto-boop/PAIOS"
_API_TEMPLATE = "https://api.github.com/repos/{repo}/releases/latest"
_TIMEOUT_SECONDS = 15

#: The two assets an installable release must carry (build_installer.py
#: emits both; SHA256SUMS.txt is the trust anchor for the download).
SETUP_ASSET = "PAIOSSetup.exe"
CHECKSUMS_ASSET = "SHA256SUMS.txt"


class ReleaseError(Exception):
    """The release feed was unreachable or not release-shaped."""


@dataclass(frozen=True)
class Release:
    tag: str
    notes: str
    assets: dict  # name -> browser_download_url

    @property
    def installable(self) -> bool:
        return SETUP_ASSET in self.assets and CHECKSUMS_ASSET in self.assets


def default_fetcher(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PAIOSUpdater",
        },
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as reply:
        return reply.read().decode("utf-8")


def latest_release(repo: str = DEFAULT_REPO, fetcher=default_fetcher) -> Release:
    url = _API_TEMPLATE.format(repo=repo)
    try:
        raw = fetcher(url)
        payload = json.loads(raw)
    except Exception as error:
        raise ReleaseError(f"Cannot read releases for {repo}: {error}") from error
    if not isinstance(payload, dict) or "tag_name" not in payload:
        raise ReleaseError(f"Release feed for {repo} has no tag_name")
    assets = {}
    for asset in payload.get("assets", ()):
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if isinstance(name, str) and isinstance(url, str):
            assets[name] = url
    return Release(
        tag=str(payload["tag_name"]),
        notes=str(payload.get("body") or ""),
        assets=assets,
    )
