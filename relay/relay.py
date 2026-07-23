#!/usr/bin/env python3
"""Single-file launcher: ``python relay.py``.

Equivalent to ``python -m paios_relay`` but runnable straight from this
directory on any machine with Python 3.12+ and nothing else installed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paios_relay.server import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
