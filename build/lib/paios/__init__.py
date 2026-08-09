"""PAIOS — Personal AI Operating System."""

__version__ = "2.4.0"
__build__ = "008"


def get_version_info() -> dict:
    from pathlib import Path
    commit = "unknown"
    try:
        pkg_dir = Path(__file__).resolve().parent
        commit_file = pkg_dir / "git_commit.txt"
        if commit_file.is_file():
            commit = commit_file.read_text(encoding="utf-8").strip()
        else:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(pkg_dir),
                capture_output=True,
                text=True,
                check=True,
            )
            commit = result.stdout.strip()
    except Exception:
        pass

    return {
        "version": __version__,
        "build": __build__,
        "commit": commit,
    }
