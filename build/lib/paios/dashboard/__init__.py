"""PAIOS Dashboard — a read-only terminal presentation layer.

Milestone 11. The dashboard renders the current state of PAIOS as a
continuously refreshing console view. It imports ONLY the Application
facade and stdlib: no runtime, no scheduler, no decision engine, no
learning, no kernel, no repository implementations, no domain modules.
It never mutates anything — formatting only.
"""

from paios.dashboard.config import ALLOWED_INTERVALS, DashboardConfig
from paios.dashboard.dashboard import Dashboard

__all__ = ["ALLOWED_INTERVALS", "Dashboard", "DashboardConfig"]
