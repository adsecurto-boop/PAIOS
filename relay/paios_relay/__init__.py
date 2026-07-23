"""PAIOS relay — a portable, dependency-free reverse-tunnel broker.

Deploy anywhere (``python relay.py`` or ``docker compose up -d``); it
imports nothing from PAIOS, so the two evolve independently. It lets a
phone reach its own desktop from any network without exposing the
desktop to inbound connections.
"""

__version__ = "1.0.0"
