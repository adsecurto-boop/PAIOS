"""PAIOS REST API — a JSON transport layer over the Application facade.

Milestone 12. The API maps HTTP to facade calls, validates request
syntax, serializes responses, and translates exceptions into HTTP status
codes — nothing more. No business logic, no persistence, no runtime /
scheduler / decision-engine / learning / repository-implementation
imports.

Framework: the Python standard library's ``http.server``. The smallest
framework that fits this architecture is no framework at all — PAIOS has
zero runtime dependencies and the API's entire transport duty (routing,
JSON bodies, status codes) is a few small, fully-tested modules.
"""

from paios.api.config import ApiConfig
from paios.api.routes import ApiRouter
from paios.api.server import ApiServer, serve

__all__ = ["ApiConfig", "ApiRouter", "ApiServer", "serve"]
