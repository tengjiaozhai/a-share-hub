import json

from src.agents.llm_client import LLMClient
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
