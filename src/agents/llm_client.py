import json
import logging
from typing import Optional

import httpx

from src.core.config import Settings

logger = logging.getLogger(__name__)


class LLMGenerationError(RuntimeError):
    pass


def _normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower()


def _loads_json_object(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        parsed = None
        for idx, char in enumerate(content):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(content[idx:])
            except json.JSONDecodeError:
                continue
            parsed = candidate
            break
        if parsed is None:
            raise
    if not isinstance(parsed, dict):
        raise LLMGenerationError("DeepSeek JSON response must be an object")
    return parsed


class LLMClient:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        s = settings or Settings()
        self.provider = s.llm_provider
        self.model = _normalize_model_name(s.llm_model)
        self.api_key = s.llm_api_key
        self.base_url = s.llm_base_url.rstrip("/")

    def generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """生成LLM响应，provider=mock 时返回固定响应，否则调用真实接口"""
        if self.provider == "mock" or not self.api_key:
            logger.debug("LLMClient: 使用 mock 模式")
            return json.dumps({
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 75,
                "target_position_ratio": 0.1,
                "reason": "Mock decision",
            }, ensure_ascii=False)

        try:
            system_prompt = (
                "你是一个A股量化交易助手。请只输出合法json，不要输出多余解释。"
                "返回字段必须包含 symbol, action, confidence, target_position_ratio, reason。"
                "示例json: {\"symbol\":\"600519.SH\",\"action\":\"BUY\",\"confidence\":80,"
                "\"target_position_ratio\":0.1,\"reason\":\"示例理由\"}"
            )
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": 512,
                        "response_format": {"type": "json_object"},
                    },
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info(f"LLMClient: 调用成功 model={self.model}")
            return content
        except Exception as e:
            logger.error(f"LLMClient: 调用失败 {e}，降级为 mock")
            return json.dumps({
                "symbol": "600519.SH",
                "action": "HOLD",
                "confidence": 0,
                "target_position_ratio": 0.0,
                "reason": f"LLM call failed: {e}",
            }, ensure_ascii=False)

    def _post_chat(self, payload: dict) -> str:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict:
        if self.provider == "mock" or not self.api_key:
            raise LLMGenerationError("DeepSeek analysis requires LLM_API_KEY")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            content = self._post_chat(payload)
            logger.info("DeepSeek raw content: %r", content[:2000])
            parsed = _loads_json_object(content)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError("DeepSeek returned invalid JSON") from exc
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise LLMGenerationError(f"DeepSeek request failed: {exc}") from exc
        return parsed
