import json

import pytest

from src.agents.llm_client import LLMClient, LLMGenerationError
from src.core.config import Settings


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": self._content,
                    }
                }
            ]
        }


class _FakeClient:
    last_request: dict | None = None

    def __init__(self, *args, **kwargs) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers, json):
        _FakeClient.last_request = {
            "url": url,
            "headers": headers,
            "json": json,
        }
        return _FakeResponse(
            '{"symbol":"600519.SH","action":"BUY","confidence":80,"target_position_ratio":0.1,"reason":"ok"}'
        )


def test_llm_client_normalizes_deepseek_model_name_and_uses_json_output(monkeypatch):
    monkeypatch.setattr("src.agents.llm_client.httpx.Client", _FakeClient)

    settings = Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="DeepSeek-V4-Pro",
        llm_base_url="https://api.deepseek.com",
    )
    client = LLMClient(settings=settings)

    result = client.generate("请基于 json 格式输出 600519.SH 的决策")
    payload = _FakeClient.last_request["json"]

    assert json.loads(result)["action"] == "BUY"
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["max_tokens"] == 512
    assert payload["response_format"] == {"type": "json_object"}
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert "json" in payload["messages"][0]["content"].lower()
    assert payload["messages"][1]["role"] == "user"


def test_generate_json_requires_api_key():
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key=""))
    with pytest.raises(LLMGenerationError, match="LLM_API_KEY"):
        client.generate_json(system_prompt="system", user_prompt="user")


def test_generate_json_rejects_non_json(monkeypatch):
    monkeypatch.setattr(
        "src.agents.llm_client.LLMClient._post_chat",
        lambda self, payload: "not-json",
    )
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key="test-key"))
    with pytest.raises(LLMGenerationError, match="invalid JSON"):
        client.generate_json(system_prompt="system", user_prompt="user")


def test_generate_json_accepts_fenced_json(monkeypatch):
    monkeypatch.setattr(
        "src.agents.llm_client.LLMClient._post_chat",
        lambda self, payload: '```json\n{"rating":"HOLD","confidence":0.4}\n```',
    )
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key="test-key"))

    result = client.generate_json(system_prompt="system", user_prompt="user")

    assert result == {"rating": "HOLD", "confidence": 0.4}


def test_generate_json_accepts_json_after_text(monkeypatch):
    monkeypatch.setattr(
        "src.agents.llm_client.LLMClient._post_chat",
        lambda self, payload: '结论如下：{"action":"HOLD","position_ratio":0}',
    )
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key="test-key"))

    result = client.generate_json(system_prompt="system", user_prompt="user")

    assert result == {"action": "HOLD", "position_ratio": 0}


def test_generate_json_retries_when_deepseek_returns_empty_content(monkeypatch):
    responses = iter([
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "",
                        "reasoning_content": "internal reasoning",
                    },
                }
            ]
        },
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"rating":"HOLD","confidence":0.4}',
                    },
                }
            ]
        },
    ])
    payloads = []

    class RetryClient:
        def __init__(self, *args, **kwargs):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            payloads.append(dict(json))

            class Response:
                def __init__(self, body):
                    self._body = body

                def raise_for_status(self):
                    return None

                def json(self):
                    return self._body

            return Response(next(responses))

    monkeypatch.setattr("src.agents.llm_client.httpx.Client", RetryClient)
    monkeypatch.setattr("src.agents.llm_client.time.sleep", lambda *_: None)
    client = LLMClient(Settings(llm_provider="deepseek", llm_api_key="test-key"))

    result = client.generate_json(system_prompt="system", user_prompt="user", max_tokens=1400)

    assert result == {"rating": "HOLD", "confidence": 0.4}
    assert payloads[0]["max_tokens"] == 1400
    assert payloads[1]["max_tokens"] == 2200
