"""Updater pure parts: semver, release feed parsing, checksums.

Also the isolation guard: paios_updater must never import paios.
"""

import ast
import json
from pathlib import Path

import pytest

import paios_updater
from paios_updater import checksums, releases, versions


class TestVersions:
    @pytest.mark.parametrize(
        "candidate,current,expected",
        [
            ("v2.2.0", "2.1.0", True),
            ("2.2.0", "2.2.0", False),
            ("v2.1.9", "2.2.0", False),
            ("v10.0.0", "9.99.99", True),
            ("2.2.0-rc1", "2.1.0", True),
        ],
    )
    def test_is_newer(self, candidate, current, expected):
        assert versions.is_newer(candidate, current) is expected

    @pytest.mark.parametrize("bad", ["", "abc", "1.2", "v1", "1.2.3.4x"])
    def test_malformed_versions_rejected(self, bad):
        with pytest.raises(versions.VersionError):
            versions.parse(bad)


def release_json(tag="v2.3.0", assets=(releases.SETUP_ASSET,
                                        releases.CHECKSUMS_ASSET)):
    return json.dumps(
        {
            "tag_name": tag,
            "body": "Release notes here",
            "assets": [
                {
                    "name": name,
                    "browser_download_url": f"https://x/{tag}/{name}",
                }
                for name in assets
            ],
        }
    )


class TestReleases:
    def test_latest_release_parses_tag_notes_assets(self):
        release = releases.latest_release(
            "owner/repo", fetcher=lambda url: release_json()
        )
        assert release.tag == "v2.3.0"
        assert release.notes == "Release notes here"
        assert release.installable is True

    def test_missing_assets_not_installable(self):
        release = releases.latest_release(
            "owner/repo",
            fetcher=lambda url: release_json(assets=("other.zip",)),
        )
        assert release.installable is False

    def test_unreachable_feed_raises_release_error(self):
        def broken(url):
            raise OSError("no network")

        with pytest.raises(releases.ReleaseError):
            releases.latest_release("owner/repo", fetcher=broken)

    def test_shapeless_payload_raises(self):
        with pytest.raises(releases.ReleaseError):
            releases.latest_release("owner/repo", fetcher=lambda url: "{}")


class TestChecksums:
    def test_verify_accepts_matching_digest(self, tmp_path):
        artifact = tmp_path / "PAIOSSetup.exe"
        artifact.write_bytes(b"installer-bytes")
        sums = (
            f"{checksums.sha256_of(artifact)}  PAIOSSetup.exe\n"
            "0" * 64 + "  other.bin\n"
        )
        checksums.verify(artifact, sums)  # no raise

    def test_verify_rejects_mismatch(self, tmp_path):
        artifact = tmp_path / "PAIOSSetup.exe"
        artifact.write_bytes(b"tampered")
        sums = "1" * 64 + "  PAIOSSetup.exe\n"
        with pytest.raises(checksums.ChecksumError, match="mismatch"):
            checksums.verify(artifact, sums)

    def test_verify_rejects_missing_entry(self, tmp_path):
        artifact = tmp_path / "PAIOSSetup.exe"
        artifact.write_bytes(b"x")
        with pytest.raises(checksums.ChecksumError, match="no entry"):
            checksums.verify(artifact, "")


class TestIsolation:
    def test_updater_never_imports_paios(self):
        """The absolute M20 constraint: PAIOSUpdater shares no code with
        the application it replaces."""
        package_dir = Path(paios_updater.__file__).parent
        for module_path in package_dir.glob("*.py"):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    assert not (
                        name == "paios" or name.startswith("paios.")
                        or name.startswith("paios_gui")
                        or name.startswith("paios_launcher")
                    ), f"{module_path.name} imports {name!r}"
