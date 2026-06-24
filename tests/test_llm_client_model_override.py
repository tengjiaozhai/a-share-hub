import json
from unittest.mock import patch, MagicMock
import httpx
from src.agents.llm_client import LLMClient
from src.core.config import Settings


def test_generate_json_uses_per_call_model():
    """generate_json 的 model 参数应覆盖默认模型"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(
            system_prompt="test",
            user_prompt="test",
            model="deepseek-v4-flash",
        )

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "deepseek-v4-flash"


def test_generate_json_uses_default_model_when_none():
    """model=None 时使用 self.model"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(system_prompt="test", user_prompt="test")

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "deepseek-v4-pro"


def test_generate_json_uses_configured_timeout():
    """超时应从 Settings.llm_timeout 读取"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(system_prompt="test", user_prompt="test")

        call_kwargs = mock_client_cls.call_args
        assert call_kwargs[1]["timeout"] == 300.0


def test_generate_json_retries_on_timeout():
    """超时应重试 3 次后成功"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    call_count = 0
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        return mock_response

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        result = client.generate_json(system_prompt="test", user_prompt="test")

        assert call_count == 3
        assert result == {"rating": "HOLD", "confidence": 0.5}