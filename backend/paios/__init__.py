"""PAIOS — Personal AI Operating System."""

#: Single source of truth for the product version, kept in lockstep with
#: pyproject.toml. The launcher passes it to the updater; the updater
#: itself never imports paios.
__version__ = "2.2.0"
