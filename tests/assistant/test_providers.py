import pytest
from paios.assistant import AssistantRequest, AssistantTask
from paios.assistant.adapters import AdapterError, AdapterUnavailableError
from paios.assistant.adapters.gemini import GeminiProvider
from paios.assistant.adapters.ollama import OllamaProvider
from paios.assistant.provider_manager import ProviderManager
from paios.api.assistant_support import calculate_cost


class FakeTransport:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def __call__(self, url, payload, headers=None, timeout=None):
        # Allow transport call signature of both:
        # (url, payload, timeout) -> Ollama
        # (url, payload, headers, timeout) -> Gemini
        self.calls.append((url, payload, headers, timeout))
        if self.error:
            raise self.error
        return self.reply


def test_gemini_provider_construction():
    # Raises when key is not set
    with pytest.raises(AdapterUnavailableError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key=None, transport=FakeTransport())

    # Succeeds with key
    provider = GeminiProvider(api_key="test-key", transport=FakeTransport())
    assert provider.name == "gemini:gemini-2.5-flash"


def test_gemini_provider_completion():
    response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello world from Gemini"}]
                }
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 12,
            "candidatesTokenCount": 8
        }
    }
    transport = FakeTransport(reply=response)
    provider = GeminiProvider(api_key="test-key", transport=transport)
    
    req = AssistantRequest(
        task=AssistantTask.ANSWER_QUESTION,
        template_name="t",
        system_prompt="sys",
        user_prompt="usr"
    )
    
    text = provider.complete(req)
    assert text == "Hello world from Gemini"
    assert provider._last_prompt_tokens == 12
    assert provider._last_completion_tokens == 8
    assert len(transport.calls) == 1
    assert "generateContent" in transport.calls[0][0]
    assert transport.calls[0][2]["x-goog-api-key"] == "test-key"


def test_gemini_provider_failure():
    transport = FakeTransport(error=OSError("network down"))
    provider = GeminiProvider(api_key="test-key", transport=transport)
    
    req = AssistantRequest(
        task=AssistantTask.ANSWER_QUESTION,
        template_name="t",
        system_prompt="sys",
        user_prompt="usr"
    )
    
    with pytest.raises(AdapterError, match="Gemini request failed"):
        provider.complete(req)


def test_provider_manager_success():
    gemini_resp = {
        "candidates": [{"content": {"parts": [{"text": "Gemini text"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}
    }
    gemini = GeminiProvider(api_key="test-key", transport=FakeTransport(reply=gemini_resp))
    
    logs = []
    manager = ProviderManager(
        active_provider_name="gemini",
        providers={"gemini": gemini},
        log_callback=logs.append
    )
    
    req = AssistantRequest(
        task=AssistantTask.ANSWER_QUESTION,
        template_name="t",
        system_prompt="sys",
        user_prompt="usr"
    )
    
    res = manager.complete(req)
    assert res == "Gemini text"
    assert len(logs) == 1
    assert logs[0]["provider"] == "gemini:gemini-2.5-flash"
    assert logs[0]["success"] is True
    assert logs[0]["prompt_tokens"] == 10
    assert logs[0]["completion_tokens"] == 5
    assert logs[0]["latency_ms"] >= 0


def test_provider_manager_fallback():
    # Gemini fails, Ollama succeeds
    gemini = GeminiProvider(api_key="test-key", transport=FakeTransport(error=AdapterError("Gemini down")))
    
    ollama_resp = {
        "message": {"content": "Ollama fallback text"},
        "prompt_eval_count": 25,
        "eval_count": 15
    }
    # Ollama needs custom probe response in construct, or we can mock/override. 
    # Let's bypass construct probe by passing a fake version transport
    probe_transport = FakeTransport(reply={"version": "1.0"})
    ollama = OllamaProvider(transport=probe_transport)
    # Now set its complete transport
    ollama._transport = FakeTransport(reply=ollama_resp)
    
    logs = []
    manager = ProviderManager(
        active_provider_name="gemini",
        providers={"gemini": gemini, "ollama": ollama},
        log_callback=logs.append
    )
    
    req = AssistantRequest(
        task=AssistantTask.ANSWER_QUESTION,
        template_name="t",
        system_prompt="sys",
        user_prompt="usr"
    )
    
    res = manager.complete(req)
    assert res == "Ollama fallback text"
    
    # Logs should capture:
    # 1. Gemini failure
    # 2. Ollama success
    assert len(logs) == 2
    assert logs[0]["provider"] == "gemini:gemini-2.5-flash"
    assert logs[0]["success"] is False
    assert "Gemini down" in logs[0]["error"]
    
    assert logs[1]["provider"] == "ollama:qwen2.5:7b"
    assert logs[1]["success"] is True
    assert logs[1]["prompt_tokens"] == 25
    assert logs[1]["completion_tokens"] == 15


def test_cost_calculation():
    # Gemini Flash
    assert calculate_cost("gemini:gemini-1.5-flash", 1000, 2000) == pytest.approx(0.000675) # 1000*0.075/1M + 2000*0.30/1M
    # Gemini Pro
    assert calculate_cost("gemini:gemini-1.5-pro", 1000, 2000) == pytest.approx(0.01125) # 1000*1.25/1M + 2000*5.00/1M
    # OpenAI GPT-4o
    assert calculate_cost("openai:gpt-4o", 1000, 2000) == pytest.approx(0.0225) # 1000*2.5/1M + 2000*10/1M
    # Claude Opus
    assert calculate_cost("anthropic:claude-opus-4-8", 1000, 2000) == pytest.approx(0.165) # 1000*15/1M + 2000*75/1M
    # Claude Sonnet
    assert calculate_cost("anthropic:claude-3-5-sonnet", 1000, 2000) == pytest.approx(0.033) # 1000*3/1M + 2000*15/1M
    # Ollama
    assert calculate_cost("ollama:qwen2.5:7b", 1000, 2000) == 0.0
