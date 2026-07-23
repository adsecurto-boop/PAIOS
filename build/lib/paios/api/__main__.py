"""Development entry point: ``python -m paios.api [port] [--host H]
[--data-dir D] [--ai-provider P] [--ai-model M]``.

AI configuration precedence: PAIOS_AI_PROVIDER / PAIOS_AI_MODEL
environment variables override these flags (assistant_support resolves
them at composition time). API keys always come from the SDKs' own
environment variables (OPENAI_API_KEY / ANTHROPIC_API_KEY).
"""

import sys

from paios.api.assistant_support import PROVIDERS
from paios.api.config import ApiConfig
from paios.api.server import serve

_USAGE = (
    "Usage: python -m paios.api [port] [--host H] [--data-dir D]"
    f" [--ai-provider {'|'.join(PROVIDERS)}] [--ai-model M]\n"
)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    host, port, data_dir = ApiConfig.host, ApiConfig.port, ApiConfig.data_dir
    ai_provider, ai_model = ApiConfig.ai_provider, ApiConfig.ai_model
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--host" and index + 1 < len(argv):
            host = argv[index + 1]
            index += 2
        elif token == "--data-dir" and index + 1 < len(argv):
            data_dir = argv[index + 1]
            index += 2
        elif token == "--ai-provider" and index + 1 < len(argv):
            ai_provider = argv[index + 1].strip().lower()
            if ai_provider not in PROVIDERS:
                sys.stderr.write(
                    f"Unknown AI provider '{ai_provider}'."
                    f" Choose one of: {', '.join(PROVIDERS)}\n"
                )
                return 2
            index += 2
        elif token == "--ai-model" and index + 1 < len(argv):
            ai_model = argv[index + 1]
            index += 2
        elif token.isdigit():
            port = int(token)
            index += 1
        else:
            sys.stderr.write(_USAGE)
            return 2
    return serve(
        ApiConfig(
            host=host,
            port=port,
            data_dir=data_dir,
            ai_provider=ai_provider,
            ai_model=ai_model,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
