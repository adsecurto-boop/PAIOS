"""Development entry point: ``python -m paios.api [port] [--host H]
[--data-dir D]``."""

import sys

from paios.api.config import ApiConfig
from paios.api.server import serve


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    host, port, data_dir = ApiConfig.host, ApiConfig.port, ApiConfig.data_dir
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--host" and index + 1 < len(argv):
            host = argv[index + 1]
            index += 2
        elif token == "--data-dir" and index + 1 < len(argv):
            data_dir = argv[index + 1]
            index += 2
        elif token.isdigit():
            port = int(token)
            index += 1
        else:
            sys.stderr.write(
                "Usage: python -m paios.api [port] [--host H] [--data-dir D]\n"
            )
            return 2
    return serve(ApiConfig(host=host, port=port, data_dir=data_dir))


if __name__ == "__main__":
    raise SystemExit(main())
