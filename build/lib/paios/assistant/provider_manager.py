"""ProviderManager: Selecting active provider, health checks, logging and automatic fallback."""

import time
from typing import Callable
from paios.assistant.adapters import LlmAdapter, AdapterError


class ProviderManager(LlmAdapter):
    def __init__(
        self,
        active_provider_name: str,
        providers: dict[str, LlmAdapter],
        log_callback: Callable[[dict], None] | None = None,
        fallback_chain: list[str] | None = None,
    ) -> None:
        self._active_provider_name = active_provider_name
        self._providers = providers
        self._log_callback = log_callback
        self._fallback_chain = fallback_chain if fallback_chain is not None else ["ollama"]

    @property
    def name(self) -> str:
        provider = self.get_active_provider()
        return provider.name if provider else self._active_provider_name

    def switch_provider(self, name: str) -> None:
        self._active_provider_name = name

    def get_active_provider(self) -> LlmAdapter | None:
        return self._providers.get(self._active_provider_name)

    def get_capabilities(self) -> dict:
        provider = self.get_active_provider()
        if provider and hasattr(provider, "capabilities"):
            caps = provider.capabilities
            return {
                "streaming": caps.streaming,
                "vision": caps.vision,
                "tool_calling": caps.tool_calling,
                "thinking": caps.thinking,
                "offline": caps.offline,
                "embeddings": caps.embeddings,
                "planning": caps.planning,
                "image_generation": caps.image_generation,
                "audio": caps.audio,
            }
        return {
            "streaming": False,
            "vision": False,
            "tool_calling": False,
            "thinking": False,
            "offline": False,
            "embeddings": False,
            "planning": True,
            "image_generation": False,
            "audio": False,
        }

    def list_providers(self) -> dict:
        result = {}
        for name, provider in self._providers.items():
            caps = {}
            if hasattr(provider, "capabilities"):
                c = provider.capabilities
                caps = {
                    "streaming": c.streaming,
                    "vision": c.vision,
                    "tool_calling": c.tool_calling,
                    "thinking": c.thinking,
                    "offline": c.offline,
                    "embeddings": c.embeddings,
                    "planning": c.planning,
                    "image_generation": c.image_generation,
                    "audio": c.audio,
                }
            healthy, reason = self.health_check(name)
            result[name] = {
                "capabilities": caps,
                "available": healthy,
                "reason": reason,
            }
        return result

    def health_check(self, provider_name: str) -> tuple[bool, str]:
        provider = self._providers.get(provider_name)
        if not provider:
            return False, f"Provider {provider_name!r} not configured"
        if hasattr(provider, "health_check"):
            return provider.health_check()
        return True, "Ready"

    def get_provider_status(self) -> dict:
        status = {}
        for name, provider in self._providers.items():
            if provider:
                try:
                    if hasattr(provider, "health_check"):
                        healthy, reason = provider.health_check()
                    else:
                        healthy, reason = True, "Ready"
                    status[name] = {"available": healthy, "reason": reason}
                except Exception as e:
                    status[name] = {"available": False, "reason": str(e)}
            else:
                status[name] = {"available": False, "reason": "Not configured"}
        return status

    def complete(self, request) -> str:
        provider = self.get_active_provider()
        import logging
        logger = logging.getLogger("paios.api")
        logger.warning(
            f"[DIAGNOSTIC] ProviderManager complete start: active_provider_name={self._active_provider_name}, "
            f"active_provider_resolved={provider.name if provider else None}, fallback_chain={self._fallback_chain}"
        )
        if not provider:
            # Try fallback chain immediately
            for fallback_name in self._fallback_chain:
                if fallback_name == self._active_provider_name:
                    continue
                fallback_provider = self._providers.get(fallback_name)
                if fallback_provider:
                    logger.warning(
                        f"[DIAGNOSTIC] ProviderManager fallback triggered (no active provider for {self._active_provider_name}): falling back to {fallback_name}"
                    )
                    fallback_start = time.perf_counter()
                    try:
                        if fallback_name == "ollama" and hasattr(fallback_provider, "_model"):
                            from paios.assistant.adapters.ollama import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL
                            fallback_provider._model = OLLAMA_DEFAULT_MODEL
                        reply = fallback_provider.complete(request)
                        prompt_tokens = getattr(fallback_provider, "_last_prompt_tokens", 0)
                        completion_tokens = getattr(fallback_provider, "_last_completion_tokens", 0)
                        latency_ms = int((time.perf_counter() - fallback_start) * 1000)
                        self._log_request(
                            provider_name=fallback_provider.name,
                            latency_ms=latency_ms,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            success=True,
                            error=None,
                        )
                        return reply
                    except AdapterError as fallback_err:
                        latency_ms = int((time.perf_counter() - fallback_start) * 1000)
                        self._log_request(
                            provider_name=fallback_provider.name,
                            latency_ms=latency_ms,
                            prompt_tokens=0,
                            completion_tokens=0,
                            success=False,
                            error=str(fallback_err),
                        )
            raise AdapterError(f"No active provider configured for {self._active_provider_name!r}")

        start_time = time.perf_counter()
        
        # Primary attempt
        try:
            reply = provider.complete(request)
            prompt_tokens = getattr(provider, "_last_prompt_tokens", 0)
            completion_tokens = getattr(provider, "_last_completion_tokens", 0)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_request(
                provider_name=provider.name,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=True,
                error=None,
            )
            return reply
        except AdapterError as err:
            primary_error = str(err)
            logger.warning(
                f"[DIAGNOSTIC] ProviderManager: primary provider {provider.name} failed. "
                f"Exception: {type(err).__name__}: {err}"
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_request(
                provider_name=provider.name,
                latency_ms=latency_ms,
                prompt_tokens=0,
                completion_tokens=0,
                success=False,
                error=primary_error,
            )

            # Try fallback chain
            for fallback_name in self._fallback_chain:
                if fallback_name == self._active_provider_name:
                    continue
                fallback_provider = self._providers.get(fallback_name)
                if fallback_provider:
                    logger.warning(
                        f"[DIAGNOSTIC] ProviderManager fallback triggered (primary provider {provider.name} failed): falling back to {fallback_name}"
                    )
                    fallback_start = time.perf_counter()
                    try:
                        if fallback_name == "ollama" and hasattr(fallback_provider, "_model"):
                            from paios.assistant.adapters.ollama import DEFAULT_MODEL as OLLAMA_DEFAULT_MODEL
                            fallback_provider._model = OLLAMA_DEFAULT_MODEL
                        reply = fallback_provider.complete(request)
                        prompt_tokens = getattr(fallback_provider, "_last_prompt_tokens", 0)
                        completion_tokens = getattr(fallback_provider, "_last_completion_tokens", 0)
                        latency_ms = int((time.perf_counter() - fallback_start) * 1000)
                        self._log_request(
                            provider_name=fallback_provider.name,
                            latency_ms=latency_ms,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            success=True,
                            error=None,
                        )
                        return reply
                    except AdapterError as fallback_err:
                        latency_ms = int((time.perf_counter() - fallback_start) * 1000)
                        self._log_request(
                            provider_name=fallback_provider.name,
                            latency_ms=latency_ms,
                            prompt_tokens=0,
                            completion_tokens=0,
                            success=False,
                            error=str(fallback_err),
                        )
            raise err

    def complete_without_fallback(self, request) -> str:
        provider = self.get_active_provider()
        import logging
        logger = logging.getLogger("paios.api")
        logger.warning(
            f"[DIAGNOSTIC] ProviderManager complete_without_fallback: active_provider_name={self._active_provider_name}, "
            f"active_provider_resolved={provider.name if provider else None}"
        )
        if not provider:
            raise AdapterError(f"AI Provider {self._active_provider_name!r} could not be initialized (missing API key or SDK)")
        try:
            return provider.complete(request)
        except Exception as err:
            logger.warning(
                f"[DIAGNOSTIC] ProviderManager complete_without_fallback failed: Exception: {type(err).__name__}: {err}"
            )
            raise

    def _log_request(
        self,
        provider_name: str,
        latency_ms: int,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool,
        error: str | None,
    ) -> None:
        if self._log_callback:
            try:
                self._log_callback({
                    "provider": provider_name,
                    "latency_ms": latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "success": success,
                    "error": error,
                })
            except Exception:
                pass
