"""Parser validation and adapter contracts."""

import json

import pytest

from paios.assistant import (
    AdapterError,
    AdapterUnavailableError,
    AssistantRequest,
    AssistantTask,
    LlmAdapter,
    NullAdapter,
    ResponseParseError,
)
from paios.assistant.response_parser import parse_response


def request() -> AssistantRequest:
    return AssistantRequest(
        task=AssistantTask.ANSWER_QUESTION,
        template_name="explain",
        system_prompt="system",
        user_prompt="user",
    )


class TestParser:
    def test_valid_response(self):
        parsed = parse_response(
            '{"answer": "Fine.", "bullets": ["a", "b"], "confidence": 0.5}'
        )
        assert parsed.answer == "Fine."
        assert parsed.bullets == ("a", "b")
        assert parsed.confidence == 0.5

    def test_bullets_and_confidence_are_optional(self):
        parsed = parse_response('{"answer": "Fine."}')
        assert parsed.bullets == ()
        assert parsed.confidence is None

    def test_fenced_json_is_accepted(self):
        parsed = parse_response('```json\n{"answer": "Fine."}\n```')
        assert parsed.answer == "Fine."

    @pytest.mark.parametrize(
        "text,match",
        [
            ("", "Empty"),
            ("   ", "Empty"),
            ("not json at all", "Malformed JSON"),
            ('{"answer": "x", ', "Malformed JSON"),
            ('["answer"]', "Expected a JSON object"),
            ('"just a string"', "Expected a JSON object"),
            ('{"bullets": []}', "Missing required field 'answer'"),
            ('{"answer": ""}', "non-empty string"),
            ('{"answer": 42}', "non-empty string"),
            ('{"answer": "x", "bullets": "nope"}', "list of strings"),
            ('{"answer": "x", "bullets": [1]}', "list of strings"),
            ('{"answer": "x", "confidence": "high"}', "number or null"),
            ('{"answer": "x", "confidence": true}', "number or null"),
            ('{"answer": "x", "confidence": 1.5}', "within"),
            ('{"answer": "x", "confidence": -0.1}', "within"),
        ],
    )
    def test_invalid_responses_are_rejected(self, text, match):
        with pytest.raises(ResponseParseError, match=match):
            parse_response(text)

    def test_result_is_immutable(self):
        parsed = parse_response('{"answer": "Fine."}')
        with pytest.raises(AttributeError):
            parsed.answer = "changed"


class TestAdapterContract:
    def test_abstract_base_enforced(self):
        with pytest.raises(TypeError):
            LlmAdapter()

        class Incomplete(LlmAdapter):
            @property
            def name(self):
                return "x"

        with pytest.raises(TypeError):
            Incomplete()

    def test_null_adapter_is_deterministic_and_parseable(self):
        adapter = NullAdapter()
        first = adapter.complete(request())
        second = adapter.complete(request())
        assert first == second
        parsed = parse_response(first)
        assert "AnswerQuestion" in parsed.answer
        assert parsed.confidence is None


class FakeAnthropicResponse:
    def __init__(self, text="", stop_reason="end_turn"):
        self.stop_reason = stop_reason
        block = type(
            "Block", (), {"type": "text", "text": text}
        )()
        self.content = [block] if text else []


class FakeAnthropicClient:
    def __init__(self, response):
        self.calls = []
        outer = self

        class Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                if isinstance(response, Exception):
                    raise response
                return response

        self.messages = Messages()


class TestAnthropicAdapter:
    def test_translates_request_and_response(self):
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        reply = json.dumps({"answer": "ok"})
        client = FakeAnthropicClient(FakeAnthropicResponse(reply))
        adapter = AnthropicAdapter(client=client)
        text = adapter.complete(request())
        assert text == reply
        call = client.calls[0]
        assert call["model"] == "claude-opus-4-8"
        assert call["system"] == "system"
        assert call["thinking"] == {"type": "adaptive"}
        assert call["messages"] == [{"role": "user", "content": "user"}]
        assert adapter.name == "anthropic:claude-opus-4-8"

    def test_refusal_becomes_adapter_error(self):
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        client = FakeAnthropicClient(
            FakeAnthropicResponse("partial", stop_reason="refusal")
        )
        with pytest.raises(AdapterError, match="refusal"):
            AnthropicAdapter(client=client).complete(request())

    def test_empty_content_becomes_adapter_error(self):
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        client = FakeAnthropicClient(FakeAnthropicResponse(""))
        with pytest.raises(AdapterError, match="no text"):
            AnthropicAdapter(client=client).complete(request())

    def test_sdk_exception_becomes_adapter_error(self):
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        client = FakeAnthropicClient(RuntimeError("boom"))
        with pytest.raises(AdapterError, match="boom"):
            AnthropicAdapter(client=client).complete(request())

    def test_unavailable_without_sdk(self):
        pytest.importorskip_reason = None
        try:
            import anthropic  # noqa: F401

            pytest.skip("anthropic SDK installed in this environment")
        except ImportError:
            pass
        from paios.assistant.adapters.anthropic import AnthropicAdapter

        with pytest.raises(AdapterUnavailableError):
            AnthropicAdapter()


class FakeOpenAIClient:
    def __init__(self, content):
        self.calls = []
        outer = self
        message = type("Message", (), {"content": content})()
        choice = type("Choice", (), {"message": message})()
        response = type("Response", (), {"choices": [choice]})()

        class Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return response

        self.chat = type("Chat", (), {"completions": Completions()})()


class TestOpenAIAdapter:
    def test_translates_request_and_response(self):
        from paios.assistant.adapters.openai import OpenAIAdapter

        client = FakeOpenAIClient('{"answer": "ok"}')
        adapter = OpenAIAdapter(client=client, model="gpt-4o")
        assert adapter.complete(request()) == '{"answer": "ok"}'
        call = client.calls[0]
        assert call["model"] == "gpt-4o"
        assert call["messages"][0] == {"role": "system", "content": "system"}
        assert call["messages"][1] == {"role": "user", "content": "user"}

    def test_empty_content_becomes_adapter_error(self):
        from paios.assistant.adapters.openai import OpenAIAdapter

        client = FakeOpenAIClient(None)
        with pytest.raises(AdapterError, match="no text"):
            OpenAIAdapter(client=client).complete(request())

    def test_unavailable_without_sdk(self):
        try:
            import openai  # noqa: F401

            pytest.skip("openai SDK installed in this environment")
        except ImportError:
            pass
        from paios.assistant.adapters.openai import OpenAIAdapter

        with pytest.raises(AdapterUnavailableError):
            OpenAIAdapter()
